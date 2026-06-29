# PROGRAM ARCHITECTURE

# P2P Networking threads: TCP communication

# Storage: local copy of blockchain
# Consensus engine: proof of work, validation
# Mempool: transactions

import json
import os
import sys
import threading
from typing import Dict, Any, List, Optional

_DEBUG = os.getenv("NODE_DEBUG") == "1"


def _dlog(port: int, msg: str) -> None:
    if _DEBUG:
        print(f"[node:{port}] {msg}", file=sys.stderr, flush=True)

import nacl.signing

from block import Block
from blockchain import Blockchain
from consensus import Consensus
from mempool import Mempool
from network import Network
from transaction import Transaction

# ./Run.sh <Port-Server> <Node-List-File>
# <Port-Server>: the port on which the node will run
# <Node-List-File>: a filename (ending in .txt) where each line is
# in the following format: host:port
class Node:

    def __init__(self, port: int, peers: List[str]):
        self.port = port
        self.peers = peers
        self.blockchain = Blockchain()
        self.mempool = Mempool()
        self.consensus = Consensus(self.blockchain, self.mempool)
        self.signing_key = nacl.signing.SigningKey.generate()

        self._round_trigger = threading.Event()
        self._round_lock = threading.Lock()
        self._current_proposal: Optional[dict] = None

        self.network = Network(
            port=port,
            peers=self.peers,
            on_transaction=self.submit_transaction,
            get_proposal=self._get_proposal_for_handler,
            on_values_received=self._on_values_received,
        )

    def _get_proposal_for_handler(self, requested_index: int) -> dict:
        # Return the in-progress round's proposal if it matches the requested index.
        if self._current_proposal is not None and self._current_proposal.get("index") == requested_index:
            return self._current_proposal
        if 0 < requested_index <= self.blockchain.last_block.index:
            for block in self.blockchain.chain:
                if block.index == requested_index:
                    return block.to_dict()
        return self.consensus._build_block().to_dict()

    def _on_values_received(self, incoming_index: int) -> None:
        if self._round_lock.locked():
            _dlog(self.port, f"values_received index={incoming_index}: round in progress, skipping")
            return
        if incoming_index == self.blockchain.last_block.index + 1:
            if len(self.mempool) > 0:
                _dlog(self.port, f"values_received index={incoming_index}: mempool non-empty, triggering round")
                self._round_trigger.set()
            else:
                _dlog(self.port, f"values_received index={incoming_index}: mempool empty, not triggering")

    def submit_transaction(self, payload: Dict[str, Any]) -> bool:
        try:
            raw_nonce = payload.get("nonce")
            if not isinstance(raw_nonce, int) or isinstance(raw_nonce, bool):
                _dlog(self.port, f"tx rejected: bad nonce type nonce={raw_nonce!r}")
                return False
            tx = Transaction(
                message=payload["message"],
                nonce=raw_nonce,
                sender=payload["sender"],
                signature=payload.get("signature"),
            )
        except (KeyError, TypeError) as e:
            _dlog(self.port, f"tx rejected: malformed payload {e}")
            return False
        added = self.mempool.add_transaction(tx)
        if added:
            _dlog(self.port, f"tx accepted: sender={tx.sender[:8]} nonce={tx.nonce}")
            print(json.dumps({"payload": payload, "type": "transaction"}, indent=2, sort_keys=True), flush=True)
            self.network.broadcast_transaction(payload)
            self._round_trigger.set()
        else:
            expected = self.mempool._confirmed_nonces.get(tx.sender, 0)
            _dlog(self.port, f"tx rejected: sender={tx.sender[:8]} nonce={tx.nonce} expected={expected}")
        return added

    def _consensus_loop(self) -> None:
        # Exit after 5 s of no triggered rounds so the process ends naturally.
        while self._round_trigger.wait(timeout=5.0):
            try:
                with self._round_lock:
                    self._round_trigger.clear()
                    if len(self.mempool) == 0:
                        continue
                    _dlog(self.port, f"round starting: chain_len={len(self.blockchain.chain)} mempool={len(self.mempool)}")
                    self._do_round()
                    if len(self.mempool) > 0:
                        self._round_trigger.set()
                    else:
                        self._round_trigger.clear()
            except Exception as e:
                _dlog(self.port, f"round exception: {e}")

    def _do_round(self) -> bool:
        local_block = self.consensus.propose_block()
        self._current_proposal = local_block.to_dict()
        try:
            if self.network.active_peer_count() > 0:
                peer_proposals = self.network.exchange_values(self._current_proposal)
                _dlog(self.port, f"exchange_values: got {len(peer_proposals)} peer proposal(s)")
                candidates = [local_block]
                for p in peer_proposals:
                    try:
                        candidates.append(Block.from_dict(p))
                    except Exception:
                        pass
            else:
                _dlog(self.port, f"no active peers, using local proposal only")
                candidates = [local_block]
        finally:
            self._current_proposal = None

        valid = [b for b in candidates if self.consensus.decide_block(b)]
        _dlog(self.port, f"valid proposals: {len(valid)}/{len(candidates)}")
        if not valid:
            _dlog(self.port, "no valid proposals, round aborted")
            return False

        non_empty = [b for b in valid if b.transactions]
        decided = min(non_empty if non_empty else valid, key=lambda b: b.current_hash)
        _dlog(self.port, f"decided block index={decided.index} txs={len(decided.transactions)} hash={decided.current_hash[:12]}")
        committed = self.consensus.commit_block(decided)
        if committed:
            _dlog(self.port, f"committed block index={decided.index}")
            print(json.dumps(decided.to_dict(), indent=2, sort_keys=True), flush=True)
        else:
            _dlog(self.port, f"commit_block returned False for index={decided.index}")
        return committed

    def run(self) -> None:
        self.network.start()
        # Daemon so it is killed immediately if the main thread exits early
        # (e.g. SIGTERM / KeyboardInterrupt); join() keeps the process alive
        # until the idle timeout fires naturally.
        t = threading.Thread(target=self._consensus_loop, daemon=True)
        t.start()
        try:
            t.join()
        except KeyboardInterrupt:
            pass
        with self._round_lock:
            pass
        self.network.close()

    @staticmethod
    def load_node_list(filename: str) -> List[str]:
        peers: List[str] = []
        try:
            with open(filename, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        peers.append(line)
        except FileNotFoundError:
            print(f"Node list file not found: {filename}", file=sys.stderr)
        except OSError as err:
            print(f"Error reading node list file: {err}", file=sys.stderr)
        return peers


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 2 or not args[0].isdigit() or not args[1].endswith(".txt"):
        print(f"Usage: {sys.argv[0]} <port> <node-list.txt>", file=sys.stderr)
        return 1
    port = int(args[0])
    peers = Node.load_node_list(args[1])
    Node(port=port, peers=peers).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# CONSENSUS ROUND

# 1. Trigger a new round
# 2. Block proposal creation
# 3. Exchange proposal (broadcast phase)
# 4. Decision on block (consensus decision)
# 5. Commit the decided block
# 6. Prepare for the next round

from typing import List

from blockchain import Blockchain
from block import Block
from mempool import Mempool
from transaction import Transaction
from utils import hash_json


class Consensus:
    """Proposes local blocks and commits the peer-decided block."""

    def __init__(self, blockchain: Blockchain, mempool: Mempool):
        self.blockchain = blockchain
        self.mempool = mempool
        self.round = 0

    def new_round(self) -> None:
        self.round += 1

    def propose_block(self) -> Block:
        self.new_round()
        return self._build_block()

    def _build_block(self) -> Block:
        txs = self.mempool.all_transactions()
        index = self.blockchain.last_block.index + 1
        previous_hash = self.blockchain.last_block.current_hash
        current_hash = self._compute_block_hash(index, previous_hash, txs)
        return Block(
            current_hash=current_hash,
            index=index,
            previous_hash=previous_hash,
            transactions=txs,
        )

    def decide_block(self, block: Block) -> bool:
        return self.blockchain.is_valid_new_block(block, self.blockchain.last_block)

    def commit_block(self, block: Block) -> bool:
        if self.blockchain.add_block(block):
            self.mempool.commit(block.transactions)
            return True
        return False

    def _compute_block_hash(self, index: int, previous_hash: str, transactions: List[Transaction]) -> str:
        payload = {
            "index": index,
            "previous_hash": previous_hash,
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx
                for tx in transactions
            ],
        }
        return hash_json(payload)

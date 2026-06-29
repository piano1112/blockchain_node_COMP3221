import json
import os
import socket
import struct
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

_HEADER = ">H"
_HDR_SIZE = struct.calcsize(_HEADER)
_MAX_MSG = 65535
_VALUES_TIMEOUT = 2.0
_RETRY_DELAY = 0.5
_DEBUG = os.getenv("NODE_DEBUG") == "1"


def _dlog(port: int, msg: str) -> None:
    if _DEBUG:
        print(f"[net:{port}] {msg}", file=sys.stderr, flush=True)


def _send_msg(sock: socket.socket, msg: dict) -> None:
    data = json.dumps(msg, sort_keys=True).encode("utf-8")
    if len(data) > _MAX_MSG:
        raise ValueError(f"Message exceeds {_MAX_MSG} bytes")
    sock.sendall(struct.pack(_HEADER, len(data)) + data)


def _recv_msg(sock: socket.socket) -> dict:
    header = _recv_exact(sock, _HDR_SIZE)
    n = struct.unpack(_HEADER, header)[0]
    return json.loads(_recv_exact(sock, n).decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed")
        buf += chunk
    return bytes(buf)


class Network:
    def __init__(
        self,
        port: int,
        peers: List[str],
        on_transaction: Callable[[dict], Any],
        get_proposal: Callable[[int], dict],
        on_values_received: Callable[[int], None],
    ):
        self.port = port
        self.peers = list(peers)
        self._on_transaction = on_transaction
        self._get_proposal = get_proposal
        self._on_values_received = on_values_received
        self._sockets: Dict[str, socket.socket] = {}
        self._crashed: set = set()
        self._lock = threading.Lock()
        self._server_sock: Optional[socket.socket] = None

    def start(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", self.port))
        srv.listen()
        self._server_sock = srv
        threading.Thread(target=self._serve, args=(srv,), daemon=True).start()
        for peer in self.peers:
            threading.Thread(target=self._connect, args=(peer,), daemon=True).start()

    def close(self) -> None:
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        with self._lock:
            for sock in self._sockets.values():
                try:
                    sock.close()
                except OSError:
                    pass
            self._sockets.clear()

    def broadcast_transaction(self, tx_dict: dict) -> None:
        """Forward a validated transaction to all peers via fresh connections."""
        msg = {"type": "transaction", "payload": tx_dict}
        for peer in self.peers:
            threading.Thread(target=self._forward_to_peer, args=(peer, msg), daemon=True).start()

    def _forward_to_peer(self, peer: str, msg: dict) -> None:
        host, port_str = peer.rsplit(":", 1)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((host, int(port_str)))
            _send_msg(sock, msg)
            sock.close()
            _dlog(self.port, f"forwarded tx to {peer}")
        except Exception as e:
            _dlog(self.port, f"forward to {peer} failed: {e}")

    def exchange_values(self, my_proposal: dict) -> List[dict]:
        """Send proposal to all active peers in parallel and collect their proposals."""
        with self._lock:
            active = [(p, s) for p, s in self._sockets.items() if p not in self._crashed]

        results: List[dict] = []
        results_lock = threading.Lock()

        def _exchange(peer: str, sock: socket.socket) -> None:
            sock.settimeout(_VALUES_TIMEOUT)
            try:
                _send_msg(sock, {"type": "values", "payload": [my_proposal]})
                reply = _recv_msg(sock)
                payload = reply.get("payload", [])
                if payload:
                    with results_lock:
                        results.append(payload[0])
            except (OSError, socket.timeout) as e:
                _dlog(self.port, f"exchange with {peer} failed: {e}")
                with self._lock:
                    self._crashed.add(peer)
            finally:
                sock.settimeout(None)

        threads = [threading.Thread(target=_exchange, args=(p, s)) for p, s in active]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def active_peer_count(self) -> int:
        with self._lock:
            return sum(1 for p in self.peers if p not in self._crashed and p in self._sockets)

    def _serve(self, srv: socket.socket) -> None:
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            while True:
                msg = _recv_msg(conn)
                mtype = msg.get("type")
                if mtype == "transaction":
                    result = self._on_transaction(msg.get("payload", {}))
                    resp = b"true" if result else b"false"
                    conn.sendall(struct.pack(_HEADER, len(resp)) + resp)
                elif mtype == "values":
                    payload = msg.get("payload", [])
                    incoming_index = payload[0].get("index", -1) if payload else -1
                    proposal = self._get_proposal(incoming_index)
                    _send_msg(conn, {"type": "values", "payload": [proposal]})
                    self._on_values_received(incoming_index)
        except Exception:
            pass
        finally:
            conn.close()

    def _connect(self, peer: str) -> None:
        host, port_str = peer.rsplit(":", 1)
        while True:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, int(port_str)))
                with self._lock:
                    self._sockets[peer] = sock
                _dlog(self.port, f"connected to {peer}")
                return
            except OSError:
                sock.close()
                time.sleep(_RETRY_DELAY)

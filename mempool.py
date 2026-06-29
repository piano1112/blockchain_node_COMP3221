import threading
from typing import Dict, List

from transaction import Transaction


class Mempool:

    def __init__(self):
        self._transactions: Dict[str, Transaction] = {}
        self._confirmed_nonces: Dict[str, int] = {}
        self._lock = threading.Lock()

    def add_transaction(self, tx: Transaction) -> bool:
        if not isinstance(tx, Transaction):
            return False
        with self._lock:
            if not self._is_valid_format(tx):
                return False
            if tx.nonce != self._confirmed_nonces.get(tx.sender, 0):
                return False
            key = self._tx_key(tx)
            if key in self._transactions:
                return False
            self._transactions[key] = tx
            return True

    def commit(self, committed_txs: List[Transaction]) -> None:
        """Update confirmed nonces and evict now-invalid transactions after a block is committed."""
        with self._lock:
            for tx in committed_txs:
                self._confirmed_nonces[tx.sender] = tx.nonce + 1
                self._transactions.pop(self._tx_key(tx), None)
            invalid = [
                k for k, t in self._transactions.items()
                if t.nonce != self._confirmed_nonces.get(t.sender, 0)
            ]
            for k in invalid:
                del self._transactions[k]

    def all_transactions(self) -> List[Transaction]:
        with self._lock:
            return list(self._transactions.values())

    def _tx_key(self, tx: Transaction) -> str:
        return f"{tx.sender}:{tx.nonce}"

    def _is_valid_format(self, tx: Transaction) -> bool:
        if not tx.sender or not isinstance(tx.sender, str):
            return False
        if len(tx.sender) != 64 or not all(c in '0123456789abcdef' for c in tx.sender):
            return False
        if not isinstance(tx.nonce, int) or isinstance(tx.nonce, bool) or tx.nonce < 0:
            return False
        if not isinstance(tx.message, str) or len(tx.message) > 70:
            return False
        if not all(32 <= ord(c) <= 126 for c in tx.message):
            return False
        if not tx.signature or not isinstance(tx.signature, str):
            return False
        if len(tx.signature) != 128 or not all(c in '0123456789abcdefABCDEF' for c in tx.signature):
            return False
        return tx.verify()

    def __len__(self) -> int:
        with self._lock:
            return len(self._transactions)

    def __repr__(self) -> str:
        with self._lock:
            return f"Mempool(size={len(self._transactions)})"

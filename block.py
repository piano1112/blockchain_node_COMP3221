import json

from transaction import Transaction

# Block proposal -> Enter consensus protocol -> Rejcct/Agree -> Update/execute transactions
class Block:

    def __init__(self, current_hash, index, previous_hash, transactions=None):
        self.current_hash = current_hash # SHA-256
        self.index = index # 1, 2, 3, ..., 1 for genesis block
        self.previous_hash = previous_hash # Previous block's current_hash
        self.transactions = transactions or []

    def to_dict(self):
        return {
            "current_hash": self.current_hash,
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": [
                tx.to_dict() if hasattr(tx, "to_dict") else tx
                for tx in self.transactions
            ],
        }

    @classmethod
    def from_dict(cls, data):
        transactions = [
            Transaction.from_dict(tx) if isinstance(tx, dict) else tx
            for tx in data.get("transactions", [])
        ]
        return cls(
            current_hash=data["current_hash"],
            index=data["index"],
            previous_hash=data["previous_hash"],
            transactions=transactions,
        )

    def serialize(self):
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=2,
            separators=(',', ': '),
        )

    def __repr__(self):
        return (
            f"Block(index={self.index}, current_hash={self.current_hash!r}, "
            f"previous_hash={self.previous_hash!r}, transactions={len(self.transactions)})"
        )

import json
from typing import List, Optional

from block import Block
from utils import hash_json


class Blockchain:
    """Basic blockchain container for chain state and validation."""

    def __init__(self, chain: Optional[List[Block]] = None):
        self.chain = chain if chain is not None else [self.new_genesis_block()]

    @staticmethod
    def new_genesis_block() -> Block:
        index = 1
        previous_hash = "0" * 64
        payload = {"index": index, "previous_hash": previous_hash, "transactions": []}
        current_hash = hash_json(payload)
        return Block(
            current_hash=current_hash,
            index=index,
            previous_hash=previous_hash,
            transactions=[],
        )

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, block: Block) -> bool:
        if self.is_valid_new_block(block, self.last_block):
            self.chain.append(block)
            return True
        return False

    def is_valid_new_block(self, block: Block, previous_block: Block) -> bool:
        if previous_block.index + 1 != block.index:
            return False
        if previous_block.current_hash != block.previous_hash:
            return False
        if not block.current_hash:
            return False
        return True

    def is_valid_chain(self, chain: List[Block]) -> bool:
        if not chain:
            return False
        if chain[0].current_hash != self.chain[0].current_hash:
            return False
        for previous_block, block in zip(chain, chain[1:]):
            if not self.is_valid_new_block(block, previous_block):
                return False
        return True

    def to_dict(self) -> dict:
        return {"chain": [block.to_dict() for block in self.chain]}

    @classmethod
    def from_dict(cls, data: dict) -> "Blockchain":
        chain = [Block.from_dict(block) for block in data.get("chain", [])]
        return cls(chain=chain)

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def __repr__(self) -> str:
        return f"Blockchain(length={len(self.chain)})"



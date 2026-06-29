import json

import nacl.signing
import nacl.exceptions

# JSON Object
# Send -> Receive -> To JSON (dict) -> Validate -> Refuse/Accept + Response (T/F) -> Pooled + Printed
class Transaction:
    def __init__(self, message, nonce, sender, signature=None):
        self.message = message # UTF-8 text, Up to 70 alphanumeric characters and spaces
        self.nonce = nonce # 0, 1, 2, 3, ... for each sender
        self.sender = sender # Hex-encoded 32-byte Ed25519 public key
        self.signature = signature # Hex-encoded 64-byte Ed25519 signature

    def to_dict(self):
        return {
            "message": self.message,
            "nonce": self.nonce,
            "sender": self.sender,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            message=data["message"],
            nonce=data["nonce"],
            sender=data["sender"],
            signature=data.get("signature"),
        )

    def signed_payload(self) -> bytes:
        """Canonical bytes that the sender signs (excludes the signature field)."""
        body = {"message": self.message, "nonce": self.nonce, "sender": self.sender}
        return json.dumps(body, sort_keys=True).encode("utf-8")

    def verify(self) -> bool:
        """Return True if the signature is a valid Ed25519 signature over signed_payload()."""
        if not self.signature:
            return False
        try:
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(self.sender))
            verify_key.verify(self.signed_payload(), bytes.fromhex(self.signature))
            return True
        except (nacl.exceptions.BadSignatureError, ValueError):
            return False

    def serialize(self):
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=2,
            separators=(',', ': '),
        )

    def __repr__(self):
        return (
            f"Transaction(sender={self.sender!r}, nonce={self.nonce}, "
            f"message={self.message!r})"
        )

    
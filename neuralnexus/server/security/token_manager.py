"""
security/token_manager.py
-------------------------
AES-256-CBC encryption / decryption for NeuralNexus session tokens.

Token format (plaintext):  "{user_id}|{role}|{YYYYMMDDHHMMSS_expiry}"
Token format (wire):       URL-safe base64( IV + ciphertext )
"""

import base64
import hashlib

from security.settings import settings
from Crypto import Random
from Crypto.Cipher import AES


class AESCipher:
    """Symmetric AES-256-CBC cipher wrapper used for session token management."""

    def __init__(self, key: str) -> None:
        self.block_size = AES.block_size
        # Derive a 32-byte key from the secret via SHA-256
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw: str) -> str:
        """Encrypt *raw* and return a URL-safe base64-encoded ciphertext string."""
        padded = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.urlsafe_b64encode(iv + cipher.encrypt(padded.encode())).decode()

    def decrypt(self, enc: str) -> str:
        """Decrypt a URL-safe base64-encoded token and return the plaintext."""
        raw = base64.urlsafe_b64decode(enc)
        iv = raw[: AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return AESCipher._unpad(cipher.decrypt(raw[AES.block_size:])).decode("utf-8")

    def _pad(self, s: str) -> str:
        pad_len = self.block_size - len(s) % self.block_size
        return s + pad_len * chr(pad_len)

    @staticmethod
    def _unpad(s: bytes) -> bytes:
        return s[: -ord(s[-1:])]


# Module-level singleton used by decorators and helpers
session_manager = AESCipher(settings.AES_SECRET)

# Legacy alias kept for backward compatibility
sessionManager = session_manager

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    """Small Fernet wrapper for encrypting Canvas PATs at rest."""

    def __init__(self, key: str | bytes):
        if isinstance(key, str):
            key = key.encode("utf-8")
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("CANVAS_ENCRYPTION_KEY must be a valid Fernet key") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("Cannot encrypt an empty token")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ValueError("Unable to decrypt Canvas token") from exc

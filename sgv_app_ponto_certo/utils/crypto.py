import os
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    Fernet = None


def _get_key_from_env() -> Optional[bytes]:
    k = os.environ.get("PIX_FERNET_KEY")
    if not k:
        return None
    try:
        return k.encode("utf-8")
    except Exception:
        return None


def encrypt_str(value: str) -> str:
    """Encrypt a string using Fernet if available and key present. Returns base64 string.

    If no key/cryptography available, returns the original value (NOT secure).
    """
    if not value:
        return ""
    key = _get_key_from_env()
    if not key or Fernet is None:
        return value
    f = Fernet(key)
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_str(value: str) -> str:
    """Decrypt a string encrypted with Fernet. If decryption fails or no key, returns original."""
    if not value:
        return ""
    key = _get_key_from_env()
    if not key or Fernet is None:
        return value
    f = Fernet(key)
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value

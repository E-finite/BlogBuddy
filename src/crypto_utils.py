"""Encryption utilities for storing sensitive credentials."""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src import config


def _get_fernet_key() -> bytes:
    """Derive a Fernet key from MASTER_KEY."""
    master_key_bytes = config.MASTER_KEY.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'wp_blog_generator_salt',
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key_bytes))
    return key


_fernet = Fernet(_get_fernet_key())


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string and return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    encrypted = _fernet.encrypt(plaintext.encode())
    return base64.b64encode(encrypted).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext and return plaintext."""
    if not ciphertext:
        return ""
    encrypted_bytes = base64.b64decode(ciphertext.encode())
    decrypted = _fernet.decrypt(encrypted_bytes)
    return decrypted.decode()

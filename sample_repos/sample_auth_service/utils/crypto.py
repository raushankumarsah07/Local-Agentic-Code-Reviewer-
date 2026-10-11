"""Cryptographic utility functions."""
import hashlib
import hmac
import base64

def hash_password(password: str, salt: str = "salt123") -> str:
    """Hashes a password using SHA-256 with salt."""
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return base64.b64encode(key).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str, salt: str = "salt123") -> bool:
    """Verifies a plain password against the stored hash."""
    return hash_password(plain_password, salt) == hashed_password

def unused_crypto_helper():
    """Unused dead code function."""
    return "legacy_md5_signature"

"""Authentication business logic."""
import time
from utils.crypto import hash_password, verify_password
from utils.validators import validate_email, validate_password_strength

class AuthService:
    def __init__(self):
        self.users_db = {}
        self.failed_attempts = {}

    def register_user(self, email: str, password: str, role: str = "member") -> dict:
        if not validate_email(email):
            raise ValueError("Invalid email format")
        if not validate_password_strength(password):
            raise ValueError("Password does not meet security criteria")
        if email in self.users_db:
            raise ValueError("User already registered")

        pwd_hash = hash_password(password)
        user_record = {
            "user_id": f"usr_{len(self.users_db) + 1}",
            "email": email,
            "password_hash": pwd_hash,
            "role": role,
            "created_at": time.time(),
        }
        self.users_db[email] = user_record
        return user_record

    def authenticate_user(self, email: str, password: str) -> dict:
        user = self.users_db.get(email)
        if not user:
            raise PermissionError("User not found")
        if not verify_password(password, user["password_hash"]):
            self.failed_attempts[email] = self.failed_attempts.get(email, 0) + 1
            raise PermissionError("Invalid password")
        return user

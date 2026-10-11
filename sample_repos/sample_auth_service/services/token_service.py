"""JWT Token generation and verification service."""
import base64
import json
import time
from config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

class TokenService:
    def __init__(self, secret: str = JWT_SECRET_KEY):
        self.secret = secret

    def generate_access_token(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "exp": time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        }
        encoded_payload = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = base64.b64encode(f"{encoded_payload}:{self.secret}".encode()).decode()
        return f"{encoded_payload}.{signature}"

    def verify_token(self, token: str) -> dict:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Malformed token")
        payload_b64, signature = parts
        expected_sig = base64.b64encode(f"{payload_b64}:{self.secret}".encode()).decode()
        if signature != expected_sig:
            raise PermissionError("Signature verification failed")
        data = json.loads(base64.b64decode(payload_b64.encode()).decode())
        if data.get("exp", 0) < time.time():
            raise TimeoutError("Token expired")
        return data

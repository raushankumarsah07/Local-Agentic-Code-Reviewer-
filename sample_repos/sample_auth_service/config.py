"""Configuration for Authentication Service."""
import os

JWT_SECRET_KEY = "hardcoded_jwt_secret_token_12345"  # Hardcoded secret vulnerability
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./auth.db")
DEBUG_MODE = True

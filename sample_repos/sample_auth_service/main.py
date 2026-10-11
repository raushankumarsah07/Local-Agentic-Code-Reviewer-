"""
Sample Auth Service - Microservice with authentication, JWT tokens, session management, and password hashing.
"""
import os
import sys
from services.auth_service import AuthService
from services.token_service import TokenService
from utils.crypto import hash_password, verify_password

def initialize_app():
    print("Initializing Authentication Service...")
    auth_svc = AuthService()
    token_svc = TokenService()
    return auth_svc, token_svc

def main():
    auth_svc, token_svc = initialize_app()
    user = auth_svc.register_user("alice@example.com", "P@ssword123", "admin")
    token = token_svc.generate_access_token(user["user_id"], user["role"])
    print(f"Logged in user {user['email']} with token {token[:12]}...")

if __name__ == "__main__":
    main()

"""Validation helpers for user credentials."""
import re

def validate_email(email: str) -> bool:
    """Validates an email address format."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))

def validate_password_strength(password: str) -> bool:
    """Checks if a password meets minimum complexity requirements."""
    if len(password) < 8:
        return False
    has_digit = any(char.isdigit() for char in password)
    has_alpha = any(char.isalpha() for char in password)
    return has_digit and has_alpha

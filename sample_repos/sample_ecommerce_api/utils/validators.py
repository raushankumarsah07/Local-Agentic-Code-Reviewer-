"""
Validation helpers for e-commerce requests.
"""

from config import MAX_ITEMS_PER_ORDER


def validate_email_address(email: str) -> bool:
    """Check basic email structure."""
    if not email or "@" not in email:
        return False
    parts = email.split("@")
    return len(parts) == 2 and "." in parts[1]


def validate_order_item_quantities(items: list) -> bool:
    """Ensure cart contains valid items and adheres to system limits."""
    if not items or len(items) > MAX_ITEMS_PER_ORDER:
        return False
    for item in items:
        if item.quantity <= 0 or item.unit_price < 0:
            return False
    return True

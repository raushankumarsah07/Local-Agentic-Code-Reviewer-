"""
Security helpers for signature validation and data obfuscation.
"""

import hmac
import hashlib
from config import PAYMENT_WEBHOOK_SECRET


def verify_webhook_signature(payload: str, signature_header: str) -> bool:
    """Validate incoming payment webhook HMAC signature."""
    if not signature_header or not payload:
        return False
    expected = hmac.new(
        PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def mask_credit_card(card_number: str) -> str:
    """Mask card number showing only last 4 digits."""
    clean = "".join(filter(str.isdigit, card_number))
    if len(clean) < 4:
        return "****"
    return "*" * (len(clean) - 4) + clean[-4:]

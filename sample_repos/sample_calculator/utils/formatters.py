"""
Formatting utilities with regular expression sanitation.
"""

import re


def clean_string(text: str) -> str:
    """Strip extraneous non-numeric or non-alphabetic characters."""
    return re.sub(r"\s+", " ", text).strip()

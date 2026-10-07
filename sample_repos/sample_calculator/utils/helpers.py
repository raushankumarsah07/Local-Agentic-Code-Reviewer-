"""
Utility helper functions for calculator input validation and formatting.
"""

from typing import Union


def validate_number(value: Union[int, float]) -> bool:
    """Validate that input is a numeric value."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"Expected number, got {type(value).__name__}")
    return True


def format_result(val: float) -> float:
    """Round result to 4 decimal places."""
    return round(val, 4)

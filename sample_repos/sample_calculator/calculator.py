"""
Calculator module implementing Basic and Scientific calculators.
"""

import math
from utils.helpers import validate_number, format_result
from config import PRECISION


class BasicCalculator:
    """Performs standard arithmetic operations."""

    def add(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(round(a + b, PRECISION))

    def subtract(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(round(a - b, PRECISION))

    def multiply(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(round(a * b, PRECISION))

    def divide(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return format_result(round(a / b, PRECISION))


class ScientificCalculator(BasicCalculator):
    """Extends BasicCalculator with exponential and power operations."""

    def power(self, base: float, exp: float) -> float:
        validate_number(base)
        validate_number(exp)
        return format_result(round(base ** exp, PRECISION))

    def sqrt(self, val: float) -> float:
        validate_number(val)
        if val < 0:
            raise ValueError("Cannot compute sqrt of negative number.")
        return format_result(round(math.sqrt(val), PRECISION))

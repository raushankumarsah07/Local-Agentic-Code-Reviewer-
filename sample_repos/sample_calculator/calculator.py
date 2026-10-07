"""
Calculator module implementing Basic and Scientific calculators.
"""

from utils.helpers import validate_number, format_result


class BasicCalculator:
    """Performs standard arithmetic operations."""

    def add(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(a + b)

    def subtract(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(a - b)

    def multiply(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        return format_result(a * b)

    def divide(self, a: float, b: float) -> float:
        validate_number(a)
        validate_number(b)
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return format_result(a / b)


class ScientificCalculator(BasicCalculator):
    """Extends BasicCalculator with exponential and power operations."""

    def power(self, base: float, exp: float) -> float:
        validate_number(base)
        validate_number(exp)
        return format_result(base ** exp)

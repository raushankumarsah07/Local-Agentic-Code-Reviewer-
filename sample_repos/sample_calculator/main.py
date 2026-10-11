"""
Simple Calculator App Entry Point.
"""

import sys
from calculator import BasicCalculator, ScientificCalculator
from utils.helpers import format_result
from config import APP_CONFIG


def run():
    print(f"Starting {APP_CONFIG['app_name']} v{APP_CONFIG['version']} on {sys.platform}...")

    basic = BasicCalculator()
    print("Add 5 + 3 =", basic.add(5, 3))
    print("Multiply 4 * 7 =", basic.multiply(4, 7))

    sci = ScientificCalculator()
    print("Power 2 ^ 4 =", sci.power(2, 4))
    print("Sqrt 16 =", sci.sqrt(16))

    print("Formatted Result:", format_result(42.00001))


if __name__ == "__main__":
    run()

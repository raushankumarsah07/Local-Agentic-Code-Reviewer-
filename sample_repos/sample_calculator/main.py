"""
Simple Calculator App Entry Point.
"""

from calculator import BasicCalculator, ScientificCalculator


def run():
    basic = BasicCalculator()
    print("Add 5 + 3 =", basic.add(5, 3))
    print("Multiply 4 * 7 =", basic.multiply(4, 7))

    sci = ScientificCalculator()
    print("Power 2 ^ 4 =", sci.power(2, 4))


if __name__ == "__main__":
    run()

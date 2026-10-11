"""
Configuration settings for the calculator app.
"""

import os

PRECISION = int(os.getenv("CALC_PRECISION", "4"))
APP_CONFIG = {
    "app_name": "Modular Calculator",
    "version": "1.0.0",
    "precision": PRECISION,
}

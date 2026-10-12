"""
Local Agentic Code Reviewer and Architecture Grapher - Backend Application
"""

import sys
from pathlib import Path

# Ensure 'backend' directory is in sys.path so 'app.*' imports resolve
# regardless of whether the working directory is the repo root or backend/
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

__version__ = "0.1.0"

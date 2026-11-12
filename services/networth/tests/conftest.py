"""
Test fixtures for Networth and Analytics Microservice.
Dynamically imports backend/tests/conftest.py so fixtures and helper functions are globally available.
"""

import sys
import importlib.util
from pathlib import Path

# Add backend directory to sys.path so app modules resolve
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

backend_conftest_path = BACKEND_DIR / "tests" / "conftest.py"
spec = importlib.util.spec_from_file_location("backend_conftest", backend_conftest_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["backend_conftest"] = mod
sys.modules["tests.conftest"] = mod
spec.loader.exec_module(mod)

for attr in dir(mod):
    if not attr.startswith("__"):
        globals()[attr] = getattr(mod, attr)

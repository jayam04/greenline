import sys
from pathlib import Path


NETWORTH_SERVICE_ROOT = Path(__file__).resolve().parents[2] / "networth"
if str(NETWORTH_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(NETWORTH_SERVICE_ROOT))

"""Additional Roxy page; existing terminal/trading execution stay unchanged."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roxy_live import render_live

render_live()

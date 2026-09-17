"""Additional opt-in mobile view; the existing terminal stays unchanged."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roxy_live_mobile import render_mobile_live

render_mobile_live()

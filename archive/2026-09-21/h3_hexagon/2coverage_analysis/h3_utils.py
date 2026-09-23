"""Backward-compatible shim. Prefer ``lib.h3_grid``."""

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from lib.h3_grid import *  # noqa: F401,F403

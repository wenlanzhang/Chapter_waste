"""Shared output paths for Step 3 (3_100m) grid, validation, and mitigation tables."""

from __future__ import annotations

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from chapter_paths import (  # noqa: E402
    active_grid_gpkg,
    extend_dir,
    grid100_dir,
    prep_dir,
)

INPUT_DIR = prep_dir()
OUTPUT_DIR = grid100_dir()
EXTEND_DIR = extend_dir()

GRID_DIR = OUTPUT_DIR / "grid"
VALIDATION_DIR = OUTPUT_DIR / "validation"
MITIGATION_DIR = OUTPUT_DIR / "mitigation"

GRID_GPKG = active_grid_gpkg()

"""Shared output paths for Step 3 (3_100m) grid, validation, and mitigation tables."""

from pathlib import Path

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"
EXTEND_DIR = DATA_ROOT / "Chapter_waste" / "0_extend_grid"

GRID_DIR = OUTPUT_DIR / "grid"
VALIDATION_DIR = OUTPUT_DIR / "validation"
MITIGATION_DIR = OUTPUT_DIR / "mitigation"

# Prefer Mollweide-extended constituency grid when available (0_extend_grid/).
# Falls back to Angela-only Step 1 clip. Existing Angela cell_id values are preserved.
_EXTENDED_GRID = EXTEND_DIR / "Nairobi_grid_100m_extended_32737.gpkg"
_ANGELA_GRID = INPUT_DIR / "Nairobi_grid_100m_32737.gpkg"
GRID_GPKG = _EXTENDED_GRID if _EXTENDED_GRID.exists() else _ANGELA_GRID

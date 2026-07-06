"""Shared output paths for Step 5 (3_100m) grid, validation, and mitigation tables."""

from pathlib import Path

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"

GRID_DIR = OUTPUT_DIR / "grid"
VALIDATION_DIR = OUTPUT_DIR / "validation"
MITIGATION_DIR = OUTPUT_DIR / "mitigation"

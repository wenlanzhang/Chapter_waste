"""Shared paths for Step 7 — independent GSVI held-out validation."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("PHD_DATA_ROOT", "/Users/wenlanzhang/Downloads/PhD_UCL/Data"))

IMG_ROOT = DATA_ROOT / "Waste" / "img"
TRAIN_ROOT = IMG_ROOT / "Train0315_695"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "7_heldout_validation"
HELDOUT_IMG_ROOT = IMG_ROOT / "7_heldout_validation"
FIG_DIR = REPO_ROOT / "Figure" / "7_heldout_validation"
VALIDATION_DIR = OUTPUT_DIR / "Validation"
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"

# Step 6 training sensitivity (inputs for design / scenario labels)
STEP6_DIR = DATA_ROOT / "Chapter_waste" / "6_sensitivity_training"
TRAINING_CSV_STEP6 = STEP6_DIR / "Train0315_695_training.csv"
TRAINING_CSV = OUTPUT_DIR / "Train0315_695_training.csv"
SCENARIO_SUMMARY_CSV = STEP6_DIR / "scenarios" / "scenario_summary.csv"

# Frozen previous dump (fallback for Validation CSVs already computed)
ARCHIVE_OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "6_sensitivity_archive"
ARCHIVE_VALIDATION_DIR = ARCHIVE_OUTPUT_DIR / "Validation"
ARCHIVE_SENS_IMG_ROOT = IMG_ROOT / "sensitivity_archive"

SPLIT_FILE = TRAIN_ROOT / "dataSet" / "trainval.txt"
IMAGES_DIR = TRAIN_ROOT / "images"
LABELS_DIR = TRAIN_ROOT / "labels"
BASIC_CSVS = [IMG_ROOT / f"{s}_basic.csv" for s in ("Google", "Faith", "ZWL")]

# Canonical held-out set (manual QA; 180 images with YOLO labels)
HELDOUT_TAG = "20260807_heldout_GSVI_p100_label"
HELDOUT_IMAGES_CSV = OUTPUT_DIR / "heldout_GSVI_p100_test.csv"
HELDOUT_UNITS_CSV = OUTPUT_DIR / "heldout_GSVI_p100_units.csv"
HELDOUT_IMG_DIR = HELDOUT_IMG_ROOT / HELDOUT_TAG


def resolve_training_csv() -> Path:
    if TRAINING_CSV.exists():
        return TRAINING_CSV
    if TRAINING_CSV_STEP6.exists():
        return TRAINING_CSV_STEP6
    raise FileNotFoundError(
        f"Missing training CSV. Tried {TRAINING_CSV} and {TRAINING_CSV_STEP6}"
    )


def resolve_validation_file(*names: str) -> Path:
    """Prefer Step 7 Validation/, then archive Validation/."""
    for name in names:
        for root in (VALIDATION_DIR, ARCHIVE_VALIDATION_DIR):
            path = root / name
            if path.exists():
                return path
            alt = root / "del" / name
            if alt.exists():
                return alt
    tried = ", ".join(names)
    raise FileNotFoundError(
        f"Missing validation file among [{tried}] in {VALIDATION_DIR} or {ARCHIVE_VALIDATION_DIR}"
    )

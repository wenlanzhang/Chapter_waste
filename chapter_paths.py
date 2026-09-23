"""Shared data roots for Steps 0–7 (+ optional SE). Override with PHD_DATA_ROOT / USE_EXTENDED_GRID.

CLI scripts should put the repo root on ``sys.path`` before importing this module:

    from pathlib import Path
    import sys
    _REPO = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PHD_DATA_ROOT = "/Users/wenlanzhang/Downloads/PhD_UCL/Data"

REPO_ROOT = Path(__file__).resolve().parent


def phd_data_root() -> Path:
    return Path(os.environ.get("PHD_DATA_ROOT", DEFAULT_PHD_DATA_ROOT))


def chapter_data_root() -> Path:
    return phd_data_root() / "Chapter_waste"


def waste_raw_dir() -> Path:
    return phd_data_root() / "Waste"


def prep_dir() -> Path:
    return chapter_data_root() / "1prepare_chapter_data"


def coverage_dir() -> Path:
    return chapter_data_root() / "2coverage_analysis"


def grid100_dir() -> Path:
    """Step 4: the 100 m visible-waste indicator (observed, interpolated, validated)."""
    return chapter_data_root() / "4_100m"


def waste_id_dir() -> Path:
    """Step 3: waste identification (YOLO + VLM) on the independent held-out set."""
    return chapter_data_root() / "3_waste_identification"


def extend_dir() -> Path:
    return chapter_data_root() / "0_extend_grid"


def figure_dir() -> Path:
    """Repo-side figure root (tracked in git, unlike the data dirs)."""
    return REPO_ROOT / "Figure"


def compare_dir() -> Path:
    return chapter_data_root() / "4_compare"


def pattern_dir() -> Path:
    return chapter_data_root() / "5_spatial_pattern"


def training_dir() -> Path:
    return chapter_data_root() / "6_sensitivity_training"


def heldout_dir() -> Path:
    return chapter_data_root() / "7_heldout_validation"


def optional_se_dir() -> Path:
    return chapter_data_root() / "99_optional_SE_analysis"


def extended_grid_gpkg() -> Path:
    return extend_dir() / "Nairobi_grid_100m_extended_32737.gpkg"


def angela_grid_gpkg() -> Path:
    return prep_dir() / "Nairobi_grid_100m_32737.gpkg"


def active_grid_gpkg() -> Path:
    """Step 3 grid: Mollweide-extended when present, else Angela clip.

    ``USE_EXTENDED_GRID`` unset preserves the exists() fallback used before
    Snakemake. ``0`` / ``false`` / ``no`` forces the Angela-only clip.
    """
    extended = extended_grid_gpkg()
    raw = os.environ.get("USE_EXTENDED_GRID")
    if raw is None:
        return extended if extended.exists() else angela_grid_gpkg()
    use = raw.strip().lower() not in {"0", "false", "no"}
    return extended if use else angela_grid_gpkg()

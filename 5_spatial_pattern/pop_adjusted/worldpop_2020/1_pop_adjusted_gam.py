#!/usr/bin/env python3
"""Sensitivity: same pop-adjusted GAMs using WorldPop unconstrained Kenya 2020.

Thin wrapper around the parent 1_pop_adjusted_gam.py with:
  raster : ken_ppp_2020.tif (unconstrained people/pixel)
  outputs: Data/.../pop_adjusted/worldpop_2020/
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
PARENT_SCRIPT = PARENT_DIR / "1_pop_adjusted_gam.py"

# Data root mirrors the chapter layout used by panoid_locations.PATTERN_DIR
DATA_OUT = (
    Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste")
    / "5_spatial_pattern"
    / "pop_adjusted"
    / "worldpop_2020"
)
POP_RASTER = DATA_OUT / "ken_ppp_2020.tif"
# Fallback if symlink not created yet
POP_RASTER_FALLBACK = Path(
    "/Users/wenlanzhang/Downloads/PhD_UCL/Data/RS/Pop_density/"
    "UnconstraintIndividualCountries/ken_ppp_2020.tif"
)


def main() -> None:
    raster = POP_RASTER if POP_RASTER.exists() else POP_RASTER_FALLBACK
    if not raster.exists():
        raise FileNotFoundError(
            f"Missing 2020 WorldPop raster. Expected {POP_RASTER} "
            f"or {POP_RASTER_FALLBACK}"
        )
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    # Forward extra CLI flags (e.g. --residuals-only) to the parent script.
    extra = [a for a in sys.argv[1:] if a]
    argv = [
        str(PARENT_SCRIPT),
        "--pop-raster",
        str(raster),
        "--output-dir",
        str(DATA_OUT),
        "--pop-label",
        "static WorldPop unconstrained Kenya 2020 (ken_ppp_2020, people/pixel)",
        "--pop-short",
        "WorldPop unconstrained KE 2020 (static)",
        "--thesis-name",
        "pop_adjusted_gam_worldpop_2020.csv",
        *extra,
    ]
    sys.argv = argv
    runpy.run_path(str(PARENT_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()

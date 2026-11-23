#!/usr/bin/env python3
"""Sensitivity: same pop-adjusted GAMs using WorldPop constrained Kenya 2024.

Not the manuscript sample. The parent 1_pop_adjusted_gam.py defaults to
WorldPop unconstrained 2020 (pop_adjusted/worldpop_2020/). This wrapper reruns
it with:
  raster : ken_pop_2024_CN_100m_R2025A_v1.tif (constrained, 100 m)
  outputs: Data/.../pop_adjusted/worldpop_2024_constrained/

The constrained layer has no value outside mapped built-up areas, so the sample
is smaller (about 74,900 panoramas) and the population term differs; the
distance effect is stronger (ΔAIC about 850 vs 317).
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import pattern_dir  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SCRIPT = SCRIPT_DIR.parent / "1_pop_adjusted_gam.py"

POP_ADJ_ROOT = pattern_dir() / "Signed_distance" / "pop_adjusted"
DATA_OUT = POP_ADJ_ROOT / "worldpop_2024_constrained"
POP_RASTER = POP_ADJ_ROOT / "ken_pop_2024_CN_100m_R2025A_v1.tif"


def main() -> None:
    if not POP_RASTER.exists():
        raise FileNotFoundError(f"Missing 2024 constrained WorldPop raster: {POP_RASTER}")
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    # Forward extra CLI flags (e.g. --residuals-only) to the parent script.
    extra = [a for a in sys.argv[1:] if a]
    sys.argv = [
        str(PARENT_SCRIPT),
        "--pop-raster", str(POP_RASTER),
        "--output-dir", str(DATA_OUT),
        "--pop-label", "static WorldPop Constrained Kenya 2024 (100 m CN)",
        "--pop-short", "WorldPop Constrained KE 2024, 100 m (static)",
        "--thesis-name", "pop_adjusted_gam_worldpop_2024_constrained.csv",
        *extra,
    ]
    runpy.run_path(str(PARENT_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()

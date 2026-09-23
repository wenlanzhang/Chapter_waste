#!/usr/bin/env python3
"""
Indicator provenance on the Mollweide-extended 100 m grid (standalone).

Runs once per analysis arm (GSVI only / GSVI + self-collected) and writes
``Nairobi_indicator_provenance_{cells,summary}_extended_{arm}.csv``.
"""

from __future__ import annotations

from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import extend_dir  # noqa: E402
from lib.arms import ARMS, Arm  # noqa: E402
from lib.ideamaps import (  # noqa: E402
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)
from lib.provenance import DEFINITIONS, PROVENANCE_ORDER, assign_provenance  # noqa: E402

EXT_DIR = extend_dir()

GRID_GPKG = EXT_DIR / "Nairobi_grid_100m_extended_32737.gpkg"


def cells_csv(arm: Arm) -> Path:
    return EXT_DIR / f"Nairobi_indicator_provenance_cells_extended_{arm.key}.csv"


def summary_csv(arm: Arm) -> Path:
    return EXT_DIR / f"Nairobi_indicator_provenance_summary_extended_{arm.key}.csv"


def build_summary(cells: gpd.GeoDataFrame) -> pd.DataFrame:
    n_city = len(cells)
    is_ext = cells["grid_source"].astype(str).str.startswith("extension")
    rows = []
    for label in PROVENANCE_ORDER:
        sub = cells.loc[cells["indicator_provenance"] == label]
        n = len(sub)
        n_ext = int(is_ext.loc[sub.index].sum()) if n else 0
        rows.append(
            {
                "Indicator provenance": label,
                "Definition": DEFINITIONS[label],
                "Cells, n": n,
                "Share (%)": 100.0 * n / n_city if n_city else np.nan,
                "Of which extension cells, n": n_ext,
                "Cells assigned to low category, n": int((sub["result"] == 0).sum()),
            }
        )

    rows.append(
        {
            "Indicator provenance": "Total",
            "Definition": "—",
            "Cells, n": n_city,
            "Share (%)": 100.0,
            "Of which extension cells, n": int(is_ext.sum()),
            "Cells assigned to low category, n": int((cells["result"] == 0).sum()),
        }
    )
    return pd.DataFrame(rows)


def run_arm(grid: gpd.GeoDataFrame, arm: Arm, breaks) -> None:
    print(f"\n[{arm.key}] {arm.label}")
    scored = run_ideamaps_grid_pipeline(
        grid, arm.svi_image_gpkg(), arm.waste_gpkg(), jenks_breaks=breaks
    )
    scored["grid_source"] = grid["grid_source"].to_numpy()
    scored = assign_provenance(scored)

    unsupported = scored["indicator_provenance"] == PROVENANCE_ORDER[2]
    if unsupported.any() and not (scored.loc[unsupported, "result"] == 0).all():
        raise RuntimeError("Unsupported cells should all map to result=0.")

    summary = build_summary(scored)
    keep_cols = [
        "cell_id",
        "grid_source",
        "total_svi_images",
        "waste_points",
        "waste_ratio",
        "smoothed_waste_ratio",
        "final_waste_ratio",
        "final_waste_ratio_platform",
        "result",
        "indicator_provenance",
    ]
    scored[keep_cols].to_csv(cells_csv(arm), index=False)
    summary.to_csv(summary_csv(arm), index=False)

    print(summary.to_string(index=False))
    print(f"Wrote {cells_csv(arm)}")
    print(f"Wrote {summary_csv(arm)}")


def main() -> None:
    if not GRID_GPKG.exists():
        raise FileNotFoundError(
            f"Missing {GRID_GPKG}\nRun first: python 0_extend_grid/1_extend_grid.py"
        )

    print("Provenance on Mollweide-extended 100 m grid...")
    grid = gpd.read_file(GRID_GPKG)
    # Same Jenks breaks for both arms so provenance classes stay comparable
    breaks = load_gsvi_submission_jenks_breaks()
    for arm in ARMS.values():
        run_arm(grid, arm, breaks)


if __name__ == "__main__":
    main()

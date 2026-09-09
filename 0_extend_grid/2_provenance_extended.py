#!/usr/bin/env python3
"""
Indicator provenance on the Mollweide-extended 100 m grid (standalone).

Reuses 3_100m pipeline helpers without modifying that folder's outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "3_100m"))

from ideamaps_grid_pipeline import (  # noqa: E402
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)
from output_paths import INPUT_DIR  # noqa: E402

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste")
EXT_DIR = DATA_ROOT / "0_extend_grid"

GRID_GPKG = EXT_DIR / "Nairobi_grid_100m_extended_32737.gpkg"
SVI_GPKG = INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg"
WASTE_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
CELLS_CSV = EXT_DIR / "Nairobi_indicator_provenance_cells_extended.csv"
SUMMARY_CSV = EXT_DIR / "Nairobi_indicator_provenance_summary_extended.csv"

PROVENANCE_ORDER = [
    "Direct observation",
    "Interpolated support",
    "Unsupported, platform-coded low",
]

DEFINITIONS = {
    "Direct observation": "At least one GSVI image in the cell",
    "Interpolated support": (
        "No local imagery; value estimated through interpolation"
    ),
    "Unsupported, platform-coded low": (
        "Missing after interpolation; encoded as zero for IDEAMaps"
    ),
}


def assign_provenance(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = grid.copy()
    has_svi = out["total_svi_images"].fillna(0).astype(int) > 0
    filled = out["final_waste_ratio"].notna()

    provenance = np.full(len(out), PROVENANCE_ORDER[2], dtype=object)
    provenance[has_svi.to_numpy()] = PROVENANCE_ORDER[0]
    provenance[(~has_svi & filled).to_numpy()] = PROVENANCE_ORDER[1]
    out["indicator_provenance"] = provenance
    out["final_waste_ratio_platform"] = out["final_waste_ratio"].fillna(0)
    return out


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


def main() -> None:
    if not GRID_GPKG.exists():
        raise FileNotFoundError(
            f"Missing {GRID_GPKG}\nRun first: python 0_extend_grid/1_extend_grid.py"
        )

    print("Provenance on Mollweide-extended 100 m grid...")
    grid = gpd.read_file(GRID_GPKG)
    breaks = load_gsvi_submission_jenks_breaks()
    scored = run_ideamaps_grid_pipeline(
        grid, SVI_GPKG, WASTE_GPKG, jenks_breaks=breaks
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
    scored[keep_cols].to_csv(CELLS_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)

    print(summary.to_string(index=False))
    print(f"\nWrote {CELLS_CSV}")
    print(f"Wrote {SUMMARY_CSV}")


if __name__ == "__main__":
    main()

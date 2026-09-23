#!/usr/bin/env python3
"""
Indicator provenance on the Nairobi 100 m grid (GSVI arm).

Classifies every city-grid cell into:
  1. Direct observation — ≥1 GSVI image in the cell
  2. Interpolated support — no local imagery; value from spatial fill
  3. Unsupported, platform-coded low — still missing after interpolation;
     encoded as zero because IDEAMaps required a complete categorical value

Uses the same GSVI layers and IDEAMaps pipeline as mitigation validation
(Empirical Bayes + linear spatial fill + fixed submission Jenks breaks).
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

from lib.ideamaps import (  # noqa: E402
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)
from lib.provenance import DEFINITIONS, PROVENANCE_ORDER, assign_provenance  # noqa: E402
from output_paths import GRID_GPKG, INPUT_DIR, OUTPUT_DIR

VALIDATION_GRID_GPKG = INPUT_DIR / "Nairobi_validation_grid_32737.gpkg"
SVI_GPKG = INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg"
WASTE_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"

THESIS_DIR = OUTPUT_DIR / "thesis_table"
CELLS_CSV = OUTPUT_DIR / "grid" / "Nairobi_indicator_provenance_cells.csv"
SUMMARY_CSV = OUTPUT_DIR / "grid" / "Nairobi_indicator_provenance_summary.csv"
TABLE_PATH = THESIS_DIR / "table_indicator_provenance.csv"


def build_summary(
    cells: gpd.GeoDataFrame, validation_ids: set[int]
) -> pd.DataFrame:
    n_city = len(cells)
    rows = []
    for label in PROVENANCE_ORDER:
        sub = cells.loc[cells["indicator_provenance"] == label]
        n = len(sub)
        n_low = int((sub["result"] == 0).sum())
        n_val = int(sub["cell_id"].isin(validation_ids).sum())
        rows.append(
            {
                "Indicator provenance": label,
                "Definition": DEFINITIONS[label],
                "City-grid cells, n": n,
                "Share of city grid (%)": 100.0 * n / n_city if n_city else np.nan,
                "Cells assigned to low category, n": n_low,
                "Crowd-validation cells, n": n_val,
            }
        )

    total_low = int((cells["result"] == 0).sum())
    total_val = int(cells["cell_id"].isin(validation_ids).sum())
    rows.append(
        {
            "Indicator provenance": "Total",
            "Definition": "—",
            "City-grid cells, n": n_city,
            "Share of city grid (%)": 100.0,
            "Cells assigned to low category, n": total_low,
            "Crowd-validation cells, n": total_val,
        }
    )
    return pd.DataFrame(rows)


def format_thesis_table(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    out["City-grid cells, n"] = out["City-grid cells, n"].map(
        lambda n: f"{int(n):,}"
    )
    out["Share of city grid (%)"] = out["Share of city grid (%)"].map(
        lambda x: f"{x:.1f}"
    )
    out["Cells assigned to low category, n"] = out[
        "Cells assigned to low category, n"
    ].map(lambda n: f"{int(n):,}")
    out["Crowd-validation cells, n"] = out["Crowd-validation cells, n"].map(
        lambda n: f"{int(n):,}"
    )
    return out


def main() -> None:
    THESIS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "grid").mkdir(parents=True, exist_ok=True)

    print("Indicator provenance (GSVI → 100 m IDEAMaps pipeline)...")
    print(f"  Grid: {GRID_GPKG}")
    grid = gpd.read_file(GRID_GPKG)
    validation = gpd.read_file(VALIDATION_GRID_GPKG)
    validation_ids = set(validation["cell_id"].astype(int))

    # Preserve optional Mollweide-extension flag from 0_extend_grid
    grid_source = (
        grid["grid_source"].to_numpy()
        if "grid_source" in grid.columns
        else None
    )

    breaks = load_gsvi_submission_jenks_breaks()
    scored = run_ideamaps_grid_pipeline(
        grid,
        SVI_GPKG,
        WASTE_GPKG,
        jenks_breaks=breaks,
    )
    if grid_source is not None:
        scored["grid_source"] = grid_source
    scored = assign_provenance(scored)

    # Sanity: unsupported cells should be coded low (0) after fillna
    unsupported = scored["indicator_provenance"] == PROVENANCE_ORDER[2]
    if unsupported.any() and not (scored.loc[unsupported, "result"] == 0).all():
        raise RuntimeError(
            "Unsupported cells should all map to result=0 after platform encoding."
        )

    summary = build_summary(scored, validation_ids)
    thesis = format_thesis_table(summary)

    keep_cols = [
        "cell_id",
        "total_svi_images",
        "waste_points",
        "waste_ratio",
        "smoothed_waste_ratio",
        "final_waste_ratio",
        "final_waste_ratio_platform",
        "result",
        "indicator_provenance",
    ]
    if "grid_source" in scored.columns:
        keep_cols.insert(1, "grid_source")
    scored[keep_cols].to_csv(CELLS_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    thesis.to_csv(TABLE_PATH, index=False)

    print(thesis.to_string(index=False))
    print(f"\nWrote {CELLS_CSV}")
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {TABLE_PATH}")
    print(f"  City-grid cells: {len(scored):,}")
    print(f"  Validation cells matched: {len(validation_ids):,}")
    if "grid_source" in scored.columns:
        print("  Grid source counts:")
        print(scored["grid_source"].value_counts().to_string())


if __name__ == "__main__":
    main()

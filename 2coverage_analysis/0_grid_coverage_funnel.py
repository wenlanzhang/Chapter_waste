#!/usr/bin/env python3
"""Step 2, block 0 — the whole coverage cascade on one frame.

Blocks 2a-2e each measure one narrowing of the observation chain, on whichever
unit suits it: 100 m cells for the road frame, road metres for SVI support,
sampling points for waste. This script puts the whole chain back on a single
unit — the 100 m cell — so the cascade can be read end to end:

    city  ->  road-accessible  ->  GSVI-observed  ->  waste-positive

and reports it two ways. Counts give the funnel. The nested matrix gives every
conditional share: for each pair of contexts, what fraction of the column
context also satisfies the row context. The diagonal is 100% by construction;
the interesting cells are off it.

The contexts are *almost* nested but not exactly, and the matrix is the place
that shows it. Three GSVI-observed cells are road-excluded, so "road given
GSVI" is 99.99% rather than 100% — Street View occurs on mapped roads, and the
handful of exceptions are the check on that assumption rather than a problem.

Definitions follow the rest of Step 2, not the archived version of this figure:
  road-accessible   Step 2a's 50 m rule (intersects a road, or within 50 m),
                    not a minimum road length per cell
  GSVI-observed     Step 2e's has_gsvi, which snaps points in grid slivers to
                    the nearest cell within 100 m (see the README on the two
                    cell-assignment rules; lib/ideamaps.py does not snap)
  waste-positive    >=1 waste-positive panorama in the cell, from Step 2c

Inputs (2coverage_analysis/):
  5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg   per-cell road + GSVI status (2e)
  3_Nairobi_sviwaste_points_gsvi_32737.gpkg    waste-positive panoramas (2c)

Outputs (Data/Chapter_waste/2coverage_analysis/):
  0_Nairobi_grid_coverage_funnel.csv       one row per context, with counts
  0_Nairobi_grid_coverage_matrix.csv       the nested conditional shares, long
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import coverage_dir  # noqa: E402
from lib.arms import ARMS  # noqa: E402

OUTPUT_DIR = coverage_dir()
GRID_GPKG = OUTPUT_DIR / ARMS["gsvi"].filename("5_Nairobi_gridsvi_grid100m")
SVIWASTE_GPKG = OUTPUT_DIR / ARMS["gsvi"].filename("3_Nairobi_sviwaste_points")

FUNNEL_CSV = OUTPUT_DIR / "0_Nairobi_grid_coverage_funnel.csv"
MATRIX_CSV = OUTPUT_DIR / "0_Nairobi_grid_coverage_matrix.csv"

CONTEXTS = [
    ("city", "City"),
    ("road", "Road-accessible"),
    ("svi", "GSVI-observed"),
    ("waste", "Waste-positive"),
]


def load_cells() -> gpd.GeoDataFrame:
    for path in (GRID_GPKG, SVIWASTE_GPKG):
        if not path.exists():
            raise SystemExit(
                f"Missing {path.name} — run 2coverage_analysis/5_gridsvi.py "
                "and 3sviwaste.py first."
            )
    cells = gpd.read_file(GRID_GPKG)
    waste = gpd.read_file(SVIWASTE_GPKG)
    waste = waste.loc[waste["waste_positive"] == 1]

    # Same within-join the rest of Step 2 uses for point-in-cell counts.
    joined = gpd.sjoin(
        waste[["geometry"]], cells[["cell_id", "geometry"]], how="inner", predicate="within"
    )
    counts = joined["cell_id"].value_counts()
    cells["n_waste_positive"] = cells["cell_id"].map(counts).fillna(0).astype(int)

    cells["ctx_city"] = 1
    cells["ctx_road"] = cells["road_accessible"].astype(int)
    cells["ctx_svi"] = cells["has_gsvi"].astype(int)
    cells["ctx_waste"] = (cells["n_waste_positive"] > 0).astype(int)
    print(f"{len(cells):,} cells | {len(waste):,} waste-positive panoramas")
    return cells


def build_funnel(cells: pd.DataFrame) -> pd.DataFrame:
    n = len(cells)
    rows = []
    prev = None
    for key, label in CONTEXTS:
        count = int(cells[f"ctx_{key}"].sum())
        rows.append(
            {
                "context": key,
                "label": label,
                "n_cells": count,
                "pct_of_city": round(100 * count / n, 2),
                "pct_of_previous": round(100 * count / prev, 2) if prev else 100.0,
            }
        )
        prev = count
    out = pd.DataFrame(rows)
    out.to_csv(FUNNEL_CSV, index=False)
    print(f"\n{out.to_string(index=False)}")
    print(f"Wrote {FUNNEL_CSV}")
    return out


def build_matrix(cells: pd.DataFrame) -> pd.DataFrame:
    """Share of each column context that also satisfies the row context."""
    rows = []
    for r_key, r_label in CONTEXTS:
        for c_key, c_label in CONTEXTS:
            denom = int(cells[f"ctx_{c_key}"].sum())
            both = int((cells[f"ctx_{r_key}"] & cells[f"ctx_{c_key}"]).sum())
            rows.append(
                {
                    "row_context": r_key,
                    "row_label": r_label,
                    "col_context": c_key,
                    "col_label": c_label,
                    "n_both": both,
                    "n_col": denom,
                    "pct": round(100 * both / denom, 2) if denom else float("nan"),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(MATRIX_CSV, index=False)

    wide = out.pivot(index="row_label", columns="col_label", values="pct")
    order = [label for _, label in CONTEXTS]
    print(f"\nNested coverage matrix (% of column context that is also row context):")
    print(wide.reindex(index=order, columns=order).to_string())
    print(f"Wrote {MATRIX_CSV}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cells = load_cells()
    flat = cells.drop(columns="geometry")
    build_funnel(flat)
    matrix = build_matrix(flat)

    # The one place the chain is not perfectly nested, called out explicitly.
    road_given_svi = matrix[
        (matrix["row_context"] == "road") & (matrix["col_context"] == "svi")
    ].iloc[0]
    n_off = int(road_given_svi["n_col"] - road_given_svi["n_both"])
    print(f"\nGSVI-observed cells that are road-excluded: {n_off:,} "
          f"({100 - road_given_svi['pct']:.2f}% of observed cells)")


if __name__ == "__main__":
    main()

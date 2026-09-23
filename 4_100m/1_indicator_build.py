#!/usr/bin/env python3
"""Step 4a — build the 100 m visible-waste indicator and separate evidence from estimate.

Runs the IDEAMaps submission pipeline (lib/ideamaps.py) on the active 100 m grid:

  1. count GSVI images and waste-positive detections per cell
  2. raw waste/image ratio, then an Empirical Bayes shrunk ratio
  3. linear spatial interpolation of that ratio over cell centroids (scipy griddata)
  4. Jenks k=3 classes using the fixed IDEAMaps submission break points

Step 3 differs from the others in kind: 1-2 are measurement, 3 is estimation.
This script keeps the two apart and quantifies the second, labelling every cell

  Direct observation              >=1 GSVI image in the cell
  Interpolated support            no imagery; ratio estimated by the spatial fill
  Unsupported, platform-coded low outside the interpolation hull, so NaN -> 0

and measuring how far each estimated cell lies from the nearest observed one.

Inputs:
  chapter_paths.active_grid_gpkg()                      the 100 m grid
  1prepare_chapter_data/Nairobi_SVI_image_gsvi_32737.gpkg   GSVI images (Step 1)
  1prepare_chapter_data/Nairobi_Waste_point_gsvi_32737.gpkg waste-positive detections (Step 3)

Outputs (Data/Chapter_waste/4_100m/):
  1_Nairobi_indicator_grid100m_gsvi_32737.gpkg  per-cell ratios, class, provenance, distance
  thesis_table/table_3_indicator_summary.csv    headline Component | Metric | Value table (chapter)
  1_indicator_direct.csv / _detail.csv          what the directly observed indicator looks like
  2_indicator_interpolation.csv                 provenance counts and interpolation range
  2_indicator_support_distance.csv              cost of imposing a maximum support distance
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, prep_dir, grid100_dir  # noqa: E402
from lib.ideamaps import (  # noqa: E402
    METHOD_LABEL,
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)
from lib.provenance import PROVENANCE_ORDER, assign_provenance  # noqa: E402

OUTPUT_DIR = grid100_dir()
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"

SVI_GPKG = prep_dir() / "Nairobi_SVI_image_gsvi_32737.gpkg"
WASTE_GPKG = prep_dir() / "Nairobi_Waste_point_gsvi_32737.gpkg"
GRID_OUT = OUTPUT_DIR / "1_Nairobi_indicator_grid100m_gsvi_32737.gpkg"

DIRECT, INTERPOLATED, UNSUPPORTED = PROVENANCE_ORDER

# Support distances to report. Nothing is capped by default — this is a
# sensitivity table showing how much of the surface each cap would give up.
SUPPORT_CAPS_M = (100, 200, 300, 500, 1000, 2000)

CLASS_LABELS = {0: "Low", 1: "Medium", 2: "High"}


def write_thesis(df: pd.DataFrame, name: str) -> Path:
    """A table that goes in the chapter."""
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    df.to_csv(path, index=False)
    print(f"Wrote {path}")
    return path


def write_support(df: pd.DataFrame, name: str) -> Path:
    """Working output: numbers behind a figure or a robustness check, not a chapter table."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    df.to_csv(path, index=False)
    print(f"Wrote {path}")
    return path


def fmt_int(x: float) -> str:
    return f"{int(round(x)):,}"


def fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


def distance_to_direct(grid: gpd.GeoDataFrame) -> pd.Series:
    """Metres from each cell centroid to the nearest directly observed cell centroid."""
    centroids = np.array([(p.x, p.y) for p in grid.geometry.centroid])
    is_direct = (grid["indicator_provenance"] == DIRECT).to_numpy()
    if not is_direct.any():
        return pd.Series(np.nan, index=grid.index)
    tree = cKDTree(centroids[is_direct])
    dist, _ = tree.query(centroids, k=1)
    return pd.Series(dist, index=grid.index)


def build_indicator(grid_path: Path) -> gpd.GeoDataFrame:
    grid = gpd.read_file(grid_path)
    print(f"Grid: {grid_path.name} ({len(grid):,} cells, {grid.crs})")
    carry = grid["grid_source"].to_numpy() if "grid_source" in grid.columns else None

    scored = run_ideamaps_grid_pipeline(
        grid, SVI_GPKG, WASTE_GPKG, jenks_breaks=load_gsvi_submission_jenks_breaks()
    )
    if carry is not None:
        scored["grid_source"] = carry
    scored = assign_provenance(scored)
    scored["dist_to_direct_m"] = distance_to_direct(scored)

    # The pipeline's own invariant: anything still missing after the spatial fill
    # is what .fillna(0) turns into the lowest class.
    unsupported = scored["indicator_provenance"] == UNSUPPORTED
    if unsupported.any() and not (scored.loc[unsupported, "result"] == 0).all():
        raise RuntimeError("Unsupported cells should all be class 0 after platform encoding.")
    return scored


# ---------------------------------------------------------------------------
# (1) What the directly observed indicator looks like
# ---------------------------------------------------------------------------
def table_direct(scored: gpd.GeoDataFrame) -> pd.DataFrame:
    n_cells = len(scored)
    obs = scored[scored["total_svi_images"] > 0]
    n_obs = len(obs)
    waste_cells = obs[obs["waste_points"] > 0]
    ratio = obs["waste_ratio"].dropna()
    nz = ratio[ratio > 0]

    rows = [
        ("Grid", "100 m cells in the study grid", fmt_int(n_cells)),
        ("Direct evidence", "Cells containing >=1 GSVI image", f"{fmt_int(n_obs)} ({fmt_pct(100 * n_obs / n_cells)})"),
        ("Direct evidence", "GSVI images contributing", fmt_int(obs["total_svi_images"].sum())),
        ("Direct evidence", "Images per observed cell, median (IQR)",
         f"{obs['total_svi_images'].median():.0f} "
         f"({obs['total_svi_images'].quantile(0.25):.0f}-{obs['total_svi_images'].quantile(0.75):.0f})"),
        ("Waste occurrence", "Observed cells with >=1 waste detection",
         f"{fmt_int(len(waste_cells))} ({fmt_pct(100 * len(waste_cells) / n_obs)} of observed)"),
        ("Waste occurrence", "Waste detections contributing", fmt_int(obs["waste_points"].sum())),
        # The measure is zero-inflated: most observed cells see no waste at all,
        # so quantiles over all observed cells are 0 and say nothing. Describe the
        # zero mass first, then the distribution among cells that do see waste.
        ("Cell-level measure", "Observed cells with ratio = 0",
         f"{fmt_int((ratio == 0).sum())} ({fmt_pct(100 * (ratio == 0).mean())} of observed)"),
        ("Cell-level measure", "Raw waste/image ratio, mean over observed cells", f"{ratio.mean():.4f}"),
        ("Cell-level measure", "Raw waste/image ratio, 95th / 99th pct",
         f"{ratio.quantile(0.95):.4f} / {ratio.quantile(0.99):.4f}"),
        ("Cell-level measure", "Among waste-positive cells: ratio median (IQR)",
         f"{nz.median():.3f} ({nz.quantile(0.25):.3f}-{nz.quantile(0.75):.3f})"),
        ("Cell-level measure", "Among waste-positive cells: ratio max", f"{nz.max():.3f}"),
        ("Cell-level measure", "Waste detections per waste-positive cell, median",
         f"{waste_cells['waste_points'].median():.0f} (max {waste_cells['waste_points'].max():.0f})"),
    ]
    display = pd.DataFrame(rows, columns=["Component", "Metric", "Value"])
    print("\n(1) Directly observed 100 m indicator:")
    print(display.to_string(index=False))
    write_support(display, "1_indicator_direct.csv")

    detail = pd.DataFrame(
        [
            {
                "n_cells_grid": n_cells,
                "n_cells_observed": n_obs,
                "pct_cells_observed": round(100 * n_obs / n_cells, 2),
                "n_images": int(obs["total_svi_images"].sum()),
                "images_per_cell_median": float(obs["total_svi_images"].median()),
                "images_per_cell_mean": float(obs["total_svi_images"].mean()),
                "images_per_cell_max": int(obs["total_svi_images"].max()),
                "n_cells_waste_positive": len(waste_cells),
                "pct_observed_waste_positive": round(100 * len(waste_cells) / n_obs, 2),
                "n_waste_detections": int(obs["waste_points"].sum()),
                "ratio_mean": float(ratio.mean()),
                "ratio_median": float(ratio.median()),
                "ratio_p95": float(ratio.quantile(0.95)),
                "ratio_p99": float(ratio.quantile(0.99)),
                "ratio_median_waste_positive_cells": float(nz.median()),
                "ratio_max": float(ratio.max()),
                "pct_observed_ratio_zero": round(100 * float((ratio == 0).mean()), 2),
                "method": METHOD_LABEL,
            }
        ]
    )
    write_support(detail, "1_indicator_direct_detail.csv")
    return display


# ---------------------------------------------------------------------------
# (2) What the interpolation adds, and over what distance
# ---------------------------------------------------------------------------
def table_interpolation(scored: gpd.GeoDataFrame) -> pd.DataFrame:
    n_cells = len(scored)
    rows = []
    for label in PROVENANCE_ORDER:
        sub = scored[scored["indicator_provenance"] == label]
        dist = sub["dist_to_direct_m"]
        rows.append(
            {
                "Provenance": label,
                "Cells, n": fmt_int(len(sub)),
                "Share of grid": fmt_pct(100 * len(sub) / n_cells),
                "Distance to nearest observed cell, median (m)": "0" if label == DIRECT else f"{dist.median():,.0f}",
                "90th pct (m)": "0" if label == DIRECT else f"{dist.quantile(0.90):,.0f}",
                "Max (m)": "0" if label == DIRECT else f"{dist.max():,.0f}",
                "Cells in lowest class, n": fmt_int((sub["result"] == 0).sum()),
            }
        )
    display = pd.DataFrame(rows)
    print("\n(2) Indicator provenance and interpolation range:")
    print(display.to_string(index=False))
    write_support(display, "2_indicator_interpolation.csv")

    # Sensitivity: what a maximum support distance would cost
    n_direct = int((scored["indicator_provenance"] == DIRECT).sum())
    interp = scored["indicator_provenance"] == INTERPOLATED
    cap_rows = []
    for cap in SUPPORT_CAPS_M:
        kept = int((interp & (scored["dist_to_direct_m"] <= cap)).sum())
        represented = n_direct + kept
        cap_rows.append(
            {
                "Maximum support distance": f"{cap:,} m",
                "Interpolated cells retained, n": fmt_int(kept),
                "Interpolated cells dropped, n": fmt_int(int(interp.sum()) - kept),
                "Cells represented, n": fmt_int(represented),
                "Share of grid represented": fmt_pct(100 * represented / n_cells),
                "Direct share of represented": fmt_pct(100 * n_direct / represented),
            }
        )
    cap_rows.append(
        {
            "Maximum support distance": "None (as published)",
            "Interpolated cells retained, n": fmt_int(int(interp.sum())),
            "Interpolated cells dropped, n": "0",
            "Cells represented, n": fmt_int(n_direct + int(interp.sum())),
            "Share of grid represented": fmt_pct(100 * (n_direct + int(interp.sum())) / n_cells),
            "Direct share of represented": fmt_pct(100 * n_direct / (n_direct + int(interp.sum()))),
        }
    )
    caps = pd.DataFrame(cap_rows)
    print("\n    Support-distance sensitivity (nothing is capped by default):")
    print(caps.to_string(index=False))
    write_support(caps, "2_indicator_support_distance.csv")
    return display


# ---------------------------------------------------------------------------
# (3) Headline summary
# ---------------------------------------------------------------------------
def table_summary(scored: gpd.GeoDataFrame) -> pd.DataFrame:
    n_cells = len(scored)
    obs = scored[scored["total_svi_images"] > 0]
    n_direct = len(obs)
    n_interp = int((scored["indicator_provenance"] == INTERPOLATED).sum())
    n_unsup = int((scored["indicator_provenance"] == UNSUPPORTED).sum())
    n_waste = int((obs["waste_points"] > 0).sum())
    represented = n_direct + n_interp
    interp_dist = scored.loc[scored["indicator_provenance"] == INTERPOLATED, "dist_to_direct_m"]

    rows = [
        ("Direct evidence", "100 m cells with an observed indicator value",
         f"{fmt_int(n_direct)} ({fmt_pct(100 * n_direct / n_cells)} of grid)"),
        ("Waste occurrence", "Observed cells with >=1 waste-positive detection",
         f"{fmt_int(n_waste)} ({fmt_pct(100 * n_waste / n_direct)} of observed)"),
        ("Interpolation", "Cells receiving an estimated value",
         f"{fmt_int(n_interp)} ({fmt_pct(100 * n_interp / n_cells)} of grid)"),
        ("Interpolation", "Estimated cell distance to nearest evidence, median",
         f"{interp_dist.median():,.0f} m (90th pct {interp_dist.quantile(0.90):,.0f} m)"),
        ("Final indicator", "Cells represented (observed + estimated)",
         f"{fmt_int(represented)} ({fmt_pct(100 * represented / n_cells)} of grid)"),
        ("Final indicator", "Share of represented cells resting on direct evidence",
         fmt_pct(100 * n_direct / represented)),
        ("Final indicator", "Cells beyond the interpolation hull, coded as lowest class",
         f"{fmt_int(n_unsup)} ({fmt_pct(100 * n_unsup / n_cells)} of grid)"),
    ]
    for cls in sorted(CLASS_LABELS):
        n = int((scored["result"] == cls).sum())
        rows.append(("Published classes", f"Cells classified {CLASS_LABELS[cls]}",
                     f"{fmt_int(n)} ({fmt_pct(100 * n / n_cells)})"))

    display = pd.DataFrame(rows, columns=["Component", "Metric", "Value"])
    print("\n(3) Indicator summary:")
    print(display.to_string(index=False))
    write_thesis(display, "table_3_indicator_summary.csv")
    return display


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=None, help="Override the 100 m grid GeoPackage")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Method: {METHOD_LABEL}")

    scored = build_indicator(args.grid or active_grid_gpkg())

    keep = [
        "cell_id",
        "total_svi_images",
        "waste_points",
        "waste_ratio",
        "smoothed_waste_ratio",
        "final_waste_ratio",
        "final_waste_ratio_platform",
        "result",
        "indicator_provenance",
        "dist_to_direct_m",
        "geometry",
    ]
    if "grid_source" in scored.columns:
        keep.insert(1, "grid_source")
    scored[keep].to_file(GRID_OUT, driver="GPKG")
    print(f"\nWrote {GRID_OUT}")

    table_direct(scored)
    table_interpolation(scored)
    table_summary(scored)


if __name__ == "__main__":
    main()

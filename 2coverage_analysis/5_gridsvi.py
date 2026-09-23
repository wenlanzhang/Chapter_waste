#!/usr/bin/env python3
"""GSVI -> analytical grid: direct observation status of every 100 m cell.

Returns from the road frame to the 100 m grid. For each cell of the active
grid (chapter_paths.active_grid_gpkg()):

  n_images              GSVI images (directional views) inside the cell
  n_panoramas           GSVI panoramas (sampling points) inside the cell
  has_gsvi              1 if the cell contains >=1 image
  dist_nearest_obs_m    cell centroid -> nearest panorama; 0 for observed cells
  road_accessible, road_length_m, road_density_km_per_km2, n_road_segments,
  dist_road_edge_m      carried over from Step 2a
  road_m_covered, road_m_uncovered, svi_road_coverage_ratio
                        carried over from Step 2b's per-cell grid

The result is the cell-level analysis table used by 5plot_gridsvi_analysis.R.

Both stages share the same denominator (all urban 100 m cells), so the
conditional coverage P(GSVI | road-accessible) = N(road-accessible AND
has_gsvi) / N(road-accessible) and the 2 x 2 road_accessible x has_gsvi table
are computed here. Cell D of that table (GSVI-observed but road-excluded)
should be small: Street View should occur near mapped roads.

Also assembles the coverage headline table (urban -> road -> GSVI -> grid) from
the Step 2a / 2b summaries and this script's summary.

Outputs (Data/Chapter_waste/2coverage_analysis/):
  5_Nairobi_gridsvi_grid100m_{arm}_32737.gpkg          per-cell observation status
  5_Nairobi_gridsvi_summary_{arm}.csv                  citywide summary
  5_Nairobi_gridsvi_road_crosstab_{arm}.csv            road_accessible x has_gsvi (with margins)
  thesis_table/table_5_gridsvi.csv                   Variable | Value | Unit
  thesis_table/table_0_coverage_headline.csv           Stage | Metric | Denominator | Value
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, coverage_dir  # noqa: E402
from lib.arms import ARMS, Arm, add_arm_argument, select_arms  # noqa: E402
from lib.road_coverage import buffer_file_tag  # noqa: E402
from lib.thesis_tables import (  # noqa: E402
    build_coverage_headline_table,
    build_gridsvi_table,
    save_thesis_table,
)

OUTPUT_DIR = coverage_dir()

DEFAULT_FAR_M = 500.0
DEFAULT_ROAD_BUFFER_M = 50.0
DEFAULT_SVI_BUFFER_M = 50.0

CELL_COLUMNS = [
    "cell_id",
    "grid_source",
    "n_images",
    "n_panoramas",
    "has_gsvi",
    "dist_nearest_obs_m",
    "road_accessible",
    "road_length_m",
    "road_density_km_per_km2",
    "n_road_segments",
    "dist_road_edge_m",
    "road_m_covered",
    "road_m_uncovered",
    "svi_road_coverage_ratio",
]
CITYROAD_GPKG = OUTPUT_DIR / "1_Nairobi_cityroad_grid100m_32737.gpkg"
CITYROAD_COLUMNS = ["road_accessible", "road_length_m", "road_density_km_per_km2", "n_road_segments", "dist_road_edge_m"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GSVI observation status on the 100 m grid.")
    parser.add_argument(
        "--far-m",
        type=float,
        default=DEFAULT_FAR_M,
        help="Threshold for 'far from any observation' share (default: 500)",
    )
    parser.add_argument(
        "--road-buffer-m",
        type=float,
        default=DEFAULT_ROAD_BUFFER_M,
        help="Which Step 2a summary feeds the headline table (default: 50)",
    )
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="Which Step 2b summary feeds the headline table (default: 50)",
    )
    add_arm_argument(parser, default="gsvi")
    return parser.parse_args()


def grid_gpkg(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("5_Nairobi_gridsvi_grid100m")


def summary_csv(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("5_Nairobi_gridsvi_summary", suffix="", ext="csv")


def crosstab_csv(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("5_Nairobi_gridsvi_road_crosstab", suffix="", ext="csv")


def _to_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


# ---------------------------------------------------------------------------
# Per-cell metrics
# ---------------------------------------------------------------------------
SNAP_MAX_M = 100.0  # points in grid slivers are assigned to the nearest cell within this distance


SNAP_COUNTS: dict[str, int] = {}


def assign_cells(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, label: str) -> pd.Series:
    """cell_id for each point: the containing cell, else the nearest cell within SNAP_MAX_M.

    The Mollweide-extended grid leaves ~0.3% of the constituency uncovered along
    the boundary; points falling in those slivers are inside the city and are
    snapped to the adjacent cell so totals reconcile with Step 1 / Step 2c.
    """
    pts = points[["geometry"]].reset_index(drop=True)
    cells = grid[["cell_id", "geometry"]]
    within = gpd.sjoin(pts, cells, how="left", predicate="within")
    within = within[~within.index.duplicated(keep="first")]
    cell_id = within["cell_id"]
    missing = cell_id.isna()
    if missing.any():
        nearest = gpd.sjoin_nearest(
            pts.loc[missing], cells, how="left", max_distance=SNAP_MAX_M, distance_col="_d"
        )
        nearest = nearest[~nearest.index.duplicated(keep="first")]
        cell_id = cell_id.copy()
        cell_id.loc[missing] = nearest["cell_id"]
        n_snapped = int(nearest["cell_id"].notna().sum())
        n_dropped = int(missing.sum()) - n_snapped
        SNAP_COUNTS[label] = n_snapped
        print(f"  {label}: {n_snapped:,} in grid slivers snapped to nearest cell"
              + (f"; {n_dropped:,} beyond {SNAP_MAX_M:.0f} m dropped" if n_dropped else ""))
    return cell_id


def count_points_in_cells(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, name: str) -> pd.Series:
    counts = assign_cells(grid, points, name).dropna().astype(int).value_counts()
    return grid["cell_id"].map(counts).fillna(0).astype(int).rename(name)


def distance_to_nearest(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.Series:
    tree = cKDTree(np.c_[points.geometry.x, points.geometry.y])
    centroids = grid.geometry.centroid
    dist, _ = tree.query(np.c_[centroids.x, centroids.y], k=1)
    return pd.Series(dist, index=grid.index, name="dist_nearest_obs_m")


ROADSVI_GRID_COLUMNS = ["road_m_covered", "road_m_uncovered", "svi_road_coverage_ratio"]


def roadsvi_grid_gpkg(arm: Arm, svi_buffer_m: float) -> Path:
    return OUTPUT_DIR / f"2_Nairobi_roadsvi_grid100m_{arm.tagged(buffer_file_tag(svi_buffer_m))}.gpkg"


def load_roadsvi_grid(arm: Arm, svi_buffer_m: float) -> pd.DataFrame:
    """Per-cell covered / uncovered road metres from Step 2b, indexed by cell_id."""
    path = roadsvi_grid_gpkg(arm, svi_buffer_m)
    if not path.exists():
        raise FileNotFoundError(f"Missing {path.name}; run 2coverage_analysis/2roadsvi.py first.")
    df = gpd.read_file(path, columns=["cell_id", *ROADSVI_GRID_COLUMNS], ignore_geometry=True)
    return df.set_index("cell_id")


def compute_cells(grid: gpd.GeoDataFrame, arm: Arm, svi_buffer_m: float) -> gpd.GeoDataFrame:
    images = _to_32737(gpd.read_file(arm.svi_image_gpkg()))
    panoramas = _to_32737(gpd.read_file(arm.svi_point_gpkg()))
    cells = grid[["cell_id", "grid_source", "geometry"]].copy()
    print(f"  {len(images):,} images | {len(panoramas):,} panoramas")
    cells["n_images"] = count_points_in_cells(grid, images, "n_images")
    cells["n_panoramas"] = count_points_in_cells(grid, panoramas, "n_panoramas")
    cells["has_gsvi"] = (cells["n_images"] > 0).astype(int)
    dist = distance_to_nearest(grid, panoramas)
    cells["dist_nearest_obs_m"] = dist.where(cells["has_gsvi"] == 0, 0.0)
    # Road frame + road metrics from Step 2a (same cells, same denominator)
    road = load_cityroad()
    for col in CITYROAD_COLUMNS:
        cells[col] = cells["cell_id"].map(road[col])
    cells["road_accessible"] = cells["road_accessible"].astype(int)
    # Step 2b covered / uncovered road metres per cell
    cov = load_roadsvi_grid(arm, svi_buffer_m)
    for col in ROADSVI_GRID_COLUMNS:
        cells[col] = cells["cell_id"].map(cov[col])
    return cells


def load_cityroad() -> pd.DataFrame:
    """Per-cell road metrics from Step 2a (1cityroad.py), indexed by cell_id."""
    if not CITYROAD_GPKG.exists():
        raise FileNotFoundError(f"Missing {CITYROAD_GPKG.name}; run 2coverage_analysis/1cityroad.py first.")
    df = gpd.read_file(CITYROAD_GPKG, columns=["cell_id", *CITYROAD_COLUMNS], ignore_geometry=True)
    return df.set_index("cell_id")


def road_gsvi_crosstab(cells: gpd.GeoDataFrame) -> pd.DataFrame:
    """2 x 2 road_accessible x has_gsvi with margins (rows: road frame, cols: GSVI)."""
    ct = pd.crosstab(
        cells["road_accessible"].map({1: "Road-accessible", 0: "Road-excluded"}),
        cells["has_gsvi"].map({1: "GSVI", 0: "No GSVI"}),
        margins=True,
        margins_name="Total",
    )
    return ct.reindex(index=["Road-accessible", "Road-excluded", "Total"], columns=["No GSVI", "GSVI", "Total"])


def compute_summary(cells: gpd.GeoDataFrame, arm: Arm, far_m: float) -> pd.DataFrame:
    n = len(cells)
    observed = cells.loc[cells["has_gsvi"] == 1]
    unobserved = cells.loc[cells["has_gsvi"] == 0]
    road = cells.loc[cells["road_accessible"] == 1]
    excluded = cells.loc[cells["road_accessible"] == 0]
    n_road_gsvi = int(road["has_gsvi"].sum())
    n_excluded_gsvi = int(excluded["has_gsvi"].sum())
    row = {
        "arm": arm.key,
        "far_m": far_m,
        "n_cells": n,
        "n_images_snapped": SNAP_COUNTS.get("n_images", 0),
        "n_panoramas_snapped": SNAP_COUNTS.get("n_panoramas", 0),
        # road frame x GSVI (denominator = all cells / road-accessible cells)
        "n_cells_road_accessible": len(road),
        "pct_cells_road_accessible": 100.0 * len(road) / n,
        "n_road_accessible_with_gsvi": n_road_gsvi,
        "pct_gsvi_given_road_accessible": 100.0 * n_road_gsvi / len(road) if len(road) else np.nan,
        "n_road_excluded_with_gsvi": n_excluded_gsvi,
        "pct_gsvi_given_road_excluded": 100.0 * n_excluded_gsvi / len(excluded) if len(excluded) else np.nan,
        "pct_observed_cells_road_excluded": 100.0 * n_excluded_gsvi / max(len(observed), 1),
        "n_images": int(cells["n_images"].sum()),
        "n_panoramas": int(cells["n_panoramas"].sum()),
        "n_cells_observed": len(observed),
        "pct_cells_observed": 100.0 * len(observed) / n,
        "n_cells_unobserved": len(unobserved),
        "pct_cells_unobserved": 100.0 * len(unobserved) / n,
        "median_images_per_observed_cell": float(observed["n_images"].median()) if len(observed) else np.nan,
        "mean_images_per_observed_cell": float(observed["n_images"].mean()) if len(observed) else np.nan,
        "median_panoramas_per_observed_cell": float(observed["n_panoramas"].median()) if len(observed) else np.nan,
        "median_dist_unobserved_m": float(unobserved["dist_nearest_obs_m"].median()) if len(unobserved) else np.nan,
        "p90_dist_unobserved_m": float(unobserved["dist_nearest_obs_m"].quantile(0.9)) if len(unobserved) else np.nan,
        "n_cells_beyond_far": int((cells["dist_nearest_obs_m"] > far_m).sum()),
        "pct_cells_beyond_far": 100.0 * (cells["dist_nearest_obs_m"] > far_m).mean(),
    }
    for src, sub in cells.groupby("grid_source"):
        row[f"pct_cells_observed_{src}"] = 100.0 * sub["has_gsvi"].mean()
    return pd.DataFrame([row])


def run_arm(grid: gpd.GeoDataFrame, arm: Arm, args: argparse.Namespace) -> pd.Series:
    print(f"\n[{arm.key}] {arm.label}")
    cells = compute_cells(grid, arm, args.svi_buffer_m)
    summary = compute_summary(cells, arm, args.far_m)

    print(f"Writing {grid_gpkg(arm).name}...")
    cells[CELL_COLUMNS + ["geometry"]].to_file(grid_gpkg(arm), driver="GPKG")
    print(f"Writing {summary_csv(arm).name}...")
    summary.to_csv(summary_csv(arm), index=False)
    ct = road_gsvi_crosstab(cells)
    print(f"Writing {crosstab_csv(arm).name}...")
    ct.to_csv(crosstab_csv(arm))

    s = summary.iloc[0]
    print("Summary")
    print(f"  Cells with >=1 image:        {int(s['n_cells_observed']):,} / {int(s['n_cells']):,} ({s['pct_cells_observed']:.1f}%)")
    print(f"  Road-accessible cells:       {int(s['n_cells_road_accessible']):,} ({s['pct_cells_road_accessible']:.1f}%)")
    print(f"  P(GSVI | road-accessible):   {int(s['n_road_accessible_with_gsvi']):,} / {int(s['n_cells_road_accessible']):,} "
          f"= {s['pct_gsvi_given_road_accessible']:.1f}%")
    print(f"  GSVI in road-excluded cells: {int(s['n_road_excluded_with_gsvi']):,} "
          f"({s['pct_gsvi_given_road_excluded']:.1f}% of excluded; {s['pct_observed_cells_road_excluded']:.1f}% of observed cells)")
    print("\n" + ct.to_string())
    print(f"  Median images / observed cell: {s['median_images_per_observed_cell']:.0f} "
          f"(mean {s['mean_images_per_observed_cell']:.1f}; median panoramas {s['median_panoramas_per_observed_cell']:.0f})")
    print(f"  Unobserved cells: median {s['median_dist_unobserved_m']:.0f} m to nearest panorama; "
          f"{s['pct_cells_beyond_far']:.1f}% of all cells >{args.far_m:.0f} m")
    return s


# ---------------------------------------------------------------------------
# Headline table: urban -> road -> GSVI -> grid
# ---------------------------------------------------------------------------
def load_headline_inputs(args: argparse.Namespace) -> dict[str, pd.Series]:
    gsvi = ARMS["gsvi"]
    paths = {
        "cityroad": OUTPUT_DIR / f"1_Nairobi_cityroad_summary_{buffer_file_tag(args.road_buffer_m)}.csv",
        "roadsvi": OUTPUT_DIR / f"2_Nairobi_roadsvi_summary_{gsvi.tagged(buffer_file_tag(args.svi_buffer_m))}.csv",
        "gridsvi": summary_csv(gsvi),
    }
    missing = [p.name for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Headline table needs Step 2a/2b/2e summaries; missing: " + ", ".join(missing)
        )
    return {k: pd.read_csv(p).iloc[0] for k, p in paths.items()}


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_path = active_grid_gpkg()
    print(f"Grid: {grid_path.name}")
    grid = _to_32737(gpd.read_file(grid_path))
    if "grid_source" not in grid.columns:
        grid["grid_source"] = "angela_original"
    print(f"  {len(grid):,} cells")

    for arm in select_arms(args.arm):
        run_arm(grid, arm, args)

    gsvi_summary = summary_csv(ARMS["gsvi"])
    if not gsvi_summary.exists():
        raise FileNotFoundError(f"Missing {gsvi_summary.name}; run with --arm gsvi first.")
    table_path = save_thesis_table(build_gridsvi_table(pd.read_csv(gsvi_summary).iloc[0]), "table_5_gridsvi.csv")
    print(f"\nWriting {table_path.name} (GSVI)...")

    inputs = load_headline_inputs(args)
    headline = build_coverage_headline_table(inputs["cityroad"], inputs["roadsvi"], inputs["gridsvi"])
    headline_path = save_thesis_table(headline, "table_0_coverage_headline.csv")
    print(f"Writing {headline_path.name}...\n")
    print(headline.to_string(index=False))
    print("\nFigures: Rscript 2coverage_analysis/5plot_gridsvi_maps.R ; Rscript 2coverage_analysis/5plot_gridsvi_analysis.R")


if __name__ == "__main__":
    main()

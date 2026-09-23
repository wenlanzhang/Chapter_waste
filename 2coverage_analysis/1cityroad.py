#!/usr/bin/env python3
"""City -> road: road access metrics for every 100 m grid cell.

For each cell of the active 100 m grid (chapter_paths.active_grid_gpkg()) three
things are computed from the cleaned local OSM segments (Step 1a):

  Road-accessible cell      cell intersects a mapped road, or lies within
                            --road-buffer-m (default 50 m) of one. Main measure
                            of whether a road-based observation system could
                            potentially observe the cell.
  Road length / density     total mapped road length inside the cell (m) and
                            km per km2. Distinguishes one tiny segment from a
                            highly road-connected cell.
  Distance to nearest road  cell polygon edge -> nearest road (0 if it
                            intersects). Quantifies the severity of
                            road-network exclusion for cells without roads.

Arm independent: roads are the same for GSVI and GSVI + SC.

Outputs (Data/Chapter_waste/2coverage_analysis/):
  1_Nairobi_cityroad_grid100m_32737.gpkg             per-cell metrics
  1_Nairobi_cityroad_summary_buf{B}m.csv             citywide summary
  thesis_table/table_1_cityroad_buf{B}m.csv        publication table
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, coverage_dir, prep_dir  # noqa: E402
from lib.road_coverage import buffer_file_tag, prepare_road_segments  # noqa: E402
from lib.roads import ROAD_FILES  # noqa: E402
from lib.thesis_tables import build_cityroad_table, save_thesis_table  # noqa: E402

INPUT_DIR = prep_dir()
OUTPUT_DIR = coverage_dir()
ROAD_GPKG = INPUT_DIR / ROAD_FILES["coverage"]

DEFAULT_ROAD_BUFFER_M = 50.0
GRID_GPKG_OUT = OUTPUT_DIR / "1_Nairobi_cityroad_grid100m_32737.gpkg"

CELL_COLUMNS = [
    "cell_id",
    "grid_source",
    "cell_area_m2",
    "intersects_road",
    "road_accessible",
    "road_length_m",
    "road_density_km_per_km2",
    "n_road_segments",
    "dist_road_edge_m",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Road access metrics on the 100 m grid.")
    parser.add_argument(
        "--road-buffer-m",
        type=float,
        default=DEFAULT_ROAD_BUFFER_M,
        help="A cell is road-accessible if within this distance of a road (default: 50)",
    )
    return parser.parse_args()


def summary_csv_path(buffer_m: float) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_cityroad_summary_{buffer_file_tag(buffer_m)}.csv"


def _to_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


# ---------------------------------------------------------------------------
# Per-cell metrics
# ---------------------------------------------------------------------------
def road_length_in_cells(grid: gpd.GeoDataFrame, segments: gpd.GeoDataFrame) -> pd.DataFrame:
    """Sum of clipped road length and number of distinct segments per cell."""
    pieces = gpd.overlay(
        segments[["segment_id", "geometry"]],
        grid[["cell_id", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["piece_m"] = pieces.geometry.length
    agg = pieces.groupby("cell_id").agg(
        road_length_m=("piece_m", "sum"),
        n_road_segments=("segment_id", "nunique"),
    )
    return agg


def distance_to_nearest_road(
    geoms: gpd.GeoSeries, segments: gpd.GeoDataFrame, column: str
) -> pd.Series:
    """Nearest-road distance for each geometry (0 where they touch)."""
    left = gpd.GeoDataFrame({"_i": np.arange(len(geoms))}, geometry=geoms.values, crs=geoms.crs)
    joined = gpd.sjoin_nearest(left, segments[["geometry"]], how="left", distance_col=column)
    # sjoin_nearest can return ties; keep the first per geometry
    joined = joined.drop_duplicates(subset="_i").set_index("_i").sort_index()
    return pd.Series(joined[column].to_numpy(), index=geoms.index, name=column)


def compute_metrics(
    grid: gpd.GeoDataFrame, segments: gpd.GeoDataFrame, buffer_m: float
) -> gpd.GeoDataFrame:
    cells = grid[["cell_id", "grid_source", "geometry"]].copy()
    cells["cell_area_m2"] = cells.geometry.area

    print("  Road length per cell (overlay)...")
    lengths = road_length_in_cells(cells, segments)
    cells["road_length_m"] = cells["cell_id"].map(lengths["road_length_m"]).fillna(0.0)
    cells["n_road_segments"] = cells["cell_id"].map(lengths["n_road_segments"]).fillna(0).astype(int)
    cells["road_density_km_per_km2"] = (cells["road_length_m"] / 1000) / (cells["cell_area_m2"] / 1e6)

    print("  Distance to nearest road (cell edge)...")
    cells["dist_road_edge_m"] = distance_to_nearest_road(cells.geometry, segments, "dist_road_edge_m")

    cells["intersects_road"] = (cells["road_length_m"] > 0).astype(int)
    cells["road_accessible"] = (
        (cells["intersects_road"] == 1) | (cells["dist_road_edge_m"] <= buffer_m)
    ).astype(int)
    return cells


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def compute_summary(cells: gpd.GeoDataFrame, segments: gpd.GeoDataFrame, buffer_m: float) -> pd.DataFrame:
    n = len(cells)
    with_road = cells.loc[cells["intersects_road"] == 1]
    accessible = cells.loc[cells["road_accessible"] == 1]
    excluded = cells.loc[cells["road_accessible"] == 0]
    total_km = float(segments["length_m"].sum()) / 1000 if "length_m" in segments.columns else float(segments.geometry.length.sum()) / 1000
    row = {
        "road_buffer_m": buffer_m,
        "n_cells": n,
        "n_road_segments": len(segments),
        "total_road_length_km": total_km,
        "road_length_in_cells_km": float(cells["road_length_m"].sum()) / 1000,
        "n_cells_with_road": len(with_road),
        "pct_cells_with_road": 100.0 * len(with_road) / n,
        "n_cells_road_accessible": len(accessible),
        "pct_cells_road_accessible": 100.0 * len(accessible) / n,
        "n_cells_road_excluded": len(excluded),
        "pct_cells_road_excluded": 100.0 * len(excluded) / n,
        "mean_road_density_km_per_km2": float(cells["road_density_km_per_km2"].mean()),
        "mean_road_density_with_road_km_per_km2": float(with_road["road_density_km_per_km2"].mean()) if len(with_road) else np.nan,
        "median_road_length_with_road_m": float(with_road["road_length_m"].median()) if len(with_road) else np.nan,
        "median_dist_road_edge_excluded_m": float(excluded["dist_road_edge_m"].median()) if len(excluded) else np.nan,
        "mean_dist_road_edge_excluded_m": float(excluded["dist_road_edge_m"].mean()) if len(excluded) else np.nan,
        "p90_dist_road_edge_excluded_m": float(excluded["dist_road_edge_m"].quantile(0.9)) if len(excluded) else np.nan,
        "max_dist_road_edge_m": float(cells["dist_road_edge_m"].max()),
    }
    for src, sub in cells.groupby("grid_source"):
        row[f"pct_cells_road_accessible_{src}"] = 100.0 * sub["road_accessible"].mean()
    return pd.DataFrame([row])


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_path = active_grid_gpkg()
    print(f"Grid: {grid_path.name}")
    grid = _to_32737(gpd.read_file(grid_path))
    if "grid_source" not in grid.columns:
        grid["grid_source"] = "angela_original"
    roads = _to_32737(gpd.read_file(ROAD_GPKG))
    segments = prepare_road_segments(roads)
    print(f"  {len(grid):,} cells | {len(segments):,} road segments | road buffer {args.road_buffer_m:.0f} m")

    cells = compute_metrics(grid, segments, args.road_buffer_m)
    summary = compute_summary(cells, segments, args.road_buffer_m)

    print(f"Writing {GRID_GPKG_OUT.name}...")
    cells[CELL_COLUMNS + ["geometry"]].to_file(GRID_GPKG_OUT, driver="GPKG")
    summary_csv = summary_csv_path(args.road_buffer_m)
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)
    thesis_path = save_thesis_table(
        build_cityroad_table(summary.iloc[0]),
        f"table_1_cityroad_{buffer_file_tag(args.road_buffer_m)}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    s = summary.iloc[0]
    print("\nSummary")
    print(f"  Cells intersecting a road:  {int(s['n_cells_with_road']):,} / {int(s['n_cells']):,} ({s['pct_cells_with_road']:.1f}%)")
    print(f"  Road-accessible (≤{args.road_buffer_m:.0f} m): {int(s['n_cells_road_accessible']):,} ({s['pct_cells_road_accessible']:.1f}%)")
    print(f"  Road-excluded cells:        {int(s['n_cells_road_excluded']):,} ({s['pct_cells_road_excluded']:.1f}%), "
          f"median {s['median_dist_road_edge_excluded_m']:.0f} m from nearest road (p90 {s['p90_dist_road_edge_excluded_m']:.0f} m)")
    print(f"  Mean road density:          {s['mean_road_density_km_per_km2']:.1f} km/km² (cells with road: {s['mean_road_density_with_road_km_per_km2']:.1f})")
    print("\nFigures: Rscript 2coverage_analysis/1plot_cityroad_maps.R ; Rscript 2coverage_analysis/1plot_cityroad_analysis.R")


if __name__ == "__main__":
    main()

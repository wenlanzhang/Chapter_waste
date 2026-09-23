#!/usr/bin/env python3
"""Road -> SVI coverage at the road-metre level (GSVI arm by default).

Each SVI sampling point (GSVI panoid, or self-collected image) is buffered
(default 50 m). For every cleaned road segment the buffers are unioned and the
line is split into covered and uncovered parts, so partially covered segments
contribute metres to both classes. The parts are then overlaid on the 100 m
grid to give each cell its covered / uncovered road metres and coverage ratio.

Outputs per arm (Data/Chapter_waste/2coverage_analysis/, tag = buf{B}m_{arm}):
  2_Nairobi_roadsvi_coverage_{tag}.gpkg         covered / uncovered line parts (maps)
  2_Nairobi_roadsvi_grid100m_{tag}.gpkg         per cell: road_m_covered, road_m_uncovered,
                                                svi_road_coverage_ratio (NaN without road)
  2_Nairobi_roadsvi_summary_{tag}.csv           citywide metres + cell-level summary
  thesis_table/table_2_roadsvi_buf{B}m.csv      GSVI arm only (Variable | Value | Unit)
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
from lib.arms import ARMS, Arm, add_arm_argument, select_arms  # noqa: E402
from lib.road_coverage import (  # noqa: E402
    DEFAULT_WORKERS,
    buffer_file_tag as file_tag,
    prepare_road_segments,
    split_road_coverage,
)
from lib.roads import ROAD_FILES  # noqa: E402
from lib.thesis_tables import build_roadsvi_table, save_thesis_table  # noqa: E402

ROAD_GPKG = ROAD_FILES["coverage"]
INPUT_DIR = prep_dir()
OUTPUT_DIR = coverage_dir()

DEFAULT_SVI_BUFFER_M = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nairobi road-metre SVI coverage per arm.")
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="SVI buffer distance in metres (default: 50)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel workers for segment splitting (default: 8)",
    )
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="Skip the metre split; rebuild the thesis table from the existing GSVI summary",
    )
    add_arm_argument(parser, default="gsvi")
    return parser.parse_args()


def summary_csv_path(buffer_m: float, arm: Arm) -> Path:
    return OUTPUT_DIR / f"2_Nairobi_roadsvi_summary_{arm.tagged(file_tag(buffer_m))}.csv"


def grid_gpkg_path(buffer_m: float, arm: Arm) -> Path:
    return OUTPUT_DIR / f"2_Nairobi_roadsvi_grid100m_{arm.tagged(file_tag(buffer_m))}.gpkg"


def _to_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


def road_coverage_on_grid(coverage_parts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Covered / uncovered road metres and coverage ratio per 100 m cell."""
    grid = _to_32737(gpd.read_file(active_grid_gpkg()))
    if "grid_source" not in grid.columns:
        grid["grid_source"] = "angela_original"
    cells = grid[["cell_id", "grid_source", "geometry"]].copy()
    pieces = gpd.overlay(
        _to_32737(coverage_parts)[["coverage_status", "geometry"]],
        cells[["cell_id", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["m"] = pieces.geometry.length
    wide = pieces.pivot_table(index="cell_id", columns="coverage_status", values="m", aggfunc="sum", fill_value=0.0)
    for status, col in [("covered", "road_m_covered"), ("uncovered", "road_m_uncovered")]:
        cells[col] = cells["cell_id"].map(wide[status] if status in wide else pd.Series(dtype=float)).fillna(0.0)
    total = cells["road_m_covered"] + cells["road_m_uncovered"]
    cells["road_m_total"] = total
    cells["svi_road_coverage_ratio"] = np.where(total > 0, cells["road_m_covered"] / total.where(total > 0, 1), np.nan)
    return cells


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    svi_buffer_m: float,
    svi_count: int,
    arm: Arm,
    cells: gpd.GeoDataFrame,
) -> pd.DataFrame:
    total_length_m = segment_summary["length_m"].sum()
    covered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "covered", "length_m"].sum()
    uncovered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "uncovered", "length_m"].sum()
    with_road = cells.loc[cells["road_m_total"] > 0]
    ratio = with_road["svi_road_coverage_ratio"]
    return pd.DataFrame(
        [
            {
                "arm": arm.key,
                "svi_buffer_m": svi_buffer_m,
                "svi_panoid_count": svi_count,
                "road_segment_count": len(segment_summary),
                "road_segments_fully_covered": int(segment_summary["fully_covered"].sum()),
                "road_segments_fully_uncovered": int(segment_summary["fully_uncovered"].sum()),
                "road_segments_partially_covered": int(segment_summary["partially_covered"].sum()),
                "coverage_part_count": len(coverage_parts),
                "total_road_length_km": total_length_m / 1000,
                "covered_road_length_km": covered_length_m / 1000,
                "uncovered_road_length_km": uncovered_length_m / 1000,
                "pct_road_length_covered": 100 * covered_length_m / max(total_length_m, 1),
                "pct_road_length_not_covered": 100 * uncovered_length_m / max(total_length_m, 1),
                # 100 m grid
                "n_cells": len(cells),
                "n_cells_with_road": len(with_road),
                "mean_svi_road_coverage_ratio": float(ratio.mean()) if len(with_road) else np.nan,
                "median_svi_road_coverage_ratio": float(ratio.median()) if len(with_road) else np.nan,
                "pct_cells_with_road_fully_covered": 100.0 * (ratio >= 0.999).mean() if len(with_road) else np.nan,
                "pct_cells_with_road_uncovered": 100.0 * (ratio <= 0.001).mean() if len(with_road) else np.nan,
            }
        ]
    )


def run_arm(args: argparse.Namespace, arm: Arm) -> pd.Series:
    tag = arm.tagged(file_tag(args.svi_buffer_m))
    coverage_gpkg = OUTPUT_DIR / f"2_Nairobi_roadsvi_coverage_{tag}.gpkg"
    summary_csv = summary_csv_path(args.svi_buffer_m, arm)

    print(f"\n[{arm.key}] {arm.label}")
    print(f"SVI buffer: {args.svi_buffer_m} m")

    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    svi = gpd.read_file(arm.svi_point_gpkg())

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)

    print(f"Splitting road coverage by metre ({len(segments):,} segments, {len(svi):,} sampling points)...")
    coverage_parts, segment_summary = split_road_coverage(
        segments, svi, args.svi_buffer_m, workers=args.workers
    )
    print("Aggregating covered / uncovered metres onto the 100 m grid...")
    cells = road_coverage_on_grid(coverage_parts)
    summary = compute_summary(segment_summary, coverage_parts, args.svi_buffer_m, len(svi), arm, cells)

    print(f"Writing {coverage_gpkg.name}...")
    coverage_parts.to_file(coverage_gpkg, driver="GPKG")
    print(f"Writing {grid_gpkg_path(args.svi_buffer_m, arm).name}...")
    cells.to_file(grid_gpkg_path(args.svi_buffer_m, arm), driver="GPKG")
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    s = summary.iloc[0]
    print("Summary")
    print(f"  Fully / partially / not covered segments: {s['road_segments_fully_covered']:,} / "
          f"{s['road_segments_partially_covered']:,} / {s['road_segments_fully_uncovered']:,} of {s['road_segment_count']:,}")
    print(f"  Road length covered: {s['pct_road_length_covered']:.1f}%  ({s['covered_road_length_km']:.0f} of {s['total_road_length_km']:.0f} km)")
    print(f"  Cells with road ({int(s['n_cells_with_road']):,}): coverage ratio mean {s['mean_svi_road_coverage_ratio']:.3f}, "
          f"median {s['median_svi_road_coverage_ratio']:.3f}; fully covered {s['pct_cells_with_road_fully_covered']:.1f}%, "
          f"uncovered {s['pct_cells_with_road_uncovered']:.1f}%")
    return s


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.table_only:
        for arm in select_arms(args.arm):
            run_arm(args, arm)

    # Thesis table reports the GSVI arm only (road -> SVI coverage is a GSVI property)
    gsvi_summary = summary_csv_path(args.svi_buffer_m, ARMS["gsvi"])
    if not gsvi_summary.exists():
        raise FileNotFoundError(f"Missing {gsvi_summary.name}; run with --arm gsvi first.")
    thesis_path = save_thesis_table(
        build_roadsvi_table(pd.read_csv(gsvi_summary).iloc[0]),
        f"table_2_roadsvi_{file_tag(args.svi_buffer_m)}.csv",
    )
    print(f"\nWriting {thesis_path.name} (GSVI)...")
    print(f"\nFigures: Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m={int(args.svi_buffer_m)}")


if __name__ == "__main__":
    main()

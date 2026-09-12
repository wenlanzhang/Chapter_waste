"""
Road -> SVI coverage at the road-metre level, with optional H3 aggregation.

Each road segment is split into covered and uncovered line parts relative to
nearby SVI panoid buffers. Partially covered segments contribute metre length
to both classes. Covered/uncovered parts are then intersected with an H3 grid
to produce per-cell road-length coverage ratios.
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

from chapter_paths import coverage_dir, prep_dir  # noqa: E402
from lib.road_coverage import (  # noqa: E402
    DEFAULT_WORKERS,
    buffer_file_tag as file_tag,
    compute_h3_metrics,
    export_coverage_csv,
    export_h3_csv,
    export_segment_csv,
    h3_file_tag,
    prepare_road_segments,
    split_road_coverage,
)
from lib.roads import ROAD_FILES  # noqa: E402
from lib.thesis_tables import build_roadsvi_table, save_thesis_table  # noqa: E402

ROAD_GPKG = ROAD_FILES["coverage"]
INPUT_DIR = prep_dir()
OUTPUT_DIR = coverage_dir()

DEFAULT_SVI_BUFFER_M = 50
DEFAULT_H3_RES = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nairobi road-metre SVI coverage (+ H3 ratios).")
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="SVI buffer distance in metres (default: 50)",
    )
    parser.add_argument(
        "--h3-res",
        type=int,
        default=DEFAULT_H3_RES,
        help="H3 resolution for cell-level coverage ratios (default: 8)",
    )
    parser.add_argument(
        "--h3-only",
        action="store_true",
        help="Skip metre split; aggregate existing Nairobi_roadsvi_coverage_buf*.gpkg to H3",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel workers for segment splitting (default: 8)",
    )
    return parser.parse_args()


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    svi_buffer_m: float,
    svi_count: int,
    h3_metrics: gpd.GeoDataFrame | None = None,
    h3_res: int | None = None,
) -> pd.DataFrame:
    total_length_m = segment_summary["length_m"].sum()
    covered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "covered", "length_m"].sum()
    uncovered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "uncovered", "length_m"].sum()

    summary = {
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
    }

    out = pd.DataFrame([summary])
    if h3_metrics is not None and h3_res is not None:
        out = _attach_h3_to_summary(out, h3_metrics, h3_res)
    return out


def _attach_h3_to_summary(
    summary: pd.DataFrame,
    h3_metrics: gpd.GeoDataFrame,
    h3_res: int,
) -> pd.DataFrame:
    with_road = h3_metrics.loc[h3_metrics["has_road"] == 1]
    summary = summary.copy()
    summary["h3_res"] = h3_res
    summary["h3_cells_in_city"] = len(h3_metrics)
    summary["h3_cells_with_road"] = int(h3_metrics["has_road"].sum())
    summary["h3_cells_with_svi_coverage"] = int(h3_metrics["has_svi_coverage"].sum())
    summary["pct_h3_cells_with_road"] = 100 * h3_metrics["has_road"].mean()
    summary["pct_h3_cells_with_svi_coverage"] = 100 * h3_metrics["has_svi_coverage"].mean()
    summary["mean_h3_svi_coverage_ratio"] = (
        float(with_road["svi_coverage_ratio"].mean()) if len(with_road) else np.nan
    )
    summary["median_h3_svi_coverage_ratio"] = (
        float(with_road["svi_coverage_ratio"].median()) if len(with_road) else np.nan
    )
    return summary


def run_h3_only(args: argparse.Namespace) -> None:
    """Aggregate existing metre-level coverage parts onto H3 without re-splitting."""
    tag = file_tag(args.svi_buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.svi_buffer_m)
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.gpkg"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.csv"

    if not coverage_gpkg.exists():
        raise FileNotFoundError(
            f"Missing {coverage_gpkg.name}. Run without --h3-only first "
            f"(python 2coverage_analysis/2roadsvi.py --svi-buffer-m {int(args.svi_buffer_m)})."
        )

    print(f"SVI buffer: {args.svi_buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")
    print(f"Loading existing coverage: {coverage_gpkg.name}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    coverage_parts = gpd.read_file(coverage_gpkg)

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(coverage_parts, boundary, args.h3_res)

    if summary_csv.exists():
        summary = pd.read_csv(summary_csv)
        summary = _attach_h3_to_summary(summary, h3_metrics, args.h3_res)
    else:
        total_m = coverage_parts["length_m"].sum()
        covered_m = coverage_parts.loc[
            coverage_parts["coverage_status"] == "covered", "length_m"
        ].sum()
        uncovered_m = coverage_parts.loc[
            coverage_parts["coverage_status"] == "uncovered", "length_m"
        ].sum()
        summary = pd.DataFrame(
            [
                {
                    "svi_buffer_m": args.svi_buffer_m,
                    "coverage_part_count": len(coverage_parts),
                    "total_road_length_km": total_m / 1000,
                    "covered_road_length_km": covered_m / 1000,
                    "uncovered_road_length_km": uncovered_m / 1000,
                    "pct_road_length_covered": 100 * covered_m / max(total_m, 1),
                    "pct_road_length_not_covered": 100 * uncovered_m / max(total_m, 1),
                    "svi_panoid_count": np.nan,
                }
            ]
        )
        summary = _attach_h3_to_summary(summary, h3_metrics, args.h3_res)

    print(f"Writing {h3_gpkg.name}...")
    h3_metrics.to_file(h3_gpkg, driver="GPKG")
    print(f"Writing {h3_csv.name}...")
    export_h3_csv(h3_metrics, h3_csv)
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadsvi_table(summary.iloc[0]),
        f"table_2_roadsvi_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures:")
    print(
        f"  Rscript 2coverage_analysis/2plot_roadsvi_maps.R"
        f" --svi-buffer-m={int(args.svi_buffer_m)} --h3-res={args.h3_res}"
    )
    print("\nSummary")
    if "pct_road_length_covered" in summary.columns:
        print(f"  Road length covered:        {summary['pct_road_length_covered'].iloc[0]:.1f}%")
    print(
        f"  Mean H3 SVI coverage ratio: {summary['mean_h3_svi_coverage_ratio'].iloc[0]:.3f}"
        f" (cells with road)"
    )
    print(
        f"  H3 cells with SVI coverage: {summary['h3_cells_with_svi_coverage'].iloc[0]:,} / "
        f"{summary['h3_cells_in_city'].iloc[0]:,}"
    )


def main() -> None:
    args = parse_args()
    if args.h3_only:
        run_h3_only(args)
        return

    tag = file_tag(args.svi_buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.svi_buffer_m)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    segments_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.gpkg"
    segments_csv = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.csv"
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.gpkg"
    coverage_csv = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.csv"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.csv"

    print(f"SVI buffer: {args.svi_buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    svi = gpd.read_file(INPUT_DIR / "Nairobi_SVI_point_gsvi_32737.gpkg")

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)

    print(f"Splitting road coverage by metre ({len(segments):,} segments, {len(svi):,} panoids)...")
    coverage_parts, segment_summary = split_road_coverage(
        segments,
        svi,
        args.svi_buffer_m,
        workers=args.workers,
    )

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(coverage_parts, boundary, args.h3_res)
    summary = compute_summary(
        segment_summary,
        coverage_parts,
        args.svi_buffer_m,
        len(svi),
        h3_metrics=h3_metrics,
        h3_res=args.h3_res,
    )

    print(f"Writing {segments_gpkg.name}...")
    segment_summary.to_file(segments_gpkg, driver="GPKG")

    print(f"Writing {segments_csv.name}...")
    export_segment_csv(segment_summary, segments_csv)

    print(f"Writing {coverage_gpkg.name}...")
    coverage_parts.to_file(coverage_gpkg, driver="GPKG")

    print(f"Writing {coverage_csv.name}...")
    export_coverage_csv(coverage_parts, coverage_csv)

    print(f"Writing {h3_gpkg.name}...")
    h3_metrics.to_file(h3_gpkg, driver="GPKG")

    print(f"Writing {h3_csv.name}...")
    export_h3_csv(h3_metrics, h3_csv)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadsvi_table(summary.iloc[0]),
        f"table_2_roadsvi_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures:")
    print(
        f"  Rscript 2coverage_analysis/2plot_roadsvi_maps.R"
        f" --svi-buffer-m={int(args.svi_buffer_m)} --h3-res={args.h3_res}"
    )
    print("\nSummary")
    print(
        f"  Fully covered segments:     {summary['road_segments_fully_covered'].iloc[0]:,} / "
        f"{summary['road_segment_count'].iloc[0]:,}"
    )
    print(
        f"  Partially covered segments: {summary['road_segments_partially_covered'].iloc[0]:,} / "
        f"{summary['road_segment_count'].iloc[0]:,}"
    )
    print(
        f"  Fully uncovered segments:   {summary['road_segments_fully_uncovered'].iloc[0]:,} / "
        f"{summary['road_segment_count'].iloc[0]:,}"
    )
    print(f"  Road length covered:        {summary['pct_road_length_covered'].iloc[0]:.1f}%")
    print(f"  Road length uncovered:      {summary['pct_road_length_not_covered'].iloc[0]:.1f}%")
    print(
        f"  Mean H3 SVI coverage ratio: {summary['mean_h3_svi_coverage_ratio'].iloc[0]:.3f}"
        f" (cells with road)"
    )
    print(
        f"  H3 cells with SVI coverage: {summary['h3_cells_with_svi_coverage'].iloc[0]:,} / "
        f"{summary['h3_cells_in_city'].iloc[0]:,}"
    )


if __name__ == "__main__":
    main()

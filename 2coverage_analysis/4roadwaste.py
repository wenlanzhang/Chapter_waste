#!/usr/bin/env python3
"""Road → waste-positive panoid coverage (road-metre level, optional H3).

Same geometry logic as 2roadsvi.py, but buffers only waste-positive GSVI
panoids (Y=1 at panoid unit) rather than all GSVI sampling panoids.

Default: 50 m buffer; EPSG:32737 roads + panoids.
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
from lib.thesis_tables import build_roadwaste_table, save_thesis_table  # noqa: E402

ROAD_GPKG = ROAD_FILES["coverage"]
INPUT_DIR = prep_dir()
OUTPUT_DIR = coverage_dir()
SVIWASTE_GPKG = OUTPUT_DIR / "Nairobi_sviwaste_points.gpkg"
SVI_GPKG = INPUT_DIR / "Nairobi_SVI_point_gsvi_32737.gpkg"
WASTE_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"

DEFAULT_BUFFER_M = 50.0
DEFAULT_H3_RES = 8
H3_RATIO_KWARGS = {
    "ratio_col": "waste_coverage_ratio",
    "covered_flag": "has_waste_coverage",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Nairobi road-metre coverage by waste-positive GSVI panoid buffers "
            "(+ optional H3 ratios)."
        )
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=DEFAULT_BUFFER_M,
        help="Buffer around waste-positive panoids in metres (default: 50)",
    )
    parser.add_argument(
        "--h3-res",
        type=int,
        default=DEFAULT_H3_RES,
        help="H3 resolution for cell-level ratios (default: 8)",
    )
    parser.add_argument(
        "--h3-only",
        action="store_true",
        help="Skip metre split; aggregate existing Nairobi_roadwaste_coverage_buf*.gpkg",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel workers for segment splitting (default: 8)",
    )
    return parser.parse_args()


def load_waste_positive_panoids() -> gpd.GeoDataFrame:
    """One point per waste-positive GSVI panoid (prefer Step 2c labels)."""
    if SVIWASTE_GPKG.exists():
        pts = gpd.read_file(SVIWASTE_GPKG)
        if "waste_positive" in pts.columns:
            waste = pts.loc[pts["waste_positive"] == 1].copy()
        else:
            waste = pts.copy()
    else:
        svi = gpd.read_file(SVI_GPKG)
        waste_pts = gpd.read_file(WASTE_GPKG)
        waste_ids = set(waste_pts["panoid"].dropna().astype(str).unique())
        svi = svi.copy()
        svi["panoid"] = svi["panoid"].astype(str)
        waste = svi.loc[svi["panoid"].isin(waste_ids)].copy()

    if waste.crs is None or waste.crs.to_epsg() != 32737:
        waste = waste.to_crs(epsg=32737)

    # One geometry per panoid if duplicates slipped in
    if "panoid" in waste.columns:
        waste = waste.drop_duplicates(subset=["panoid"], keep="first")

    waste = waste[waste.geometry.notna() & ~waste.geometry.is_empty].reset_index(
        drop=True
    )
    return waste


def _attach_h3_summary(
    summary: pd.DataFrame,
    h3_metrics: gpd.GeoDataFrame,
    h3_res: int,
) -> pd.DataFrame:
    with_road = h3_metrics.loc[h3_metrics["has_road"] == 1]
    summary = summary.copy()
    summary["h3_res"] = h3_res
    summary["h3_cells_in_city"] = len(h3_metrics)
    summary["h3_cells_with_road"] = int(h3_metrics["has_road"].sum())
    summary["h3_cells_with_waste_coverage"] = int(
        h3_metrics["has_waste_coverage"].sum()
    )
    summary["pct_h3_cells_with_road"] = 100 * h3_metrics["has_road"].mean()
    summary["pct_h3_cells_with_waste_coverage"] = (
        100 * h3_metrics["has_waste_coverage"].mean()
    )
    summary["mean_h3_waste_coverage_ratio"] = (
        float(with_road["waste_coverage_ratio"].mean()) if len(with_road) else np.nan
    )
    summary["median_h3_waste_coverage_ratio"] = (
        float(with_road["waste_coverage_ratio"].median()) if len(with_road) else np.nan
    )
    return summary


def _maybe_attach_all_svi_comparison(summary: pd.DataFrame, buffer_m: float) -> pd.DataFrame:
    """If all-GSVI roadsvi summary exists, attach reference coverage %."""
    ref_path = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{file_tag(buffer_m)}.csv"
    if not ref_path.exists():
        return summary
    ref = pd.read_csv(ref_path)
    if "pct_road_length_covered" not in ref.columns:
        return summary
    all_pct = float(ref["pct_road_length_covered"].iloc[0])
    waste_pct = float(summary["pct_road_length_covered"].iloc[0])
    summary = summary.copy()
    summary["pct_road_length_covered_all_gsvi"] = all_pct
    summary["pct_of_all_gsvi_coverage"] = (
        100.0 * waste_pct / all_pct if all_pct > 0 else np.nan
    )
    if "svi_panoid_count" in ref.columns:
        summary["all_gsvi_panoid_count"] = int(ref["svi_panoid_count"].iloc[0])
    return summary


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    buffer_m: float,
    waste_count: int,
    h3_metrics: gpd.GeoDataFrame | None = None,
    h3_res: int | None = None,
) -> pd.DataFrame:
    total_length_m = segment_summary["length_m"].sum()
    covered_length_m = coverage_parts.loc[
        coverage_parts["coverage_status"] == "covered", "length_m"
    ].sum()
    uncovered_length_m = coverage_parts.loc[
        coverage_parts["coverage_status"] == "uncovered", "length_m"
    ].sum()

    summary = pd.DataFrame(
        [
            {
                "buffer_m": buffer_m,
                "waste_positive_panoid_count": waste_count,
                "road_segment_count": len(segment_summary),
                "road_segments_fully_covered": int(segment_summary["fully_covered"].sum()),
                "road_segments_fully_uncovered": int(
                    segment_summary["fully_uncovered"].sum()
                ),
                "road_segments_partially_covered": int(
                    segment_summary["partially_covered"].sum()
                ),
                "coverage_part_count": len(coverage_parts),
                "total_road_length_km": total_length_m / 1000,
                "covered_road_length_km": covered_length_m / 1000,
                "uncovered_road_length_km": uncovered_length_m / 1000,
                "pct_road_length_covered": 100 * covered_length_m / max(total_length_m, 1),
                "pct_road_length_not_covered": 100
                * uncovered_length_m
                / max(total_length_m, 1),
                "unit": "waste_positive_panoid_buffer",
            }
        ]
    )
    if h3_metrics is not None and h3_res is not None:
        summary = _attach_h3_summary(summary, h3_metrics, h3_res)
    summary = _maybe_attach_all_svi_comparison(summary, buffer_m)
    return summary


def run_h3_only(args: argparse.Namespace) -> None:
    tag = file_tag(args.buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.buffer_m)
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadwaste_coverage_{tag}.gpkg"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadwaste_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadwaste_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadwaste_grid_{h3_tag}.csv"

    if not coverage_gpkg.exists():
        raise FileNotFoundError(
            f"Missing {coverage_gpkg.name}. Run without --h3-only first:\n"
            f"  python 2coverage_analysis/4roadwaste.py --buffer-m {int(args.buffer_m)}"
        )

    print(f"Waste+ panoid buffer: {args.buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")
    print(f"Loading existing coverage: {coverage_gpkg.name}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    coverage_parts = gpd.read_file(coverage_gpkg)

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(
        coverage_parts, boundary, args.h3_res, **H3_RATIO_KWARGS
    )

    if summary_csv.exists():
        summary = pd.read_csv(summary_csv)
        summary = _attach_h3_summary(summary, h3_metrics, args.h3_res)
        summary = _maybe_attach_all_svi_comparison(summary, args.buffer_m)
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
                    "buffer_m": args.buffer_m,
                    "coverage_part_count": len(coverage_parts),
                    "total_road_length_km": total_m / 1000,
                    "covered_road_length_km": covered_m / 1000,
                    "uncovered_road_length_km": uncovered_m / 1000,
                    "pct_road_length_covered": 100 * covered_m / max(total_m, 1),
                    "pct_road_length_not_covered": 100 * uncovered_m / max(total_m, 1),
                    "waste_positive_panoid_count": np.nan,
                    "unit": "waste_positive_panoid_buffer",
                }
            ]
        )
        summary = _attach_h3_summary(summary, h3_metrics, args.h3_res)
        summary = _maybe_attach_all_svi_comparison(summary, args.buffer_m)

    print(f"Writing {h3_gpkg.name}...")
    h3_metrics.to_file(h3_gpkg, driver="GPKG")
    print(f"Writing {h3_csv.name}...")
    export_h3_csv(h3_metrics, h3_csv, **H3_RATIO_KWARGS)
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadwaste_table(summary.iloc[0]),
        f"table_4_roadwaste_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")
    _print_summary(summary)


def main() -> None:
    args = parse_args()
    if args.h3_only:
        run_h3_only(args)
        return

    tag = file_tag(args.buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.buffer_m)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    segments_gpkg = OUTPUT_DIR / f"Nairobi_roadwaste_segments_{tag}.gpkg"
    segments_csv = OUTPUT_DIR / f"Nairobi_roadwaste_segments_{tag}.csv"
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadwaste_coverage_{tag}.gpkg"
    coverage_csv = OUTPUT_DIR / f"Nairobi_roadwaste_coverage_{tag}.csv"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadwaste_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadwaste_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadwaste_grid_{h3_tag}.csv"

    print(f"Waste+ panoid buffer: {args.buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    waste = load_waste_positive_panoids()

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)

    print(
        f"Splitting road coverage by metre "
        f"({len(segments):,} segments, {len(waste):,} waste+ panoids)..."
    )
    coverage_parts, segment_summary = split_road_coverage(
        segments,
        waste,
        args.buffer_m,
        workers=args.workers,
    )

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(
        coverage_parts, boundary, args.h3_res, **H3_RATIO_KWARGS
    )
    summary = compute_summary(
        segment_summary,
        coverage_parts,
        args.buffer_m,
        len(waste),
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
    export_h3_csv(h3_metrics, h3_csv, **H3_RATIO_KWARGS)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadwaste_table(summary.iloc[0]),
        f"table_4_roadwaste_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    _print_summary(summary)


def _print_summary(summary: pd.DataFrame) -> None:
    print("\nSummary (road length near waste-positive panoids)")
    print(
        f"  Waste+ panoids:             "
        f"{int(summary['waste_positive_panoid_count'].iloc[0]):,}"
    )
    print(
        f"  Fully covered segments:     "
        f"{int(summary['road_segments_fully_covered'].iloc[0]):,} / "
        f"{int(summary['road_segment_count'].iloc[0]):,}"
    )
    print(
        f"  Partially covered segments: "
        f"{int(summary['road_segments_partially_covered'].iloc[0]):,} / "
        f"{int(summary['road_segment_count'].iloc[0]):,}"
    )
    print(
        f"  Fully uncovered segments:   "
        f"{int(summary['road_segments_fully_uncovered'].iloc[0]):,} / "
        f"{int(summary['road_segment_count'].iloc[0]):,}"
    )
    print(
        f"  Road length covered:        "
        f"{summary['pct_road_length_covered'].iloc[0]:.2f}% "
        f"({summary['covered_road_length_km'].iloc[0]:.1f} km)"
    )
    print(
        f"  Road length uncovered:      "
        f"{summary['pct_road_length_not_covered'].iloc[0]:.2f}%"
    )
    if "pct_road_length_covered_all_gsvi" in summary.columns:
        print(
            f"  All-GSVI road coverage ref:  "
            f"{summary['pct_road_length_covered_all_gsvi'].iloc[0]:.1f}% "
            f"(waste+ is "
            f"{summary['pct_of_all_gsvi_coverage'].iloc[0]:.1f}% of that)"
        )
    if "mean_h3_waste_coverage_ratio" in summary.columns:
        print(
            f"  Mean H3 waste coverage:     "
            f"{summary['mean_h3_waste_coverage_ratio'].iloc[0]:.3f} "
            f"(cells with road)"
        )
        print(
            f"  H3 cells with waste cover:  "
            f"{int(summary['h3_cells_with_waste_coverage'].iloc[0]):,} / "
            f"{int(summary['h3_cells_in_city'].iloc[0]):,}"
        )


if __name__ == "__main__":
    main()

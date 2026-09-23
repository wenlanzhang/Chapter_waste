#!/usr/bin/env python3
"""Road -> waste-positive sampling-point coverage (road-metre level; GSVI arm by default).

Same geometry logic as 2roadsvi.py, but buffers only the waste-positive
sampling points labelled in Step 2c (GSVI panoids, or self-collected images)
rather than all sampling points. The arm's all-SVI road coverage from 2b is
attached as a reference percentage.

Outputs per arm (Data/Chapter_waste/2coverage_analysis/, tag = buf{B}m_{arm}):
  4_Nairobi_roadwaste_coverage_{tag}.gpkg
  4_Nairobi_roadwaste_summary_{tag}.csv
  thesis_table/table_4_roadwaste_buf{B}m.csv   GSVI arm only
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
from lib.arms import ARMS, Arm, add_arm_argument, observation_key, select_arms  # noqa: E402
from lib.road_coverage import (  # noqa: E402
    DEFAULT_WORKERS,
    buffer_file_tag as file_tag,
    prepare_road_segments,
    split_road_coverage,
)
from lib.roads import ROAD_FILES  # noqa: E402
from lib.thesis_tables import build_roadwaste_table, save_thesis_table  # noqa: E402

ROAD_GPKG = ROAD_FILES["coverage"]
INPUT_DIR = prep_dir()
OUTPUT_DIR = coverage_dir()

DEFAULT_BUFFER_M = 50.0


def sviwaste_gpkg(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("3_Nairobi_sviwaste_points")


def summary_csv_path(buffer_m: float, arm: Arm) -> Path:
    return OUTPUT_DIR / f"4_Nairobi_roadwaste_summary_{arm.tagged(file_tag(buffer_m))}.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nairobi road-metre coverage by waste-positive sampling-point buffers, per arm."
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=DEFAULT_BUFFER_M,
        help="Buffer around waste-positive points in metres (default: 50)",
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


def load_waste_positive_points(arm: Arm) -> gpd.GeoDataFrame:
    """One point per waste-positive sampling point (prefer Step 2c labels)."""
    path = sviwaste_gpkg(arm)
    if path.exists():
        pts = gpd.read_file(path)
        waste = pts.loc[pts["waste_positive"] == 1].copy() if "waste_positive" in pts.columns else pts.copy()
    else:
        svi = gpd.read_file(arm.svi_point_gpkg())
        waste_ids = set(observation_key(gpd.read_file(arm.waste_gpkg())).unique())
        waste = svi.loc[observation_key(svi).isin(waste_ids)].copy()

    if waste.crs is None or waste.crs.to_epsg() != 32737:
        waste = waste.to_crs(epsg=32737)
    # One geometry per sampling point (panoid, or img_name for self-collected rows)
    waste["obs_key"] = observation_key(waste)
    waste = waste.drop_duplicates(subset=["obs_key"], keep="first")
    return waste[waste.geometry.notna() & ~waste.geometry.is_empty].reset_index(drop=True)


def _attach_all_svi_reference(summary: pd.DataFrame, buffer_m: float, arm: Arm) -> pd.DataFrame:
    """If this arm's all-SVI roadsvi summary exists, attach reference coverage %."""
    ref_path = OUTPUT_DIR / f"2_Nairobi_roadsvi_summary_{arm.tagged(file_tag(buffer_m))}.csv"
    if not ref_path.exists():
        return summary
    ref = pd.read_csv(ref_path)
    all_pct = float(ref["pct_road_length_covered"].iloc[0])
    waste_pct = float(summary["pct_road_length_covered"].iloc[0])
    summary = summary.copy()
    summary["pct_road_length_covered_all_svi"] = all_pct
    summary["pct_of_all_svi_coverage"] = 100.0 * waste_pct / all_pct if all_pct > 0 else np.nan
    summary["all_svi_panoid_count"] = int(ref["svi_panoid_count"].iloc[0])
    return summary


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    buffer_m: float,
    waste_count: int,
    arm: Arm,
) -> pd.DataFrame:
    total_length_m = segment_summary["length_m"].sum()
    covered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "covered", "length_m"].sum()
    uncovered_length_m = coverage_parts.loc[coverage_parts["coverage_status"] == "uncovered", "length_m"].sum()
    summary = pd.DataFrame(
        [
            {
                "arm": arm.key,
                "buffer_m": buffer_m,
                "waste_positive_panoid_count": waste_count,
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
                "unit": "waste_positive_point_buffer",
            }
        ]
    )
    return _attach_all_svi_reference(summary, buffer_m, arm)


def run_arm(args: argparse.Namespace, arm: Arm) -> pd.Series:
    tag = arm.tagged(file_tag(args.buffer_m))
    coverage_gpkg = OUTPUT_DIR / f"4_Nairobi_roadwaste_coverage_{tag}.gpkg"
    summary_csv = summary_csv_path(args.buffer_m, arm)

    print(f"\n[{arm.key}] {arm.label}")
    print(f"Waste+ point buffer: {args.buffer_m} m")

    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    waste = load_waste_positive_points(arm)

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)
    print(f"Splitting road coverage by metre ({len(segments):,} segments, {len(waste):,} waste+ points)...")
    coverage_parts, segment_summary = split_road_coverage(
        segments, waste, args.buffer_m, workers=args.workers
    )
    summary = compute_summary(segment_summary, coverage_parts, args.buffer_m, len(waste), arm)

    print(f"Writing {coverage_gpkg.name}...")
    coverage_parts.to_file(coverage_gpkg, driver="GPKG")
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    s = summary.iloc[0]
    print("Summary (road length near waste-positive points)")
    print(f"  Waste+ points:        {int(s['waste_positive_panoid_count']):,}")
    print(f"  Road length covered:  {s['pct_road_length_covered']:.2f}% ({s['covered_road_length_km']:.1f} km)")
    if "pct_road_length_covered_all_svi" in summary.columns:
        print(f"  All-SVI reference:    {s['pct_road_length_covered_all_svi']:.1f}% "
              f"(waste+ is {s['pct_of_all_svi_coverage']:.1f}% of that)")
    return s


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.table_only:
        for arm in select_arms(args.arm):
            run_arm(args, arm)

    gsvi_summary = summary_csv_path(args.buffer_m, ARMS["gsvi"])
    if not gsvi_summary.exists():
        raise FileNotFoundError(f"Missing {gsvi_summary.name}; run with --arm gsvi first.")
    thesis_path = save_thesis_table(
        build_roadwaste_table(pd.read_csv(gsvi_summary).iloc[0]),
        f"table_4_roadwaste_{file_tag(args.buffer_m)}.csv",
    )
    print(f"\nWriting {thesis_path.name} (GSVI)...")


if __name__ == "__main__":
    main()

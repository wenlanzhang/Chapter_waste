"""
SVI -> waste coverage at the sampling-point level, per analysis arm.

Labels each SVI sampling point as waste-positive if it appears in the waste
dataset. GSVI points are panoids (one per panorama); self-collected Faith/ZWL
images have no panoid, so each image is its own sampling point and is matched
on img_name (see lib.arms.observation_key).

Outputs per arm: 3_Nairobi_sviwaste_points_{arm}_32737.gpkg and
3_Nairobi_sviwaste_summary_{arm}.csv. Runs the GSVI arm by default; the thesis
table table_3_sviwaste.csv reports GSVI only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import coverage_dir  # noqa: E402
from lib.arms import ARMS, Arm, add_arm_argument, observation_key, select_arms  # noqa: E402
from lib.thesis_tables import build_sviwaste_table, save_thesis_table  # noqa: E402

OUTPUT_DIR = coverage_dir()


def points_gpkg(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("3_Nairobi_sviwaste_points")


def summary_csv(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("3_Nairobi_sviwaste_summary", suffix="", ext="csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label waste-positive SVI sampling points per arm.")
    add_arm_argument(parser, default="gsvi")
    return parser.parse_args()


def label_waste_on_svi(svi: gpd.GeoDataFrame, waste: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    waste_keys = set(observation_key(waste).unique())
    out = svi.copy()
    out["obs_key"] = observation_key(out)
    out["waste_positive"] = out["obs_key"].isin(waste_keys).astype(int)
    out["waste_negative"] = (1 - out["waste_positive"]).astype(int)
    return out


def compute_summary(svi: gpd.GeoDataFrame, waste: gpd.GeoDataFrame, arm: Arm) -> pd.DataFrame:
    waste_positive = int(svi["waste_positive"].sum())
    waste_keys = observation_key(waste)
    summary = {
        "arm": arm.key,
        "total_svi_panoids": len(svi),
        "total_waste_detections": len(waste),
        "unique_waste_panoids": waste_keys.nunique(),
        "svi_waste_positive_panoids": waste_positive,
        "svi_waste_negative_panoids": int(svi["waste_negative"].sum()),
        "pct_svi_with_waste": 100 * waste_positive / max(len(svi), 1),
        "pct_waste_detections_matched_to_svi": 100
        * waste_keys.isin(svi["obs_key"]).sum()
        / max(len(waste), 1),
    }
    if "source" in svi.columns:
        for src, n in svi["source"].value_counts().items():
            summary[f"svi_points_{src}"] = int(n)
            summary[f"svi_waste_positive_{src}"] = int(
                svi.loc[svi["source"] == src, "waste_positive"].sum()
            )
    return pd.DataFrame([summary])


def run_arm(arm: Arm) -> pd.Series:
    print(f"\n[{arm.key}] {arm.label}")
    svi = gpd.read_file(arm.svi_point_gpkg())
    waste = gpd.read_file(arm.waste_gpkg())

    print("Labelling waste-positive SVI sampling points...")
    points = label_waste_on_svi(svi, waste)
    summary = compute_summary(points, waste, arm)

    print(f"Writing {points_gpkg(arm).name}...")
    points.to_file(points_gpkg(arm), driver="GPKG")
    print(f"Writing {summary_csv(arm).name}...")
    summary.to_csv(summary_csv(arm), index=False)

    row = summary.iloc[0]
    print(f"  SVI sampling points:    {row['total_svi_panoids']:,}")
    print(f"  Waste-positive points:  {row['svi_waste_positive_panoids']:,} ({row['pct_svi_with_waste']:.2f}%)")
    print(f"  Waste detections:       {row['total_waste_detections']:,}")
    return row


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for arm in select_arms(args.arm):
        run_arm(arm)

    gsvi_summary = summary_csv(ARMS["gsvi"])
    if not gsvi_summary.exists():
        raise FileNotFoundError(f"Missing {gsvi_summary.name}; run with --arm gsvi first.")
    thesis_path = save_thesis_table(
        build_sviwaste_table(pd.read_csv(gsvi_summary).iloc[0]),
        "table_3_sviwaste.csv",
    )
    print(f"\nWriting {thesis_path.name} (GSVI)...")
    print("\nFigures: Rscript 2coverage_analysis/3plot_sviwaste_maps.R")


if __name__ == "__main__":
    main()

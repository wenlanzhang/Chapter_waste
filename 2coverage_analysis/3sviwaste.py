"""
SVI -> waste coverage at the panoid (sampling point) level.

Labels each SVI panoid as waste-positive if it appears in the waste dataset.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from thesis_tables import build_sviwaste_table, save_thesis_table

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "2coverage_analysis"


def label_waste_on_svi(svi: gpd.GeoDataFrame, waste: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    waste_panoids = set(waste["panoid"].dropna().unique())
    out = svi.copy()
    out["waste_positive"] = out["panoid"].isin(waste_panoids).astype(int)
    out["waste_negative"] = (1 - out["waste_positive"]).astype(int)
    return out


def export_point_csv(points: gpd.GeoDataFrame, path: Path) -> None:
    columns = [
        "panoid",
        "img_name",
        "lat",
        "lon",
        "img_dir",
        "Domestic",
        "waste_positive",
        "waste_negative",
    ]
    points[columns].to_csv(path, index=False)


def compute_summary(svi: gpd.GeoDataFrame, waste: gpd.GeoDataFrame) -> pd.DataFrame:
    waste_positive = int(svi["waste_positive"].sum())
    summary = {
        "total_svi_panoids": len(svi),
        "total_waste_detections": len(waste),
        "unique_waste_panoids": waste["panoid"].nunique(),
        "svi_waste_positive_panoids": waste_positive,
        "svi_waste_negative_panoids": int(svi["waste_negative"].sum()),
        "pct_svi_with_waste": 100 * waste_positive / max(len(svi), 1),
        "pct_waste_detections_matched_to_svi": 100
        * waste["panoid"].isin(svi["panoid"]).sum()
        / max(len(waste), 1),
    }
    return pd.DataFrame([summary])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    points_gpkg = OUTPUT_DIR / "Nairobi_sviwaste_points.gpkg"
    points_csv = OUTPUT_DIR / "Nairobi_sviwaste_points.csv"
    summary_csv = OUTPUT_DIR / "Nairobi_sviwaste_summary.csv"

    svi = gpd.read_file(INPUT_DIR / "Nairobi_SVI_point_32737.gpkg")
    waste = gpd.read_file(INPUT_DIR / "Nairobi_Waste_point_32737.gpkg")

    print("Labelling waste-positive SVI panoids...")
    points = label_waste_on_svi(svi, waste)
    summary = compute_summary(points, waste)

    print(f"Writing {points_gpkg.name}...")
    points.to_file(points_gpkg, driver="GPKG")

    print(f"Writing {points_csv.name}...")
    export_point_csv(points, points_csv)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_sviwaste_table(summary.iloc[0]),
        "table_3_sviwaste.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures: Rscript 2coverage_analysis/3plot_sviwaste_maps.R")
    print("\nSummary")
    print(f"  SVI sampling panoids:   {summary['total_svi_panoids'].iloc[0]:,}")
    print(f"  Waste-positive panoids: {summary['svi_waste_positive_panoids'].iloc[0]:,} ({summary['pct_svi_with_waste'].iloc[0]:.2f}%)")
    print(f"  Waste detections:       {summary['total_waste_detections'].iloc[0]:,}")


if __name__ == "__main__":
    main()

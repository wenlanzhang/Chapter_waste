"""
Compare GSVI vs self-collected imagery and waste detections (image-level counts).

Reads harmonised Step 1 GeoPackages and writes a thesis summary table with one
row per data source: GSVI, Self-collected, and GSVI + Self-collected.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "4_compare"
TABLE_DIR = OUTPUT_DIR / "thesis_table"
TABLE_PATH = TABLE_DIR / "Nairobi_compare_sources_table.csv"

SELF_SOURCES = {"Faith", "ZWL"}

SVI_IMAGE_GSVI = INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg"
SVI_IMAGE_COMBINED = INPUT_DIR / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg"
WASTE_GSVI = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
WASTE_COMBINED = INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg"


def _fmt_int(value: int) -> str:
    return f"{int(value):,}"


def count_by_source(gdf: gpd.GeoDataFrame) -> dict[str, int]:
    grouped = gdf.groupby("source", observed=True).size()
    return {str(source): int(count) for source, count in grouped.items()}


def build_compare_sources_table() -> pd.DataFrame:
    svi_gsvi = gpd.read_file(SVI_IMAGE_GSVI)
    svi_combined = gpd.read_file(SVI_IMAGE_COMBINED)
    waste_gsvi = gpd.read_file(WASTE_GSVI)
    waste_combined = gpd.read_file(WASTE_COMBINED)

    svi_counts = count_by_source(svi_combined)
    waste_counts = count_by_source(waste_combined)

    self_svi = sum(svi_counts.get(source, 0) for source in SELF_SOURCES)
    self_waste = sum(waste_counts.get(source, 0) for source in SELF_SOURCES)

    rows = [
        {
            "Data source": "GSVI",
            "SVI images": _fmt_int(len(svi_gsvi)),
            "Waste-positive images": _fmt_int(len(waste_gsvi)),
        },
        {
            "Data source": "Self-collected",
            "SVI images": _fmt_int(self_svi),
            "Waste-positive images": _fmt_int(self_waste),
        },
        {
            "Data source": "GSVI + Self-collected",
            "SVI images": _fmt_int(len(svi_combined)),
            "Waste-positive images": _fmt_int(len(waste_combined)),
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    table = build_compare_sources_table()
    table.to_csv(TABLE_PATH, index=False)
    print(f"Wrote {TABLE_PATH}")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

"""Publication-style summary tables for thesis / reports."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

THESIS_TABLE_DIR = Path(
    "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/2coverage_analysis/thesis_table"
)


def _fmt_int(value: float | int) -> str:
    return f"{int(round(value)):,}"


def _fmt_float(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}"


def _table(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Variable", "Value", "Unit"])


def save_thesis_table(table: pd.DataFrame, filename: str) -> Path:
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / filename
    table.to_csv(path, index=False)
    return path


def build_cityroad_table(
    summary: pd.Series,
    metrics: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
) -> pd.DataFrame:
    if "length_m" in roads.columns:
        total_km = roads["length_m"].sum() / 1000
    else:
        total_km = roads.geometry.length.sum() / 1000
    mean_coverage_pct = 100 * metrics["road_coverage_ratio"].mean()
    return _table(
        [
            ("Total road length", _fmt_int(total_km), "km"),
            ("Number of road segments", _fmt_int(len(roads)), ""),
            (
                "Mean road density",
                _fmt_float(summary["mean_road_length_density_km_per_km2"]),
                "km/km²",
            ),
            ("Mean road coverage", _fmt_float(mean_coverage_pct), "%"),
            (
                "Mean intersections",
                _fmt_float(summary["mean_road_intersection_density_per_km2"]),
                "per km²",
            ),
        ]
    )


def build_roadsvi_table(summary: pd.Series) -> pd.DataFrame:
    return _table(
        [
            ("Total road length", _fmt_int(summary["total_road_length_km"]), "km"),
            ("Covered road length", _fmt_int(summary["covered_road_length_km"]), "km"),
            ("Uncovered road length", _fmt_int(summary["uncovered_road_length_km"]), "km"),
            ("Coverage", _fmt_float(summary["pct_road_length_covered"]), "%"),
            ("Number of SVI panoids", _fmt_int(summary["svi_panoid_count"]), ""),
        ]
    )


def build_sviwaste_table(summary: pd.Series) -> pd.DataFrame:
    return _table(
        [
            ("Total SVI", _fmt_int(summary["total_svi_panoids"]), ""),
            ("Waste-positive", _fmt_int(summary["svi_waste_positive_panoids"]), ""),
            ("Waste detections", _fmt_int(summary["total_waste_detections"]), ""),
            ("Detection rate", _fmt_float(summary["pct_svi_with_waste"]), "%"),
        ]
    )

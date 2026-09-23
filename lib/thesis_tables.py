"""Publication-style summary tables for thesis / reports."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from chapter_paths import coverage_dir

THESIS_TABLE_DIR = coverage_dir() / "thesis_table"


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


def build_cityroad_table(summary: pd.Series) -> pd.DataFrame:
    """Road access on the 100 m grid (Step 2a)."""
    buf = int(summary["road_buffer_m"])
    return _table(
        [
            ("Total road length", _fmt_int(summary["total_road_length_km"]), "km"),
            ("Number of road segments", _fmt_int(summary["n_road_segments"]), ""),
            ("100 m cells", _fmt_int(summary["n_cells"]), ""),
            ("Cells intersecting a road", _fmt_float(summary["pct_cells_with_road"]), "%"),
            (f"Road-accessible cells (\u2264{buf} m)", _fmt_float(summary["pct_cells_road_accessible"]), "%"),
            ("Road-excluded cells", _fmt_float(summary["pct_cells_road_excluded"]), "%"),
            ("Mean road density, cells with road", _fmt_float(summary["mean_road_density_with_road_km_per_km2"]), "km/km\u00b2"),
            ("Median distance to road, excluded cells", _fmt_int(summary["median_dist_road_edge_excluded_m"]), "m"),
            ("90th pct distance to road, excluded cells", _fmt_int(summary["p90_dist_road_edge_excluded_m"]), "m"),
        ]
    )


def build_roadsvi_table(summary: pd.Series) -> pd.DataFrame:
    rows = [
        ("Total road length", _fmt_int(summary["total_road_length_km"]), "km"),
        ("Covered road length", _fmt_int(summary["covered_road_length_km"]), "km"),
        ("Uncovered road length", _fmt_int(summary["uncovered_road_length_km"]), "km"),
        ("Coverage", _fmt_float(summary["pct_road_length_covered"]), "%"),
        ("Number of SVI panoids", _fmt_int(summary["svi_panoid_count"]), ""),
    ]
    return _table(rows)


def build_sviwaste_table(summary: pd.Series) -> pd.DataFrame:
    return _table(
        [
            ("Total SVI", _fmt_int(summary["total_svi_panoids"]), ""),
            ("Waste-positive", _fmt_int(summary["svi_waste_positive_panoids"]), ""),
            ("Waste detections", _fmt_int(summary["total_waste_detections"]), ""),
            ("Detection rate", _fmt_float(summary["pct_svi_with_waste"]), "%"),
        ]
    )


def build_roadwaste_table(summary: pd.Series) -> pd.DataFrame:
    """Road-metre coverage by waste-positive panoid buffers (Step 2d)."""
    rows = [
        ("Total road length", _fmt_int(summary["total_road_length_km"]), "km"),
        ("Covered road length", _fmt_int(summary["covered_road_length_km"]), "km"),
        ("Uncovered road length", _fmt_int(summary["uncovered_road_length_km"]), "km"),
        ("Coverage", _fmt_float(summary["pct_road_length_covered"]), "%"),
        ("Waste-positive panoids", _fmt_int(summary["waste_positive_panoid_count"]), ""),
    ]
    if (
        "pct_road_length_covered_all_svi" in summary.index
        and pd.notna(summary["pct_road_length_covered_all_svi"])
    ):
        rows.append(
            (
                "All-GSVI road coverage (ref.)",
                _fmt_float(summary["pct_road_length_covered_all_svi"]),
                "%",
            )
        )
    return _table(rows)


def build_gridsvi_table(summary: pd.Series) -> pd.DataFrame:
    """GSVI observation status on the 100 m grid (Step 2e)."""
    far = int(summary["far_m"])
    return _table(
        [
            ("100 m cells", _fmt_int(summary["n_cells"]), ""),
            ("GSVI images", _fmt_int(summary["n_images"]), ""),
            ("GSVI panoramas", _fmt_int(summary["n_panoramas"]), ""),
            ("Panoramas in grid slivers, snapped to nearest cell", _fmt_int(summary["n_panoramas_snapped"]), ""),
            ("Cells with \u22651 GSVI image", _fmt_float(summary["pct_cells_observed"]), "%"),
            ("Cells without GSVI image", _fmt_float(summary["pct_cells_unobserved"]), "%"),
            ("Road-accessible cells with \u22651 GSVI image", _fmt_float(summary["pct_gsvi_given_road_accessible"]), "%"),
            ("Road-excluded cells with \u22651 GSVI image", _fmt_float(summary["pct_gsvi_given_road_excluded"]), "%"),
            ("Median images per observed cell", _fmt_int(summary["median_images_per_observed_cell"]), ""),
            ("Median panoramas per observed cell", _fmt_int(summary["median_panoramas_per_observed_cell"]), ""),
            ("Median distance to observation, unobserved cells", _fmt_int(summary["median_dist_unobserved_m"]), "m"),
            (f"Cells >{far} m from an observation", _fmt_float(summary["pct_cells_beyond_far"]), "%"),
        ]
    )


def build_coverage_headline_table(
    cityroad: pd.Series, roadsvi: pd.Series, gridsvi: pd.Series
) -> pd.DataFrame:
    """Headline chain urban -> road -> GSVI -> analytical grid (Stage | Metric | Denominator | Value)."""
    road_buf = int(cityroad["road_buffer_m"])
    far = int(gridsvi["far_m"])
    all_cells = "All urban 100 m cells"
    # Panoramas, not images, are the unit here: each panorama yields four directional
    # images, so images/cell overstates the number of observation locations.
    rows = [
        ("Urban \u2192 road frame", f"Cells within {road_buf} m of mapped road", all_cells, f"{cityroad['pct_cells_road_accessible']:.1f}%"),
        ("", "Median distance to road among road-excluded cells", "Road-excluded cells", f"{int(round(cityroad['median_dist_road_edge_excluded_m']))} m"),
        ("Road frame \u2192 GSVI", "Road-accessible cells containing \u22651 GSVI panorama", "Road-accessible cells", f"{gridsvi['pct_gsvi_given_road_accessible']:.1f}%"),
        ("", "Mapped road length with GSVI support", "Total mapped road length", f"{roadsvi['pct_road_length_covered']:.1f}%"),
        ("GSVI \u2192 analytical grid", "Cells containing \u22651 direct GSVI observation", all_cells, f"{gridsvi['pct_cells_observed']:.1f}%"),
        ("Observation intensity", "Median panoramas per observed cell", "Directly observed cells", f"{int(round(gridsvi['median_panoramas_per_observed_cell']))}"),
        ("Observation gaps", f"Cells >{far} m from nearest GSVI observation", all_cells, f"{gridsvi['pct_cells_beyond_far']:.1f}%"),
    ]
    return pd.DataFrame(rows, columns=["Stage", "Metric", "Denominator", "Value"])

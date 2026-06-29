"""
City -> road coverage metrics on an H3 grid.

Computes per-cell road density, segment counts, intersection density,
road-buffer coverage, and road-type composition. No SVI/waste metrics here.

Network centrality (betweenness/closeness) is intentionally omitted because
it is too resource-intensive at city scale.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from h3_utils import PROJECTED_CRS, build_h3_grid, clip_grid_to_city
from thesis_tables import build_cityroad_table, save_thesis_table

import sys

_PREP_DIR = Path(__file__).resolve().parent.parent / "1prepare_chapter_data"
if str(_PREP_DIR) not in sys.path:
    sys.path.insert(0, str(_PREP_DIR))
from road_utils import ROAD_FILES

ROAD_GPKG = ROAD_FILES["coverage"]

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "2coverage_analysis"

DEFAULT_H3_RES = 8
DEFAULT_ROAD_BUFFER_M = 50
SNAP_TOLERANCE_M = 1.0

ROAD_TYPE_COLUMNS = [
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "service",
    "unclassified",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nairobi city->road H3 coverage metrics.")
    parser.add_argument("--h3-res", type=int, default=DEFAULT_H3_RES, help="H3 resolution (default: 8)")
    parser.add_argument(
        "--road-buffer-m",
        type=float,
        default=DEFAULT_ROAD_BUFFER_M,
        help="Road buffer for coverage ratio in metres (default: 50)",
    )
    return parser.parse_args()


def file_tag(h3_res: int, road_buffer_m: float) -> str:
    return f"h3_res{h3_res}_buf{int(road_buffer_m)}m"


def normalize_road_type(value: object) -> str:
    if pd.isna(value):
        return "other"
    text = str(value).lower()
    if "primary" in text:
        return "primary"
    if "secondary" in text:
        return "secondary"
    if "tertiary" in text:
        return "tertiary"
    if text == "residential":
        return "residential"
    if text == "service":
        return "service"
    if text == "unclassified":
        return "unclassified"
    return "other"


def roads_in_cells(roads: gpd.GeoDataFrame, grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    road_cells = gpd.overlay(
        roads[["osm_id", "type", "geometry"]].copy(),
        grid[["h3_index", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    road_cells = road_cells.explode(index_parts=False).reset_index(drop=True)
    road_cells = road_cells[road_cells.geometry.length > 0].copy()
    road_cells["length_m"] = road_cells.geometry.length
    road_cells["road_class"] = road_cells["type"].map(normalize_road_type)
    road_cells["segment_id"] = road_cells.index
    return road_cells


def road_length_and_segments(road_cells: gpd.GeoDataFrame) -> pd.DataFrame:
    length = road_cells.groupby("h3_index", as_index=False).agg(
        road_length_m=("length_m", "sum"),
        road_segment_count=("segment_id", "count"),
    )
    length["has_road"] = (length["road_length_m"] > 0).astype(int)
    return length


def road_type_counts(road_cells: gpd.GeoDataFrame) -> pd.DataFrame:
    counts = road_cells.groupby("h3_index", as_index=False).agg(
        road_type_count=("type", "nunique"),
    )
    return counts


def road_type_shares(road_cells: gpd.GeoDataFrame) -> pd.DataFrame:
    by_type = (
        road_cells.groupby(["h3_index", "road_class"], as_index=False)["length_m"]
        .sum()
        .pivot(index="h3_index", columns="road_class", values="length_m")
        .fillna(0)
    )
    for col in ROAD_TYPE_COLUMNS:
        if col not in by_type.columns:
            by_type[col] = 0.0

    total = by_type[ROAD_TYPE_COLUMNS].sum(axis=1)
    shares = by_type[ROAD_TYPE_COLUMNS].div(total.replace(0, np.nan), axis=0).fillna(0)
    shares = shares.rename(columns={col: f"pct_{col}" for col in ROAD_TYPE_COLUMNS})
    return shares.reset_index()


def road_coverage_ratio(
    roads: gpd.GeoDataFrame,
    metrics: gpd.GeoDataFrame,
    buffer_m: float,
) -> tuple[pd.Series, pd.Series]:
    road_buffers = roads.copy()
    road_buffers["geometry"] = road_buffers.geometry.buffer(buffer_m)
    covered = gpd.overlay(
        road_buffers[["geometry"]],
        metrics[["h3_index", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    covered["area_m2"] = covered.geometry.area
    area_by_cell = covered.groupby("h3_index")["area_m2"].sum()
    ratio = area_by_cell / metrics.set_index("h3_index")["city_area_m2"]
    return ratio.fillna(0).clip(0, 1), area_by_cell


def intersection_counts_by_cell(
    roads: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    snap_tolerance_m: float = SNAP_TOLERANCE_M,
) -> pd.Series:
    """Lightweight junction count: endpoints that snap to the same coordinate."""
    roads = roads.explode(index_parts=False).reset_index(drop=True)
    endpoints = []
    for geom in roads.geometry:
        coords = list(geom.coords)
        endpoints.append(Point(coords[0]))
        endpoints.append(Point(coords[-1]))

    points = gpd.GeoDataFrame(geometry=endpoints, crs=roads.crs)
    points["snap_x"] = (points.geometry.x / snap_tolerance_m).round().astype(int)
    points["snap_y"] = (points.geometry.y / snap_tolerance_m).round().astype(int)

    endpoint_counts = points.groupby(["snap_x", "snap_y"]).size()
    junction_keys = endpoint_counts[endpoint_counts >= 3].index

    if len(junction_keys) == 0:
        return pd.Series(dtype=int)

    junctions = pd.DataFrame(list(junction_keys), columns=["snap_x", "snap_y"])
    junctions["geometry"] = gpd.points_from_xy(
        junctions["snap_x"] * snap_tolerance_m,
        junctions["snap_y"] * snap_tolerance_m,
        crs=roads.crs,
    )
    junctions = gpd.GeoDataFrame(junctions, geometry="geometry", crs=roads.crs)

    joined = gpd.sjoin(junctions, grid[["h3_index", "geometry"]], how="inner", predicate="within")
    return joined.groupby("h3_index").size()


def compute_metrics(
    boundary: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    h3_res: int,
    road_buffer_m: float,
) -> gpd.GeoDataFrame:
    grid = build_h3_grid(boundary, h3_res)
    metrics = clip_grid_to_city(grid, boundary)

    road_cells = roads_in_cells(roads, grid)
    length_stats = road_length_and_segments(road_cells)
    type_count_stats = road_type_counts(road_cells)
    type_stats = road_type_shares(road_cells)
    coverage_ratio, coverage_area = road_coverage_ratio(roads, metrics, road_buffer_m)
    intersections = intersection_counts_by_cell(roads, grid)

    metrics = metrics.merge(length_stats, on="h3_index", how="left")
    metrics = metrics.merge(type_count_stats, on="h3_index", how="left")
    metrics = metrics.merge(type_stats, on="h3_index", how="left")
    metrics["road_length_m"] = metrics["road_length_m"].fillna(0)
    metrics["road_segment_count"] = metrics["road_segment_count"].fillna(0).astype(int)
    metrics["road_type_count"] = metrics["road_type_count"].fillna(0).astype(int)
    metrics["has_road"] = metrics["has_road"].fillna(0).astype(int)

    for col in [f"pct_{t}" for t in ROAD_TYPE_COLUMNS]:
        if col not in metrics.columns:
            metrics[col] = 0.0
        metrics[col] = metrics[col].fillna(0)

    city_area_km2 = metrics["city_area_m2"] / 1e6
    metrics["road_length_density_km_per_km2"] = np.where(
        city_area_km2 > 0,
        (metrics["road_length_m"] / 1000) / city_area_km2,
        0,
    )

    metrics["road_intersection_count"] = metrics["h3_index"].map(intersections).fillna(0).astype(int)
    metrics["road_intersection_density_per_km2"] = np.where(
        city_area_km2 > 0,
        metrics["road_intersection_count"] / city_area_km2,
        0,
    )

    metrics["road_coverage_ratio"] = metrics["h3_index"].map(coverage_ratio).fillna(0)
    metrics["road_coverage_area_m2"] = metrics["h3_index"].map(coverage_area).fillna(0)
    metrics["has_road_coverage"] = (metrics["road_coverage_ratio"] > 0).astype(int)

    return metrics


def export_cell_csv(metrics: gpd.GeoDataFrame, path: Path) -> None:
    columns = [
        "h3_index",
        "h3_res",
        "cell_area_m2",
        "city_area_m2",
        "in_city",
        "road_length_m",
        "road_length_density_km_per_km2",
        "road_segment_count",
        "road_type_count",
        "road_intersection_count",
        "road_intersection_density_per_km2",
        "road_coverage_ratio",
        "road_coverage_area_m2",
        "has_road",
        "has_road_coverage",
        "pct_primary",
        "pct_secondary",
        "pct_tertiary",
        "pct_residential",
        "pct_service",
        "pct_unclassified",
    ]
    metrics[columns].to_csv(path, index=False)


def citywide_road_coverage_area(
    roads: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    buffer_m: float,
) -> float:
    from shapely.ops import unary_union

    road_buffers = roads.copy()
    road_buffers["geometry"] = road_buffers.geometry.buffer(buffer_m)
    covered = gpd.overlay(
        gpd.GeoDataFrame(geometry=[unary_union(road_buffers.geometry)], crs=roads.crs),
        boundary[["geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    return float(covered.geometry.area.sum())


def compute_summary(
    metrics: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    h3_res: int,
    road_buffer_m: float,
) -> pd.DataFrame:
    city_area_m2 = metrics["city_area_m2"].sum()
    covered_area_m2 = citywide_road_coverage_area(roads, boundary, road_buffer_m)
    summary = {
        "h3_res": h3_res,
        "road_buffer_m": road_buffer_m,
        "city_area_km2": city_area_m2 / 1e6,
        "h3_cells_in_city": len(metrics),
        "total_road_length_km": metrics["road_length_m"].sum() / 1000,
        "mean_road_length_density_km_per_km2": metrics["road_length_density_km_per_km2"].mean(),
        "mean_road_segment_count": metrics["road_segment_count"].mean(),
        "total_road_intersections": int(metrics["road_intersection_count"].sum()),
        "mean_road_intersection_density_per_km2": metrics["road_intersection_density_per_km2"].mean(),
        "pct_city_area_road_covered": 100 * covered_area_m2 / city_area_m2,
        "pct_cells_with_road": 100 * metrics["has_road"].mean(),
        "pct_cells_with_road_coverage": 100 * metrics["has_road_coverage"].mean(),
    }
    for road_type in ROAD_TYPE_COLUMNS:
        summary[f"citywide_pct_{road_type}"] = 100 * (
            metrics["road_length_m"] * metrics[f"pct_{road_type}"]
        ).sum() / max(metrics["road_length_m"].sum(), 1)
    return pd.DataFrame([summary])


def main() -> None:
    args = parse_args()
    tag = file_tag(args.h3_res, args.road_buffer_m)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_csv = OUTPUT_DIR / f"Nairobi_cityroad_grid_{tag}.csv"
    summary_csv = OUTPUT_DIR / f"Nairobi_cityroad_summary_{tag}.csv"
    grid_gpkg = OUTPUT_DIR / f"Nairobi_cityroad_grid_{tag}.gpkg"

    print(f"H3 resolution: {args.h3_res}")
    print(f"Road buffer:   {args.road_buffer_m} m")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)

    print("Computing city->road metrics...")
    metrics = compute_metrics(boundary, roads, args.h3_res, args.road_buffer_m)
    summary = compute_summary(metrics, boundary, roads, args.h3_res, args.road_buffer_m)

    print(f"Writing {grid_csv.name}...")
    export_cell_csv(metrics, grid_csv)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_cityroad_table(summary.iloc[0], metrics, roads),
        f"table_1_cityroad_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print(f"Writing {grid_gpkg.name}...")
    metrics.to_file(grid_gpkg, driver="GPKG")

    print("\nFigures:")
    print("  Rscript 2coverage_analysis/1plot_cityroad_maps.R")
    print("  Rscript 2coverage_analysis/1plot_cityroad_analysis.R")
    print("\nCity-wide summary")
    print(f"  Road-covered city area: {summary['pct_city_area_road_covered'].iloc[0]:.1f}%")
    print(f"  Cells with road:        {summary['pct_cells_with_road'].iloc[0]:.1f}%")
    print(f"  Mean road density:      {summary['mean_road_length_density_km_per_km2'].iloc[0]:.2f} km/km²")
    print(f"  Total intersections:    {summary['total_road_intersections'].iloc[0]:,}")


if __name__ == "__main__":
    main()

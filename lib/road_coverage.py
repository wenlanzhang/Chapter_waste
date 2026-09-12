"""Road-metre coverage: buffer points, split segments, aggregate to H3."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

from .h3_grid import build_h3_grid, clip_grid_to_city

MIN_PART_LENGTH_M = 0.1
DEFAULT_WORKERS = 8


def buffer_file_tag(buffer_m: float) -> str:
    return f"buf{int(buffer_m)}m"


def h3_file_tag(h3_res: int, buffer_m: float) -> str:
    return f"h3_res{h3_res}_buf{int(buffer_m)}m"


def prepare_road_segments(roads: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Use cleaned road segments as-is (one row per OSM way segment)."""
    segments = roads[["segment_id", "osm_id", "type", "geometry", "length_m"]].copy()
    segments = segments[segments.geometry.length > 0].reset_index(drop=True)
    return segments


def _union_geoms(geoms) -> object:
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return None
    if len(geoms) == 1:
        return geoms[0]
    try:
        from shapely import union_all

        return union_all(geoms)
    except ImportError:
        return unary_union(geoms)


def _iter_line_parts(geom, min_length_m: float):
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "LineString":
        if geom.length >= min_length_m:
            yield geom
    elif geom.geom_type == "MultiLineString":
        for part in geom.geoms:
            if part.length >= min_length_m:
                yield part


def _split_one_segment(
    segment_id,
    osm_id,
    road_type,
    seg_geom,
    buffer_indices,
    buf_geoms,
    min_length_m: float,
) -> list[dict]:
    local_zone = _union_geoms(buf_geoms[i] for i in buffer_indices)
    rows: list[dict] = []

    for part in _iter_line_parts(seg_geom.intersection(local_zone), min_length_m):
        rows.append(
            {
                "segment_id": segment_id,
                "osm_id": osm_id,
                "type": road_type,
                "coverage_status": "covered",
                "length_m": part.length,
                "geometry": part,
            }
        )
    for part in _iter_line_parts(seg_geom.difference(local_zone), min_length_m):
        rows.append(
            {
                "segment_id": segment_id,
                "osm_id": osm_id,
                "type": road_type,
                "coverage_status": "uncovered",
                "length_m": part.length,
                "geometry": part,
            }
        )
    return rows


def split_road_coverage(
    segments: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    buffer_m: float,
    min_length_m: float = MIN_PART_LENGTH_M,
    workers: int = DEFAULT_WORKERS,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Split each segment into covered / uncovered line parts vs point buffers."""
    base_cols = ["segment_id", "osm_id", "type", "geometry"]
    base = segments[base_cols].copy()

    print("  Buffering points...")
    point_buffers = gpd.GeoDataFrame(geometry=points.geometry.buffer(buffer_m), crs=points.crs)
    buf_geoms = point_buffers.geometry.values

    print("  Spatial join: segments x buffers...")
    hits = gpd.sjoin(base, point_buffers, how="inner", predicate="intersects")
    buf_ids_by_seg = (
        hits.groupby("segment_id")["index_right"]
        .apply(lambda idx: sorted(set(idx.to_numpy())))
        .to_dict()
    )

    touched_ids = set(buf_ids_by_seg)
    untouched = base[~base["segment_id"].isin(touched_ids)].copy()
    touched = base[base["segment_id"].isin(touched_ids)].copy()
    print(f"  Touched segments: {len(touched):,} | Fully uncovered: {len(untouched):,}")

    rows: list[dict] = []
    for seg_row in untouched.itertuples(index=False):
        rows.append(
            {
                "segment_id": seg_row.segment_id,
                "osm_id": seg_row.osm_id,
                "type": seg_row.type,
                "coverage_status": "uncovered",
                "length_m": seg_row.geometry.length,
                "geometry": seg_row.geometry,
            }
        )

    touched_records = list(touched.itertuples(index=False))
    n_touched = len(touched_records)
    print(f"  Splitting {n_touched:,} touched segments ({workers} workers)...")

    def _task(seg_row):
        return _split_one_segment(
            seg_row.segment_id,
            seg_row.osm_id,
            seg_row.type,
            seg_row.geometry,
            buf_ids_by_seg[seg_row.segment_id],
            buf_geoms,
            min_length_m,
        )

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for part_rows in pool.map(_task, touched_records, chunksize=256):
            rows.extend(part_rows)
            done += 1
            if done % 5000 == 0 or done == n_touched:
                print(f"    {done:,}/{n_touched:,} segments processed")

    coverage_parts = gpd.GeoDataFrame(rows, geometry="geometry", crs=segments.crs)

    cov_by_seg = (
        coverage_parts.loc[coverage_parts["coverage_status"] == "covered"]
        .groupby("segment_id")["length_m"]
        .sum()
    )
    uncov_by_seg = (
        coverage_parts.loc[coverage_parts["coverage_status"] == "uncovered"]
        .groupby("segment_id")["length_m"]
        .sum()
    )

    segment_summary = segments.copy()
    segment_summary["covered_length_m"] = segment_summary["segment_id"].map(cov_by_seg).fillna(0.0)
    segment_summary["uncovered_length_m"] = segment_summary["segment_id"].map(uncov_by_seg).fillna(0.0)
    segment_summary["pct_length_covered"] = (
        100 * segment_summary["covered_length_m"] / segment_summary["length_m"].clip(lower=1e-9)
    )
    segment_summary["fully_covered"] = (segment_summary["uncovered_length_m"] <= min_length_m).astype(int)
    segment_summary["fully_uncovered"] = (segment_summary["covered_length_m"] <= min_length_m).astype(int)
    segment_summary["partially_covered"] = (
        (segment_summary["fully_covered"] == 0) & (segment_summary["fully_uncovered"] == 0)
    ).astype(int)

    return coverage_parts, segment_summary


def export_segment_csv(segments: gpd.GeoDataFrame, path: Path) -> None:
    columns = [
        "segment_id",
        "osm_id",
        "type",
        "length_m",
        "covered_length_m",
        "uncovered_length_m",
        "pct_length_covered",
        "fully_covered",
        "fully_uncovered",
        "partially_covered",
    ]
    segments[columns].to_csv(path, index=False)


def export_coverage_csv(coverage: gpd.GeoDataFrame, path: Path) -> None:
    columns = [
        "segment_id",
        "osm_id",
        "type",
        "coverage_status",
        "length_m",
    ]
    coverage[columns].to_csv(path, index=False)


def compute_h3_metrics(
    coverage_parts: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    h3_res: int,
    *,
    ratio_col: str = "svi_coverage_ratio",
    covered_flag: str = "has_svi_coverage",
) -> gpd.GeoDataFrame:
    """Aggregate covered/uncovered road metres onto an H3 grid."""
    grid = build_h3_grid(boundary, h3_res)
    metrics = clip_grid_to_city(grid, boundary)

    cell_parts = gpd.overlay(
        coverage_parts[["coverage_status", "geometry"]],
        metrics[["h3_index", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    cell_parts = cell_parts.explode(index_parts=False).reset_index(drop=True)
    cell_parts = cell_parts[cell_parts.geometry.length > 0].copy()
    cell_parts["length_m"] = cell_parts.geometry.length

    by_status = (
        cell_parts.groupby(["h3_index", "coverage_status"], as_index=False)["length_m"]
        .sum()
        .pivot(index="h3_index", columns="coverage_status", values="length_m")
        .fillna(0.0)
    )
    for col in ("covered", "uncovered"):
        if col not in by_status.columns:
            by_status[col] = 0.0

    length_stats = pd.DataFrame(
        {
            "h3_index": by_status.index,
            "covered_road_length_m": by_status["covered"].to_numpy(),
            "uncovered_road_length_m": by_status["uncovered"].to_numpy(),
        }
    )
    length_stats["road_length_m"] = (
        length_stats["covered_road_length_m"] + length_stats["uncovered_road_length_m"]
    )
    length_stats[ratio_col] = np.where(
        length_stats["road_length_m"] > 0,
        length_stats["covered_road_length_m"] / length_stats["road_length_m"],
        np.nan,
    )
    length_stats["has_road"] = (length_stats["road_length_m"] > 0).astype(int)
    length_stats[covered_flag] = (length_stats["covered_road_length_m"] > 0).astype(int)

    metrics = metrics.merge(length_stats, on="h3_index", how="left")
    metrics["road_length_m"] = metrics["road_length_m"].fillna(0.0)
    metrics["covered_road_length_m"] = metrics["covered_road_length_m"].fillna(0.0)
    metrics["uncovered_road_length_m"] = metrics["uncovered_road_length_m"].fillna(0.0)
    metrics["has_road"] = metrics["has_road"].fillna(0).astype(int)
    metrics[covered_flag] = metrics[covered_flag].fillna(0).astype(int)
    return metrics


def export_h3_csv(
    metrics: gpd.GeoDataFrame,
    path: Path,
    *,
    ratio_col: str = "svi_coverage_ratio",
    covered_flag: str = "has_svi_coverage",
) -> None:
    columns = [
        "h3_index",
        "h3_res",
        "cell_area_m2",
        "city_area_m2",
        "in_city",
        "road_length_m",
        "covered_road_length_m",
        "uncovered_road_length_m",
        ratio_col,
        "has_road",
        covered_flag,
    ]
    metrics[columns].to_csv(path, index=False)

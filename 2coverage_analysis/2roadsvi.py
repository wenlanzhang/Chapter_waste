"""
Road -> SVI coverage at the road-metre level.

Each road segment is split into covered and uncovered line parts relative to
nearby SVI panoid buffers. Partially covered segments contribute metre length
to both classes.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

import sys

_PREP_DIR = Path(__file__).resolve().parent.parent / "1prepare_chapter_data"
if str(_PREP_DIR) not in sys.path:
    sys.path.insert(0, str(_PREP_DIR))
from road_utils import ROAD_FILES
from thesis_tables import build_roadsvi_table, save_thesis_table

ROAD_GPKG = ROAD_FILES["coverage"]

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "2coverage_analysis"

DEFAULT_SVI_BUFFER_M = 50
MIN_PART_LENGTH_M = 0.1
DEFAULT_WORKERS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nairobi road-metre SVI coverage.")
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="SVI buffer distance in metres (default: 50)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Parallel workers for segment splitting (default: 8)",
    )
    return parser.parse_args()


def file_tag(svi_buffer_m: float) -> str:
    return f"buf{int(svi_buffer_m)}m"


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
    svi: gpd.GeoDataFrame,
    buffer_m: float,
    min_length_m: float = MIN_PART_LENGTH_M,
    workers: int = DEFAULT_WORKERS,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Split each segment into covered / uncovered line parts."""
    base_cols = ["segment_id", "osm_id", "type", "geometry"]
    base = segments[base_cols].copy()

    print("  Buffering SVI panoids...")
    svi_buffers = gpd.GeoDataFrame(geometry=svi.geometry.buffer(buffer_m), crs=svi.crs)
    buf_geoms = svi_buffers.geometry.values

    print("  Spatial join: segments x SVI buffers...")
    hits = gpd.sjoin(base, svi_buffers, how="inner", predicate="intersects")
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


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    svi_buffer_m: float,
    svi_count: int,
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
    return pd.DataFrame([summary])


def main() -> None:
    args = parse_args()
    tag = file_tag(args.svi_buffer_m)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    segments_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.gpkg"
    segments_csv = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.csv"
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.gpkg"
    coverage_csv = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.csv"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{tag}.csv"

    print(f"SVI buffer: {args.svi_buffer_m} m")

    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    svi = gpd.read_file(INPUT_DIR / "Nairobi_SVI_point_32737.gpkg")

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)

    print(f"Splitting road coverage by metre ({len(segments):,} segments, {len(svi):,} panoids)...")
    coverage_parts, segment_summary = split_road_coverage(
        segments,
        svi,
        args.svi_buffer_m,
        workers=args.workers,
    )
    summary = compute_summary(segment_summary, coverage_parts, args.svi_buffer_m, len(svi))

    print(f"Writing {segments_gpkg.name}...")
    segment_summary.to_file(segments_gpkg, driver="GPKG")

    print(f"Writing {segments_csv.name}...")
    export_segment_csv(segment_summary, segments_csv)

    print(f"Writing {coverage_gpkg.name}...")
    coverage_parts.to_file(coverage_gpkg, driver="GPKG")

    print(f"Writing {coverage_csv.name}...")
    export_coverage_csv(coverage_parts, coverage_csv)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadsvi_table(summary.iloc[0]),
        f"table_2_roadsvi_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures: Rscript 2coverage_analysis/2plot_roadsvi_maps.R")
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


if __name__ == "__main__":
    main()

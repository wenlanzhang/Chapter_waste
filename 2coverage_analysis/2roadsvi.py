"""
Road -> SVI coverage at the road-metre level, with optional H3 aggregation.

Each road segment is split into covered and uncovered line parts relative to
nearby SVI panoid buffers. Partially covered segments contribute metre length
to both classes. Covered/uncovered parts are then intersected with an H3 grid
to produce per-cell road-length coverage ratios.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

import sys

_PREP_DIR = Path(__file__).resolve().parent.parent / "1prepare_chapter_data"
if str(_PREP_DIR) not in sys.path:
    sys.path.insert(0, str(_PREP_DIR))
from road_utils import ROAD_FILES
from h3_utils import build_h3_grid, clip_grid_to_city
from thesis_tables import build_roadsvi_table, save_thesis_table

ROAD_GPKG = ROAD_FILES["coverage"]

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "2coverage_analysis"

DEFAULT_SVI_BUFFER_M = 50
DEFAULT_H3_RES = 8
MIN_PART_LENGTH_M = 0.1
DEFAULT_WORKERS = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nairobi road-metre SVI coverage (+ H3 ratios).")
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="SVI buffer distance in metres (default: 50)",
    )
    parser.add_argument(
        "--h3-res",
        type=int,
        default=DEFAULT_H3_RES,
        help="H3 resolution for cell-level coverage ratios (default: 8)",
    )
    parser.add_argument(
        "--h3-only",
        action="store_true",
        help="Skip metre split; aggregate existing Nairobi_roadsvi_coverage_buf*.gpkg to H3",
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


def h3_file_tag(h3_res: int, svi_buffer_m: float) -> str:
    return f"h3_res{h3_res}_buf{int(svi_buffer_m)}m"


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


def compute_h3_metrics(
    coverage_parts: gpd.GeoDataFrame,
    boundary: gpd.GeoDataFrame,
    h3_res: int,
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
    length_stats["svi_coverage_ratio"] = np.where(
        length_stats["road_length_m"] > 0,
        length_stats["covered_road_length_m"] / length_stats["road_length_m"],
        np.nan,
    )
    length_stats["has_road"] = (length_stats["road_length_m"] > 0).astype(int)
    length_stats["has_svi_coverage"] = (length_stats["covered_road_length_m"] > 0).astype(int)

    metrics = metrics.merge(length_stats, on="h3_index", how="left")
    metrics["road_length_m"] = metrics["road_length_m"].fillna(0.0)
    metrics["covered_road_length_m"] = metrics["covered_road_length_m"].fillna(0.0)
    metrics["uncovered_road_length_m"] = metrics["uncovered_road_length_m"].fillna(0.0)
    metrics["has_road"] = metrics["has_road"].fillna(0).astype(int)
    metrics["has_svi_coverage"] = metrics["has_svi_coverage"].fillna(0).astype(int)
    # Keep NaN for road-free cells so choropleths can mask them
    return metrics


def export_h3_csv(metrics: gpd.GeoDataFrame, path: Path) -> None:
    columns = [
        "h3_index",
        "h3_res",
        "cell_area_m2",
        "city_area_m2",
        "in_city",
        "road_length_m",
        "covered_road_length_m",
        "uncovered_road_length_m",
        "svi_coverage_ratio",
        "has_road",
        "has_svi_coverage",
    ]
    metrics[columns].to_csv(path, index=False)


def compute_summary(
    segment_summary: gpd.GeoDataFrame,
    coverage_parts: gpd.GeoDataFrame,
    svi_buffer_m: float,
    svi_count: int,
    h3_metrics: gpd.GeoDataFrame | None = None,
    h3_res: int | None = None,
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

    out = pd.DataFrame([summary])
    if h3_metrics is not None and h3_res is not None:
        out = _attach_h3_to_summary(out, h3_metrics, h3_res)
    return out


def _attach_h3_to_summary(
    summary: pd.DataFrame,
    h3_metrics: gpd.GeoDataFrame,
    h3_res: int,
) -> pd.DataFrame:
    with_road = h3_metrics.loc[h3_metrics["has_road"] == 1]
    summary = summary.copy()
    summary["h3_res"] = h3_res
    summary["h3_cells_in_city"] = len(h3_metrics)
    summary["h3_cells_with_road"] = int(h3_metrics["has_road"].sum())
    summary["h3_cells_with_svi_coverage"] = int(h3_metrics["has_svi_coverage"].sum())
    summary["pct_h3_cells_with_road"] = 100 * h3_metrics["has_road"].mean()
    summary["pct_h3_cells_with_svi_coverage"] = 100 * h3_metrics["has_svi_coverage"].mean()
    summary["mean_h3_svi_coverage_ratio"] = (
        float(with_road["svi_coverage_ratio"].mean()) if len(with_road) else np.nan
    )
    summary["median_h3_svi_coverage_ratio"] = (
        float(with_road["svi_coverage_ratio"].median()) if len(with_road) else np.nan
    )
    return summary


def run_h3_only(args: argparse.Namespace) -> None:
    """Aggregate existing metre-level coverage parts onto H3 without re-splitting."""
    tag = file_tag(args.svi_buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.svi_buffer_m)
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.gpkg"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.csv"

    if not coverage_gpkg.exists():
        raise FileNotFoundError(
            f"Missing {coverage_gpkg.name}. Run without --h3-only first "
            f"(python 2coverage_analysis/2roadsvi.py --svi-buffer-m {int(args.svi_buffer_m)})."
        )

    print(f"SVI buffer: {args.svi_buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")
    print(f"Loading existing coverage: {coverage_gpkg.name}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    coverage_parts = gpd.read_file(coverage_gpkg)

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(coverage_parts, boundary, args.h3_res)

    if summary_csv.exists():
        summary = pd.read_csv(summary_csv)
        summary = _attach_h3_to_summary(summary, h3_metrics, args.h3_res)
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
                    "svi_buffer_m": args.svi_buffer_m,
                    "coverage_part_count": len(coverage_parts),
                    "total_road_length_km": total_m / 1000,
                    "covered_road_length_km": covered_m / 1000,
                    "uncovered_road_length_km": uncovered_m / 1000,
                    "pct_road_length_covered": 100 * covered_m / max(total_m, 1),
                    "pct_road_length_not_covered": 100 * uncovered_m / max(total_m, 1),
                    "svi_panoid_count": np.nan,
                }
            ]
        )
        summary = _attach_h3_to_summary(summary, h3_metrics, args.h3_res)

    print(f"Writing {h3_gpkg.name}...")
    h3_metrics.to_file(h3_gpkg, driver="GPKG")
    print(f"Writing {h3_csv.name}...")
    export_h3_csv(h3_metrics, h3_csv)
    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadsvi_table(summary.iloc[0]),
        f"table_2_roadsvi_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures:")
    print(
        f"  Rscript 2coverage_analysis/2plot_roadsvi_maps.R"
        f" --svi-buffer-m={int(args.svi_buffer_m)} --h3-res={args.h3_res}"
    )
    print("\nSummary")
    if "pct_road_length_covered" in summary.columns:
        print(f"  Road length covered:        {summary['pct_road_length_covered'].iloc[0]:.1f}%")
    print(
        f"  Mean H3 SVI coverage ratio: {summary['mean_h3_svi_coverage_ratio'].iloc[0]:.3f}"
        f" (cells with road)"
    )
    print(
        f"  H3 cells with SVI coverage: {summary['h3_cells_with_svi_coverage'].iloc[0]:,} / "
        f"{summary['h3_cells_in_city'].iloc[0]:,}"
    )


def main() -> None:
    args = parse_args()
    if args.h3_only:
        run_h3_only(args)
        return

    tag = file_tag(args.svi_buffer_m)
    h3_tag = h3_file_tag(args.h3_res, args.svi_buffer_m)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    segments_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.gpkg"
    segments_csv = OUTPUT_DIR / f"Nairobi_roadsvi_segments_{tag}.csv"
    coverage_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.gpkg"
    coverage_csv = OUTPUT_DIR / f"Nairobi_roadsvi_coverage_{tag}.csv"
    summary_csv = OUTPUT_DIR / f"Nairobi_roadsvi_summary_{tag}.csv"
    h3_gpkg = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.gpkg"
    h3_csv = OUTPUT_DIR / f"Nairobi_roadsvi_grid_{h3_tag}.csv"

    print(f"SVI buffer: {args.svi_buffer_m} m")
    print(f"H3 resolution: {args.h3_res}")

    boundary = gpd.read_file(INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg")
    roads = gpd.read_file(INPUT_DIR / ROAD_GPKG)
    svi = gpd.read_file(INPUT_DIR / "Nairobi_SVI_point_gsvi_32737.gpkg")

    print("Preparing road segments...")
    segments = prepare_road_segments(roads)

    print(f"Splitting road coverage by metre ({len(segments):,} segments, {len(svi):,} panoids)...")
    coverage_parts, segment_summary = split_road_coverage(
        segments,
        svi,
        args.svi_buffer_m,
        workers=args.workers,
    )

    print(f"Aggregating coverage to H3 res {args.h3_res}...")
    h3_metrics = compute_h3_metrics(coverage_parts, boundary, args.h3_res)
    summary = compute_summary(
        segment_summary,
        coverage_parts,
        args.svi_buffer_m,
        len(svi),
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
    export_h3_csv(h3_metrics, h3_csv)

    print(f"Writing {summary_csv.name}...")
    summary.to_csv(summary_csv, index=False)

    thesis_path = save_thesis_table(
        build_roadsvi_table(summary.iloc[0]),
        f"table_2_roadsvi_{tag}.csv",
    )
    print(f"Writing {thesis_path.name}...")

    print("\nFigures:")
    print(
        f"  Rscript 2coverage_analysis/2plot_roadsvi_maps.R"
        f" --svi-buffer-m={int(args.svi_buffer_m)} --h3-res={args.h3_res}"
    )
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
    print(
        f"  Mean H3 SVI coverage ratio: {summary['mean_h3_svi_coverage_ratio'].iloc[0]:.3f}"
        f" (cells with road)"
    )
    print(
        f"  H3 cells with SVI coverage: {summary['h3_cells_with_svi_coverage'].iloc[0]:,} / "
        f"{summary['h3_cells_in_city'].iloc[0]:,}"
    )


if __name__ == "__main__":
    main()

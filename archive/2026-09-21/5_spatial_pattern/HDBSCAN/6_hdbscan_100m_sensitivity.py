#!/usr/bin/env python3
"""Experiment 4 sensitivity: HDBSCAN on 100 m positive cells.

Aggregate waste-positive panoramas to 100 m grid cells:
  - cell positive if it contains ≥1 positive panorama
  - one point per positive cell (centroid)
  - run HDBSCAN and compare footprint with panoid-level hotspots

This tests whether clusters persist after reducing dense panorama sampling
and repeated views of the same local site.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg  # noqa: E402
from lib.hdbscan_fit import (  # noqa: E402
    MIN_CLUSTER_SIZE,
    MIN_SAMPLES,
    cluster_convex_hull,
    cluster_labels,
)
from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    load_gsvi_waste_panoids,
)

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"
GRID_GPKG = active_grid_gpkg()

PANOID_HOTSPOT_GPKG = OUTPUT_DIR / "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg"
PANOID_CLUSTERED_GPKG = OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg"

MIN_CLUSTER_SIZE_FLOOR = 10


def run_hdbscan(gdf: gpd.GeoDataFrame, min_cluster_size: int) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out["HDB_cluster"] = cluster_labels(
        gdf,
        min_cluster_size=min_cluster_size,
        min_samples=min(MIN_SAMPLES, min_cluster_size),
    )
    return out


def _union_geom(gdf: gpd.GeoDataFrame):
    if gdf is None or gdf.empty:
        return None
    return unary_union(list(gdf.geometry))


def polygon_union_area_km2(gdf: gpd.GeoDataFrame) -> float:
    geom = _union_geom(gdf)
    if geom is None or geom.is_empty:
        return 0.0
    return float(geom.area / 1e6)


def overlap_metrics(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> dict:
    ua = _union_geom(a)
    ub = _union_geom(b)
    if ua is None or ua.is_empty or ub is None or ub.is_empty:
        return {
            "intersection_km2": 0.0,
            "union_km2": 0.0,
            "jaccard": np.nan,
            "a_only_km2": polygon_union_area_km2(a),
            "b_only_km2": polygon_union_area_km2(b),
        }
    inter = ua.intersection(ub).area / 1e6
    union = ua.union(ub).area / 1e6
    a_only = ua.difference(ub).area / 1e6
    b_only = ub.difference(ua).area / 1e6
    return {
        "intersection_km2": float(inter),
        "union_km2": float(union),
        "jaccard": float(inter / union) if union > 0 else np.nan,
        "a_only_km2": float(a_only),
        "b_only_km2": float(b_only),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("100 m-cell HDBSCAN sensitivity (panorama → cell)...")
    print(f"  Grid: {GRID_GPKG}")
    grid = gpd.read_file(GRID_GPKG)
    if grid.crs is None or grid.crs.to_epsg() != 32737:
        grid = grid.to_crs(epsg=32737)

    waste = load_gsvi_waste_panoids()
    try:
        joined = gpd.sjoin(waste, grid[["geometry"]], how="inner", predicate="within")
    except TypeError:
        joined = gpd.sjoin(waste, grid[["geometry"]], how="inner", op="within")
    if "index_right" not in joined.columns:
        raise SystemExit("Spatial join to grid failed (no index_right).")

    cell_ids = joined.groupby("index_right").size().rename("n_positive_panoramas")
    positive_cells = grid.loc[cell_ids.index].copy()
    positive_cells["n_positive_panoramas"] = cell_ids.to_numpy()
    positive_cells["geometry"] = positive_cells.geometry.centroid
    positive_cells = positive_cells.reset_index(drop=True)

    n_cells = len(positive_cells)
    min_cluster_size = MIN_CLUSTER_SIZE
    if n_cells < MIN_CLUSTER_SIZE * 4:
        min_cluster_size = max(MIN_CLUSTER_SIZE_FLOOR, n_cells // 20)
    print(f"  Positive cells: {n_cells:,} | min_cluster_size={min_cluster_size}")

    clustered = run_hdbscan(positive_cells, min_cluster_size=min_cluster_size)
    labels = clustered["HDB_cluster"].to_numpy()
    n_noise = int((labels == -1).sum())
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    clustered_path = OUTPUT_DIR / "Nairobi_waste_hdbscan_100m_cells_32737.gpkg"
    clustered.to_file(clustered_path, driver="GPKG")

    hulls = cluster_convex_hull(clustered)
    hull_path = OUTPUT_DIR / "Nairobi_waste_hotspot_polygons_100m_cells_32737.gpkg"
    hulls.to_file(hull_path, driver="GPKG")

    # Compare with panoid-level hotspot polygons if available
    if PANOID_HOTSPOT_GPKG.exists():
        panoid_hulls = gpd.read_file(PANOID_HOTSPOT_GPKG)
    elif PANOID_CLUSTERED_GPKG.exists():
        panoid_pts = gpd.read_file(PANOID_CLUSTERED_GPKG)
        panoid_hulls = cluster_convex_hull(panoid_pts)
    else:
        panoid_hulls = gpd.GeoDataFrame(geometry=[], crs=clustered.crs)

    ov = overlap_metrics(panoid_hulls, hulls)
    summary = {
        "unit": "100m_positive_cell_centroid",
        "grid_source": str(GRID_GPKG.name),
        "n_positive_panoramas": int(len(waste)),
        "n_positive_cells": n_cells,
        "min_cluster_size": min_cluster_size,
        "min_samples": min(MIN_SAMPLES, min_cluster_size),
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "noise_ratio": n_noise / n_cells if n_cells else np.nan,
        "hotspot_area_km2_sum_hulls": float(hulls["area_km2"].sum())
        if len(hulls)
        else 0.0,
        "hotspot_area_km2_union": polygon_union_area_km2(hulls),
        "panoid_hotspot_area_km2_union": polygon_union_area_km2(panoid_hulls),
        "overlap_intersection_km2": ov["intersection_km2"],
        "overlap_union_km2": ov["union_km2"],
        "jaccard_vs_panoid_hotspots": ov["jaccard"],
        "panoid_only_km2": ov["a_only_km2"],
        "cell_only_km2": ov["b_only_km2"],
    }
    summary_path = OUTPUT_DIR / "Nairobi_hdbscan_100m_sensitivity_summary.csv"
    pd.DataFrame([summary]).to_csv(summary_path, index=False)

    thesis = pd.DataFrame(
        [
            ("Positive panoramas (input)", f"{summary['n_positive_panoramas']:,}", ""),
            ("Positive 100 m cells", f"{summary['n_positive_cells']:,}", ""),
            ("min_cluster_size", str(min_cluster_size), ""),
            ("Clusters", str(n_clusters), ""),
            ("Noise cells", f"{n_noise:,}", ""),
            (
                "Hotspot union area (100 m cells)",
                f"{summary['hotspot_area_km2_union']:.3f}",
                "km²",
            ),
            (
                "Hotspot union area (panoid HDBSCAN)",
                f"{summary['panoid_hotspot_area_km2_union']:.3f}",
                "km²",
            ),
            (
                "Jaccard overlap vs panoid hotspots",
                f"{ov['jaccard']:.3f}" if pd.notna(ov["jaccard"]) else "",
                "",
            ),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / "table_hdbscan_100m_sensitivity.csv"
    thesis.to_csv(thesis_path, index=False)

    print(f"  Clusters: {n_clusters} | noise: {n_noise:,}")
    print(
        f"  Jaccard vs panoid hotspots: "
        f"{ov['jaccard']:.3f}" if pd.notna(ov["jaccard"]) else "  Jaccard: n/a"
    )
    print(f"Wrote {clustered_path}")
    print(f"Wrote {hull_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

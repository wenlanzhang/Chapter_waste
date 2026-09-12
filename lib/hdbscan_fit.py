"""Shared HDBSCAN settings and clustering helpers (Step 5)."""

from __future__ import annotations

import geopandas as gpd
import hdbscan
import numpy as np
from shapely.geometry import MultiPoint

MIN_CLUSTER_SIZE = 25
MIN_SAMPLES = 6


def cluster_labels(
    gdf: gpd.GeoDataFrame,
    *,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    min_samples: int | None = None,
) -> np.ndarray:
    coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    ms = MIN_SAMPLES if min_samples is None else min_samples
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min(ms, min_cluster_size),
        gen_min_span_tree=True,
    )
    return clusterer.fit_predict(coords)


def cluster_points(
    gdf: gpd.GeoDataFrame,
    *,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    min_samples: int | None = None,
    unit: str = "panorama_location",
) -> tuple[gpd.GeoDataFrame, dict]:
    """Fit HDBSCAN and return clustered points plus a summary dict."""
    labels = cluster_labels(
        gdf, min_cluster_size=min_cluster_size, min_samples=min_samples
    )
    out = gdf.copy()
    out["HDB_cluster"] = labels

    n_pts = int(len(labels))
    n_noise = int((labels == -1).sum())
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_clustered = n_pts - n_noise
    ms = MIN_SAMPLES if min_samples is None else min_samples
    summary = {
        "min_cluster_size": min_cluster_size,
        "min_samples": min(ms, min_cluster_size),
        "n_points": n_pts,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "n_clustered": n_clustered,
        "pct_waste_points_clustered": 100.0 * n_clustered / n_pts if n_pts else np.nan,
        "noise_ratio": n_noise / n_pts if n_pts else np.nan,
        "unit": unit,
    }
    return out, summary


def cluster_convex_hull(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    clustered = gdf[gdf["HDB_cluster"] != -1].copy()
    if clustered.empty:
        return gpd.GeoDataFrame(
            columns=["HDB_cluster", "n_points", "area_m2", "area_km2", "geometry"],
            geometry="geometry",
            crs=gdf.crs,
        )

    def hull(geoms: gpd.GeoSeries) -> object:
        points = list(geoms)
        if len(points) == 1:
            return points[0].buffer(1.0)
        hull_geom = MultiPoint(points).convex_hull
        if hull_geom.area == 0:
            return hull_geom.buffer(1.0)
        return hull_geom

    polys = (
        clustered.groupby("HDB_cluster")["geometry"]
        .apply(hull)
        .reset_index(name="geometry")
    )
    polys = gpd.GeoDataFrame(polys, geometry="geometry", crs=gdf.crs)
    polys["n_points"] = clustered.groupby("HDB_cluster").size().values
    polys["area_m2"] = polys.geometry.area
    polys["area_km2"] = polys["area_m2"] / 1e6
    return polys

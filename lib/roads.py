"""Shared road-network cleaning and comparison helpers."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import get_parts, node

PROJECTED_CRS = "EPSG:32737"
WGS84 = "EPSG:4326"

ROAD_FILES = {
    "local_raw": "Nairobi_road_01_local_raw_32737.gpkg",
    "osmnx_raw": "Nairobi_road_02_osmnx_raw_32737.gpkg",
    "local_cleaned": "Nairobi_road_03_local_cleaned_32737.gpkg",
    "local_noded": "Nairobi_road_03_local_noded_32737.gpkg",
    "osmnx_cleaned": "Nairobi_road_04_osmnx_cleaned_32737.gpkg",
    # Step-2 coverage scripts (1cityroad, 2roadsvi, plot_process_zoom_map)
    "coverage": "Nairobi_road_03_local_cleaned_32737.gpkg",
    "comparison": "Nairobi_road_05_cleaned_comparison_32737.gpkg",
    "local_cleaned_legacy": "Nairobi_road_line_32737.gpkg",
    "osmnx_cleaned_legacy": "Nairobi_road_line_OSMnx_32737.gpkg",
}


def normalize_highway(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "unknown"
    if isinstance(value, list):
        return str(value[0])
    return str(value)


def normalize_name(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def clean_road_segments(roads: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    OSMnx-aligned cleaning for line GeoDataFrames:
      explode multipart lines -> clip to boundary -> project -> standardise schema
    """
    type_col = "highway" if "highway" in roads.columns else "type"
    osm_col = "osmid" if "osmid" in roads.columns else "osm_id" if "osm_id" in roads.columns else None

    segments = roads.explode(index_parts=False).reset_index(drop=True)
    segments = segments[~segments.geometry.is_empty].copy()
    segments = gpd.clip(segments, boundary.to_crs(segments.crs))
    segments = segments.to_crs(PROJECTED_CRS)
    segments = segments[segments.geometry.length > 0].copy()

    out = gpd.GeoDataFrame(
        {
            "segment_id": segments.index,
            "osm_id": segments[osm_col] if osm_col else segments.index,
            "name": segments["name"].map(normalize_name) if "name" in segments.columns else None,
            "type": segments[type_col].map(normalize_highway),
            "length_m": segments.geometry.length,
        },
        geometry=segments.geometry,
        crs=PROJECTED_CRS,
    )
    return out[out.geometry.length > 0].reset_index(drop=True)


def node_road_segments(roads: gpd.GeoDataFrame, min_length_m: float = 0.1) -> gpd.GeoDataFrame:
    """
    Intersection-based segmentation (planar noding).

    Typical process:
      1. Start from cleaned line geometries (projected, clipped).
      2. Node the network: split every line at all intersection / touch points
         (Shapely ``node`` — equivalent to PostGIS ST_Node).
      3. Each resulting line between two junctions becomes one segment.
      4. Transfer OSM attributes from source lines via longest overlap.

    This differs from geometry-based cleaning, where one OSM way often stays
    one row even when it crosses multiple intersections.
    """
    lines = roads.explode(index_parts=False).reset_index(drop=True)
    lines = lines[~lines.geometry.is_empty & lines.geometry.length > 0].copy()

    attr_cols = [c for c in ["osm_id", "type", "name"] if c in lines.columns]
    source = lines[["geometry", *attr_cols]].copy()

    noded_parts = list(get_parts(node(lines.geometry.union_all())))
    noded = gpd.GeoDataFrame({"segment_id": range(len(noded_parts)), "geometry": noded_parts}, crs=lines.crs)
    noded = noded[noded.geometry.length >= min_length_m].copy().reset_index(drop=True)
    noded["segment_id"] = noded.index
    noded["length_m"] = noded.geometry.length

    overlap = gpd.overlay(
        noded[["segment_id", "geometry"]],
        source,
        how="intersection",
        keep_geom_type=True,
    )
    overlap["ovl_len"] = overlap.geometry.length
    best = overlap.loc[overlap.groupby("segment_id")["ovl_len"].idxmax(), ["segment_id", *attr_cols]]

    out = noded.merge(best, on="segment_id", how="left")
    missing_ids = out.loc[out["type"].isna(), "segment_id"]
    if len(missing_ids):
        nearest = gpd.sjoin_nearest(
            out.loc[out["segment_id"].isin(missing_ids), ["segment_id", "geometry"]],
            source,
            how="left",
        )
        fill = nearest.drop_duplicates("segment_id").set_index("segment_id")
        for col in attr_cols:
            out[col] = out[col].fillna(out["segment_id"].map(fill[col]))
        out["type"] = out["type"].fillna("unknown")

    out = gpd.GeoDataFrame(
        {
            "segment_id": out["segment_id"],
            "osm_id": out["osm_id"] if "osm_id" in out.columns else out["segment_id"],
            "name": out["name"] if "name" in out.columns else None,
            "type": out["type"].map(normalize_highway),
            "length_m": out["length_m"],
        },
        geometry=out.geometry,
        crs=roads.crs,
    )
    return out[out.geometry.length > 0].reset_index(drop=True)


def prepare_raw_local(roads: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clip local OSM extract to boundary and project (no explode / simplify)."""
    clipped = gpd.clip(roads, boundary)
    clipped = clipped.to_crs(PROJECTED_CRS)
    clipped = clipped[clipped.geometry.length > 0].copy().reset_index(drop=True)
    clipped["segment_id"] = clipped.index
    clipped["length_m"] = clipped.geometry.length
    return clipped


def prepare_raw_osmnx_edges(edges: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Minimal processing for OSMnx graph edges before simplify."""
    type_col = "highway" if "highway" in edges.columns else "type"
    osm_col = "osmid" if "osmid" in edges.columns else "osm_id" if "osm_id" in edges.columns else None

    segments = edges.explode(index_parts=False).reset_index(drop=True)
    segments = segments[segments.geometry.length > 0].copy()
    segments = gpd.clip(segments, boundary.to_crs(segments.crs))
    segments = segments.to_crs(PROJECTED_CRS)

    out = gpd.GeoDataFrame(
        {
            "segment_id": segments.index,
            "osm_id": segments[osm_col] if osm_col else segments.index,
            "type": segments[type_col].map(normalize_highway) if type_col in segments.columns else "unknown",
            "length_m": segments.geometry.length,
        },
        geometry=segments.geometry,
        crs=PROJECTED_CRS,
    )
    return out[out.geometry.length > 0].reset_index(drop=True)


def build_cleaned_comparison(
    local: gpd.GeoDataFrame, osmnx: gpd.GeoDataFrame
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Classify cleaned segments: overlap, local_only, osmnx_only."""
    local = local.reset_index(drop=True)
    osmnx = osmnx.reset_index(drop=True)

    local_hits = gpd.sjoin(
        local[["segment_id", "geometry"]],
        osmnx[["geometry"]],
        how="inner",
        predicate="intersects",
    )["segment_id"].unique()

    osmnx_hits = gpd.sjoin(
        osmnx[["segment_id", "geometry"]],
        local[["geometry"]],
        how="inner",
        predicate="intersects",
    )["segment_id"].unique()

    overlap = local[local["segment_id"].isin(local_hits)].copy()
    overlap["coverage_class"] = "overlap"

    local_only = local[~local["segment_id"].isin(local_hits)].copy()
    local_only["coverage_class"] = "local_only"

    osmnx_only = osmnx[~osmnx["segment_id"].isin(osmnx_hits)].copy()
    osmnx_only["coverage_class"] = "osmnx_only"

    comparison = pd.concat([overlap, local_only, osmnx_only], ignore_index=True)

    summary = pd.DataFrame(
        [
            {
                "class": "overlap",
                "segment_count": len(overlap),
                "length_km": overlap["length_m"].sum() / 1000,
                "pct_local_segments": 100 * len(overlap) / max(len(local), 1),
                "pct_osmnx_segments": 100 * len(overlap) / max(len(osmnx), 1),
            },
            {
                "class": "local_only",
                "segment_count": len(local_only),
                "length_km": local_only["length_m"].sum() / 1000,
                "pct_local_segments": 100 * len(local_only) / max(len(local), 1),
                "pct_osmnx_segments": 0.0,
            },
            {
                "class": "osmnx_only",
                "segment_count": len(osmnx_only),
                "length_km": osmnx_only["length_m"].sum() / 1000,
                "pct_local_segments": 0.0,
                "pct_osmnx_segments": 100 * len(osmnx_only) / max(len(osmnx), 1),
            },
        ]
    )

    return comparison, summary


def composition_table(roads: gpd.GeoDataFrame, source: str) -> pd.DataFrame:
    grouped = (
        roads.groupby("type", as_index=False)
        .agg(segment_count=("segment_id", "count"), length_m=("length_m", "sum"))
        .assign(
            source=source,
            length_km=lambda df: df["length_m"] / 1000,
            pct_length=lambda df: 100 * df["length_m"] / df["length_m"].sum(),
            pct_count=lambda df: 100 * df["segment_count"] / df["segment_count"].sum(),
        )
        .sort_values("length_m", ascending=False)
    )
    return grouped


def compare_road_networks(local: gpd.GeoDataFrame, osmnx: gpd.GeoDataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    local_comp = composition_table(local, "local")
    osmnx_comp = composition_table(osmnx, "osmnx")

    type_comparison = pd.merge(
        local_comp[["type", "source", "segment_count", "length_km", "pct_length", "pct_count"]],
        osmnx_comp[["type", "segment_count", "length_km", "pct_length", "pct_count"]],
        on="type",
        how="outer",
        suffixes=("_local", "_osmnx"),
    ).fillna(0)
    type_comparison["pct_length_diff"] = (
        type_comparison["pct_length_osmnx"] - type_comparison["pct_length_local"]
    )

    summary = pd.DataFrame(
        [
            {
                "metric": "segment_count",
                "local": len(local),
                "osmnx": len(osmnx),
                "diff_osmnx_minus_local": len(osmnx) - len(local),
                "pct_diff": 100 * (len(osmnx) - len(local)) / max(len(local), 1),
            },
            {
                "metric": "total_length_km",
                "local": local["length_m"].sum() / 1000,
                "osmnx": osmnx["length_m"].sum() / 1000,
                "diff_osmnx_minus_local": (osmnx["length_m"].sum() - local["length_m"].sum()) / 1000,
                "pct_diff": 100
                * (osmnx["length_m"].sum() - local["length_m"].sum())
                / max(local["length_m"].sum(), 1),
            },
            {
                "metric": "road_type_count",
                "local": local["type"].nunique(),
                "osmnx": osmnx["type"].nunique(),
                "diff_osmnx_minus_local": osmnx["type"].nunique() - local["type"].nunique(),
                "pct_diff": 100
                * (osmnx["type"].nunique() - local["type"].nunique())
                / max(local["type"].nunique(), 1),
            },
        ]
    )

    composition_long = pd.concat([local_comp, osmnx_comp], ignore_index=True)
    return summary, type_comparison, composition_long


DEFAULT_SVI_ON_ROAD_THRESHOLDS_M = (10, 25, 50)


def analyze_svi_on_road_network(
    svi: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    source: str,
    on_road_thresholds_m: tuple[float, ...] = DEFAULT_SVI_ON_ROAD_THRESHOLDS_M,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """
    Measure distance from each SVI panoid to the nearest road segment.

    Returns per-panoid snap distances and a one-row summary table.
    """
    id_col = "panoid" if "panoid" in svi.columns else None
    if id_col is None:
        raise ValueError("SVI GeoDataFrame must include a 'panoid' column.")

    roads = roads[roads.geometry.length > 0].copy()
    svi_pts = svi[[id_col, "geometry"]].dropna(subset=[id_col]).to_crs(roads.crs)
    svi_pts = svi_pts.drop_duplicates(subset=[id_col], keep="first").reset_index(drop=True)

    nearest = gpd.sjoin_nearest(
        svi_pts,
        roads[["segment_id", "geometry"]],
        how="left",
        distance_col="dist_to_road_m",
    )
    snapped = (
        nearest.groupby(id_col, as_index=False)
        .agg(
            dist_to_road_m=("dist_to_road_m", "min"),
            nearest_segment_id=("segment_id", "first"),
        )
        .rename(columns={id_col: "panoid"})
    )
    snapped["road_source"] = source

    max_threshold = max(on_road_thresholds_m)
    summary: dict[str, object] = {
        "road_source": source,
        "svi_panoid_count": len(svi_pts),
        "mean_dist_to_road_m": snapped["dist_to_road_m"].mean(),
        "median_dist_to_road_m": snapped["dist_to_road_m"].median(),
        "max_dist_to_road_m": snapped["dist_to_road_m"].max(),
    }
    for threshold_m in on_road_thresholds_m:
        key = f"within_{int(threshold_m)}m"
        count = int((snapped["dist_to_road_m"] <= threshold_m).sum())
        summary[f"panoids_{key}"] = count
        summary[f"pct_{key}"] = 100 * count / max(len(svi_pts), 1)

    off_network = snapped["dist_to_road_m"] > max_threshold
    summary["panoids_off_network"] = int(off_network.sum())
    summary["pct_off_network"] = 100 * off_network.sum() / max(len(svi_pts), 1)
    summary["all_on_network"] = int(off_network.sum() == 0)

    return snapped, pd.DataFrame([summary])


def compare_svi_on_road_networks(
    svi: gpd.GeoDataFrame,
    local: gpd.GeoDataFrame,
    osmnx: gpd.GeoDataFrame,
    on_road_thresholds_m: tuple[float, ...] = DEFAULT_SVI_ON_ROAD_THRESHOLDS_M,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    """Snap SVI panoids to local and OSMnx cleaned road networks."""
    local_snapped, local_summary = analyze_svi_on_road_network(
        svi, local, "local_cleaned", on_road_thresholds_m
    )
    osmnx_snapped, osmnx_summary = analyze_svi_on_road_network(
        svi, osmnx, "osmnx_cleaned", on_road_thresholds_m
    )
    comparison = pd.concat([local_summary, osmnx_summary], ignore_index=True)
    return local_snapped, osmnx_snapped, comparison

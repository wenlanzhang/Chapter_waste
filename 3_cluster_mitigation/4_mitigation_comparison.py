"""
4. Compare HDBSCAN mitigation metrics: Google SVI vs GSVI + self-collected.

Field photos = self-collected imagery (Faith/ + ZWL/) added to Google SVI waste
detections. Hotspot area is the sum of per-cluster convex-hull polygon areas
(EPSG:32737), excluding noise points.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import hdbscan
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_cluster_mitigation"

GSVI_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
GSVI_SELF_COLLECTED_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg"
BOUNDARY_GPKG = INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg"

MIN_CLUSTER_SIZE = 25
MIN_SAMPLES = 6

ARMS = {
    "gsvi": {
        "column": "Google SVI",
        "label": "Google SVI (GSVI only)",
        "clustered_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        "hotspot_gpkg": OUTPUT_DIR / "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg",
    },
    "gsvi_selfcollected": {
        "column": "GSVI + self-collected",
        "label": "GSVI + self-collected (Faith/ + ZWL/)",
        "clustered_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        "hotspot_gpkg": OUTPUT_DIR / "Nairobi_waste_hotspot_polygons_gsvi_selfcollected_32737.gpkg",
    },
}

TABLE_DIR = OUTPUT_DIR / "thesis_table"
TABLE_PATH = TABLE_DIR / "Nairobi_mitigation_comparison_table.csv"
NEW_OBS_TABLE_PATH = TABLE_DIR / "Nairobi_mitigation_new_observations_table.csv"

HOTSPOT_OVERLAP_FRAC = 0.30

LEGACY_CLUSTERED_GPKGS = {
    "gsvi_selfcollected": [
        OUTPUT_DIR / "Nairobi_waste_hdbscan_all_32737.gpkg",
        OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_field_32737.gpkg",
    ],
}


def load_gsvi_waste() -> gpd.GeoDataFrame:
    return gpd.read_file(GSVI_GPKG)


def load_gsvi_selfcollected_waste() -> gpd.GeoDataFrame:
    return gpd.read_file(GSVI_SELF_COLLECTED_GPKG)


def run_hdbscan(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        gen_min_span_tree=True,
    )
    out = gdf.copy()
    out["HDB_cluster"] = clusterer.fit_predict(coords)
    return out


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
        return MultiPoint(points).convex_hull

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


def compute_metrics(clustered_gdf: gpd.GeoDataFrame) -> dict:
    labels = clustered_gdf["HDB_cluster"]
    n_total = len(clustered_gdf)
    n_noise = int((labels == -1).sum())
    n_clustered = n_total - n_noise
    n_hotspots = len(set(labels) - {-1})

    hotspot_polys = cluster_convex_hull(clustered_gdf)
    total_area_km2 = float(hotspot_polys["area_km2"].sum()) if len(hotspot_polys) else 0.0

    return {
        "waste_observations": n_total,
        "clustered_observations": n_clustered,
        "noise_observations": n_noise,
        "number_of_hotspots": n_hotspots,
        "total_hotspot_area_km2": total_area_km2,
        "hotspot_polygons": hotspot_polys,
    }


def format_count(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:,.3f}"
    return f"{int(value):,}"


def format_change(gsvi_val: float, selfcollected_val: float, *, area: bool = False) -> str:
    delta = selfcollected_val - gsvi_val
    if area:
        return f"{delta:+.3f}"
    return f"{int(round(delta)):+,}"


def format_change_percent(gsvi_val: float, selfcollected_val: float) -> str:
    if gsvi_val == 0:
        return "—"
    pct = 100.0 * (selfcollected_val - gsvi_val) / gsvi_val
    return f"{pct:+.1f}%"


def build_comparison_table(gsvi: dict, selfcollected: dict) -> pd.DataFrame:
    rows = [
        (
            "Waste observations",
            gsvi["waste_observations"],
            selfcollected["waste_observations"],
            False,
        ),
        (
            "Clustered observations",
            gsvi["clustered_observations"],
            selfcollected["clustered_observations"],
            False,
        ),
        (
            "Noise observations",
            gsvi["noise_observations"],
            selfcollected["noise_observations"],
            False,
        ),
        (
            "Number of hotspots",
            gsvi["number_of_hotspots"],
            selfcollected["number_of_hotspots"],
            False,
        ),
        (
            "Total hotspot area (km²)",
            gsvi["total_hotspot_area_km2"],
            selfcollected["total_hotspot_area_km2"],
            True,
        ),
    ]

    records = []
    for metric, gsvi_val, selfcollected_val, is_area in rows:
        records.append(
            {
                "Metric": metric,
                ARMS["gsvi"]["column"]: format_count(gsvi_val),
                ARMS["gsvi_selfcollected"]["column"]: format_count(selfcollected_val),
                "Change": format_change(gsvi_val, selfcollected_val, area=is_area),
                "Change percent": format_change_percent(gsvi_val, selfcollected_val),
            }
        )
    return pd.DataFrame(records)


def observation_keys(gdf: gpd.GeoDataFrame) -> pd.Series:
    attrs = gdf.drop(columns="geometry").reset_index(drop=True)
    if "img_name" in attrs.columns:
        return pd.Series(
            zip(
                attrs["lat"].round(6),
                attrs["lon"].round(6),
                attrs["img_name"].astype(str),
            )
        )
    coords = gdf.geometry
    return pd.Series(zip(coords.x.round(3), coords.y.round(3)))


def extract_new_observations(
    gsvi_gdf: gpd.GeoDataFrame, selfcollected_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    gsvi_keys = set(observation_keys(gsvi_gdf))
    mask = ~observation_keys(selfcollected_gdf).isin(gsvi_keys)
    return selfcollected_gdf.loc[mask].copy()


def count_inside_existing_hotspots(
    new_obs: gpd.GeoDataFrame, gsvi_hulls: gpd.GeoDataFrame
) -> tuple[int, int]:
    if new_obs.empty or gsvi_hulls.empty:
        return 0, len(new_obs)

    joined = gpd.sjoin(
        new_obs,
        gsvi_hulls[["geometry"]],
        how="left",
        predicate="intersects",
    )
    inside_idx = joined.index[joined.index_right.notna()].unique()
    n_inside = len(inside_idx)
    return n_inside, len(new_obs) - n_inside


def match_hotspots(
    gsvi_hulls: gpd.GeoDataFrame, selfcollected_hulls: gpd.GeoDataFrame
) -> tuple[int, int]:
    """Return (retained gsvi hotspots, newly created self-collected hotspots)."""
    if gsvi_hulls.empty:
        return 0, len(selfcollected_hulls)
    if selfcollected_hulls.empty:
        return 0, 0

    retained = 0
    for gsvi_geom in gsvi_hulls.geometry:
        best_overlap = 0.0
        for selfcollected_geom in selfcollected_hulls.geometry:
            inter = gsvi_geom.intersection(selfcollected_geom)
            if inter.is_empty:
                continue
            best_overlap = max(best_overlap, inter.area / gsvi_geom.area)
        if best_overlap >= HOTSPOT_OVERLAP_FRAC:
            retained += 1

    newly_created = 0
    for selfcollected_geom in selfcollected_hulls.geometry:
        best_overlap = 0.0
        for gsvi_geom in gsvi_hulls.geometry:
            inter = selfcollected_geom.intersection(gsvi_geom)
            if inter.is_empty:
                continue
            best_overlap = max(best_overlap, inter.area / selfcollected_geom.area)
        if best_overlap < HOTSPOT_OVERLAP_FRAC:
            newly_created += 1

    return retained, newly_created


def format_share(part: int, whole: int) -> str:
    if whole == 0:
        return "0 (0.0%)"
    return f"{part:,} ({100.0 * part / whole:.1f}%)"


def build_new_observations_table(
    gsvi_gdf: gpd.GeoDataFrame,
    selfcollected_gdf: gpd.GeoDataFrame,
    gsvi_hulls: gpd.GeoDataFrame,
    selfcollected_hulls: gpd.GeoDataFrame,
) -> pd.DataFrame:
    new_obs = extract_new_observations(gsvi_gdf, selfcollected_gdf)
    n_new = len(new_obs)
    n_inside, n_outside = count_inside_existing_hotspots(new_obs, gsvi_hulls)
    n_gsvi_hotspots = len(gsvi_hulls)
    n_retained, n_new_hotspots = match_hotspots(gsvi_hulls, selfcollected_hulls)

    retained_pct = 100.0 * n_retained / n_gsvi_hotspots if n_gsvi_hotspots else 0.0

    return pd.DataFrame(
        [
            {"Metric": "New observations added", "Value": f"{n_new:,}"},
            {
                "Metric": "New observations inside existing hotspots",
                "Value": format_share(n_inside, n_new),
            },
            {
                "Metric": "New observations forming new hotspots",
                "Value": format_share(n_outside, n_new),
            },
            {
                "Metric": "Existing hotspots retained",
                "Value": f"{n_retained} / {n_gsvi_hotspots} ({retained_pct:.1f}%)",
            },
            {"Metric": "Newly created hotspots", "Value": f"{n_new_hotspots:,}"},
        ]
    )


def read_clustered_gdf(key: str) -> gpd.GeoDataFrame | None:
    meta = ARMS[key]
    candidates = [meta["clustered_gpkg"]]
    if key in LEGACY_CLUSTERED_GPKGS:
        candidates.extend(
            path for path in LEGACY_CLUSTERED_GPKGS[key] if path != meta["clustered_gpkg"]
        )
    for path in candidates:
        if path.exists():
            return gpd.read_file(path)
    return None


def ensure_clustered_gdf(key: str) -> gpd.GeoDataFrame:
    meta = ARMS[key]
    existing = read_clustered_gdf(key)
    if existing is not None:
        return existing

    if key == "gsvi":
        waste = load_gsvi_waste()
    else:
        waste = load_gsvi_selfcollected_waste()

    clustered = run_hdbscan(waste)
    clustered.to_file(meta["clustered_gpkg"], driver="GPKG")
    return clustered


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Computing mitigation comparison (Google SVI vs GSVI + self-collected)...")
    gsvi_gdf = ensure_clustered_gdf("gsvi")
    selfcollected_gdf = ensure_clustered_gdf("gsvi_selfcollected")

    gsvi_metrics = compute_metrics(gsvi_gdf)
    selfcollected_metrics = compute_metrics(selfcollected_gdf)

    gsvi_metrics["hotspot_polygons"].to_file(ARMS["gsvi"]["hotspot_gpkg"], driver="GPKG")
    selfcollected_metrics["hotspot_polygons"].to_file(
        ARMS["gsvi_selfcollected"]["hotspot_gpkg"], driver="GPKG"
    )

    table = build_comparison_table(gsvi_metrics, selfcollected_metrics)
    table.to_csv(TABLE_PATH, index=False)

    new_obs_table = build_new_observations_table(
        gsvi_gdf,
        selfcollected_gdf,
        gsvi_metrics["hotspot_polygons"],
        selfcollected_metrics["hotspot_polygons"],
    )
    new_obs_table.to_csv(NEW_OBS_TABLE_PATH, index=False)

    print(f"Wrote {TABLE_PATH}")
    print(f"Wrote {NEW_OBS_TABLE_PATH}")
    print(f"Wrote {ARMS['gsvi']['hotspot_gpkg']}")
    print(f"Wrote {ARMS['gsvi_selfcollected']['hotspot_gpkg']}")
    print()
    print(table.to_string(index=False))
    print()
    print(new_obs_table.to_string(index=False))


if __name__ == "__main__":
    main()

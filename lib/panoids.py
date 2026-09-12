"""Panorama-level waste locations for Step 5 spatial pattern analysis.

GSVI arm: waste-positive panoids from Step 2c (Nairobi_sviwaste_points.gpkg).
GSVI + self-collected: those panoids plus Faith/ZWL waste locations (no panoid).

Primary spatial unit is the panorama (panoid): Y=1 if at least one directional
image is waste-positive. n_positive_views is retained for sensitivity only.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

from chapter_paths import coverage_dir, pattern_dir, phd_data_root, prep_dir, waste_raw_dir

DATA_ROOT = phd_data_root()
CHAPTER_DIR = DATA_ROOT / "Chapter_waste"
INPUT_DIR = prep_dir()
COVERAGE_DIR = coverage_dir()
PATTERN_DIR = pattern_dir()

SVIWASTE_GPKG = COVERAGE_DIR / "Nairobi_sviwaste_points.gpkg"
WASTE_GSVI_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
WASTE_SELF_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg"
BOUNDARY_GPKG = INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg"
SLUM_GPKG = INPUT_DIR / "Nairobi_slum_polygon_32737.gpkg"
SVI_CSV = waste_raw_dir() / "img" / "Combined_SVI.csv"

SELF_SOURCES = {"Faith", "ZWL"}
EXCLUDED_IMG_DIRS = {"ZWL/", "Faith/"}


def _ensure_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


def load_sviwaste_points() -> gpd.GeoDataFrame:
    return _ensure_32737(gpd.read_file(SVIWASTE_GPKG))


def load_n_positive_views() -> pd.Series:
    """Count of waste-positive directional images per panoid (sensitivity only)."""
    waste = gpd.read_file(WASTE_GSVI_GPKG)
    waste = waste.dropna(subset=["panoid"])
    counts = waste.groupby(waste["panoid"].astype(str)).size()
    counts.name = "n_positive_views"
    return counts


def load_panoid_year_map() -> pd.Series:
    """Capture year per panoid from Combined_SVI (first Google row; GSVI only)."""
    df = pd.read_csv(SVI_CSV, usecols=["panoid", "year", "img_dir"], low_memory=False)
    df = df[~df["img_dir"].isin(EXCLUDED_IMG_DIRS)].dropna(subset=["panoid"])
    df["panoid"] = df["panoid"].astype(str)
    df = df.drop_duplicates(subset=["panoid"], keep="first")
    years = pd.to_numeric(df["year"], errors="coerce")
    out = pd.Series(years.to_numpy(), index=df["panoid"].to_numpy(), name="year")
    return out


def enrich_sviwaste_frame(
    sviwaste: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """One row per GSVI panoid with waste_positive, year, n_positive_views."""
    points = sviwaste if sviwaste is not None else load_sviwaste_points()
    out = points.copy()
    out["panoid"] = out["panoid"].astype(str)

    year_map = load_panoid_year_map()
    out["year"] = out["panoid"].map(year_map)

    n_views = load_n_positive_views()
    out["n_positive_views"] = out["panoid"].map(n_views).fillna(0).astype(int)
    # Non-positive panoramas must have zero positive views
    out.loc[out["waste_positive"] != 1, "n_positive_views"] = 0
    return out


def _sjoin_within(left: gpd.GeoDataFrame, right: gpd.GeoDataFrame, how: str = "left"):
    """geopandas compatibility: predicate= (new) vs op= (old)."""
    try:
        return gpd.sjoin(left, right, how=how, predicate="within")
    except TypeError:
        return gpd.sjoin(left, right, how=how, op="within")


def label_inside_settlement(
    points: gpd.GeoDataFrame, slums: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Binary inside/outside mapped urban-poor settlements (panorama unit)."""
    slum_union = gpd.GeoDataFrame(
        geometry=[unary_union(slums.geometry)],
        crs=slums.crs,
    )
    joined = _sjoin_within(points, slum_union, how="left")
    out = points.copy()
    out["inside_settlement"] = joined["index_right"].notna().astype(int).to_numpy()
    return out


def signed_distance_to_slums(
    points: gpd.GeoDataFrame, slums: gpd.GeoDataFrame
) -> np.ndarray:
    """Signed distance (m): negative inside settlement, positive outside, 0 on boundary."""
    slum_union = unary_union(slums.geometry)
    dist_to_poly = points.geometry.distance(slum_union).to_numpy(dtype=float)
    dist_to_boundary = points.geometry.distance(slum_union.boundary).to_numpy(
        dtype=float
    )
    inside = dist_to_poly <= 1e-6
    signed = np.where(inside, -dist_to_boundary, dist_to_poly)
    return signed.astype(float)


def load_gsvi_waste_panoids(sviwaste: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Waste-positive GSVI panoids (one row per panoid)."""
    points = sviwaste if sviwaste is not None else load_sviwaste_points()
    waste = points.loc[points["waste_positive"] == 1].copy()
    waste["location_kind"] = "gsvi_panoid"
    waste["arm_source"] = "Google"
    return waste.reset_index(drop=True)


def load_selfcollected_waste_locations() -> gpd.GeoDataFrame:
    """Faith/ZWL waste detections as extra locations (no panoid)."""
    waste = _ensure_32737(gpd.read_file(WASTE_SELF_GPKG))
    self_pts = waste.loc[waste["source"].isin(SELF_SOURCES)].copy()
    self_pts["location_kind"] = "self_collected"
    self_pts["arm_source"] = self_pts["source"].astype(str)
    if "panoid" not in self_pts.columns:
        self_pts["panoid"] = pd.NA
    return self_pts.reset_index(drop=True)


def load_gsvi_selfcollected_locations(
    sviwaste: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """GSVI waste-positive panoids plus Faith/ZWL locations."""
    gsvi = load_gsvi_waste_panoids(sviwaste)
    self_pts = load_selfcollected_waste_locations()

    keep_cols = [
        "panoid",
        "img_name",
        "lat",
        "lon",
        "location_kind",
        "arm_source",
        "geometry",
    ]
    for col in keep_cols:
        if col not in gsvi.columns:
            gsvi[col] = pd.NA
        if col not in self_pts.columns:
            self_pts[col] = pd.NA

    combined = pd.concat(
        [gsvi[keep_cols], self_pts[keep_cols]],
        ignore_index=True,
    )
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=gsvi.crs)


def location_keys(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Stable keys: panoid for GSVI; img_name (+rounded coords) for self-collected."""
    attrs = gdf.drop(columns="geometry", errors="ignore").reset_index(drop=True)
    keys = []
    for _, row in attrs.iterrows():
        kind = row.get("location_kind", "")
        panoid = row.get("panoid")
        if kind == "gsvi_panoid" or (pd.notna(panoid) and str(panoid).strip()):
            keys.append(("panoid", str(panoid)))
            continue
        img = str(row.get("img_name", ""))
        lat = row.get("lat")
        lon = row.get("lon")
        if pd.notna(lat) and pd.notna(lon):
            keys.append(("self", round(float(lat), 6), round(float(lon), 6), img))
        else:
            keys.append(("self_geom", img))
    return pd.Series(keys)


def load_boundary() -> gpd.GeoDataFrame:
    return _ensure_32737(gpd.read_file(BOUNDARY_GPKG))


def load_slums() -> gpd.GeoDataFrame:
    return _ensure_32737(gpd.read_file(SLUM_GPKG))

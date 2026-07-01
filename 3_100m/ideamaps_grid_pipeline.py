"""
IDEAMaps 100 m grid indicator — matches SVI_IDEAMaps.ipynb submission logic.

Pipeline (same on any grid extent; only cell count / boundary differs):
  1. Count SVI images and waste detections per cell (spatial join, within)
  2. Empirical Bayes smoothed waste/SVI ratio
  3. Linear spatial interpolation on cell centroids (griddata)
  4. Jenks Natural Breaks k=3 on final_waste_ratio.fillna(0) → result 0/1/2

This is NOT the fixed-band scheme (0.024 / 0.164 thresholds) in grid_classification.py.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import mapclassify
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

METHOD_LABEL = (
    "Empirical Bayes waste/SVI ratio + linear spatial fill + Jenks k=3 (SVI_IDEAMaps.ipynb)"
)
FIXED_BREAKS_METHOD_LABEL = (
    "Empirical Bayes + spatial fill + GSVI submission Jenks break points (fixed thresholds)"
)
RAW_RATIO_METHOD_LABEL = (
    "Raw cell waste/SVI ratio (no EB, no spatial fill) + fixed Jenks break points"
)

DEFAULT_SUBMISSION_GRID = (
    Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data/Waste/IDEAMaps/waste_Nairobi_grid.geojson")
)

# IDEAMaps submission Jenks k=3 upper bounds (full-grid fit at export time).
GSVI_SUBMISSION_JENKS_BREAKS = np.array([0.02224478, 0.08448627, 0.41013691])


def count_points_in_grid(
    grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, value_col: str
) -> gpd.GeoDataFrame:
    grid = grid.reset_index(drop=True).copy()
    grid["_grid_idx"] = grid.index
    joined = gpd.sjoin(
        points.to_crs(grid.crs),
        grid[["_grid_idx", "geometry"]],
        how="inner",
        predicate="within",
    )
    counts = joined.groupby("_grid_idx").size().rename(value_col)
    out = grid.drop(columns=["_grid_idx"], errors="ignore")
    out[value_col] = out.index.map(counts).fillna(0).astype(int)
    return out


def empirical_bayes_ratio(
    waste_points: pd.Series, total_svi_images: pd.Series
) -> pd.Series:
    """Notebook formula: population variance over all grid cells."""
    s = waste_points.astype(float)
    n = total_svi_images.astype(float)
    mean_p = s.sum() / n.sum()
    observed = np.where(n > 0, s / n, np.nan)
    var_p = np.nanmean((observed - mean_p) ** 2)
    if var_p <= 0 or not np.isfinite(var_p):
        var_p = mean_p * (1 - mean_p) / max(n.sum(), 1)
    denom = mean_p * (1 - mean_p) / var_p - 1
    alpha = mean_p * denom
    beta = (1 - mean_p) * denom
    smoothed = (s + alpha) / (n + alpha + beta)
    return smoothed.where(n > 0, np.nan)


def spatial_fill_ratio(grid: gpd.GeoDataFrame, values: pd.Series) -> pd.Series:
    coords = np.array([(g.centroid.x, g.centroid.y) for g in grid.geometry])
    vals = values.to_numpy(dtype=float)
    known = np.isfinite(vals)
    if known.sum() < 3:
        return values.copy()
    filled = griddata(coords[known], vals[known], coords, method="linear")
    return pd.Series(filled, index=grid.index, dtype=float).fillna(values)


def jenks_result(final_ratio: pd.Series) -> pd.Series:
    values = final_ratio.fillna(0)
    classifier = mapclassify.NaturalBreaks(values, k=3)
    return pd.Series(classifier.yb, index=final_ratio.index, dtype=int)


def load_gsvi_submission_jenks_breaks(
    submission_grid: Path | None = DEFAULT_SUBMISSION_GRID,
) -> np.ndarray:
    """Return fixed IDEAMaps submission Jenks upper bounds (optionally verify against geojson)."""
    breaks = GSVI_SUBMISSION_JENKS_BREAKS.copy()
    if submission_grid is None or not submission_grid.exists():
        return breaks
    g = gpd.read_file(submission_grid)
    values = g["final_waste_ratio"].fillna(0)
    classifier = mapclassify.NaturalBreaks(values, k=3)
    from_file = np.asarray(classifier.bins, dtype=float)
    if not np.allclose(from_file, breaks, rtol=0, atol=1e-4):
        import warnings

        warnings.warn(
            f"Submission geojson Jenks bins {from_file} differ from hard-coded "
            f"{breaks}; using hard-coded breaks.",
            stacklevel=2,
        )
    return breaks


def classify_with_breaks(final_ratio: pd.Series, breaks: np.ndarray) -> pd.Series:
    """
    Apply Jenks k=3 upper bounds as two cut points → classes 0/1/2.

    breaks[0] and breaks[1] separate low/medium/high. breaks[2] is the maximum
    ratio in the high Jenks class on the original submission grid (not a 4th
    category boundary). Values above breaks[2] remain class 2.
    """
    values = final_ratio.fillna(0).to_numpy(dtype=float)
    out = np.zeros(len(values), dtype=int)
    out[values > breaks[0]] = 1
    out[values > breaks[1]] = 2
    return pd.Series(out, index=final_ratio.index, dtype=int)


def compute_ratios(
    grid: gpd.GeoDataFrame, svi_gpkg: Path, waste_gpkg: Path
) -> gpd.GeoDataFrame:
    svi = gpd.read_file(svi_gpkg)
    waste = gpd.read_file(waste_gpkg)
    out = count_points_in_grid(grid, svi, "total_svi_images")
    out["waste_points"] = count_points_in_grid(grid, waste, "waste_points")[
        "waste_points"
    ].values
    out["waste_ratio"] = np.where(
        out["total_svi_images"] == 0,
        np.nan,
        out["waste_points"] / out["total_svi_images"],
    )
    out["smoothed_waste_ratio"] = empirical_bayes_ratio(
        out["waste_points"], out["total_svi_images"]
    )
    out["final_waste_ratio"] = spatial_fill_ratio(out, out["smoothed_waste_ratio"])
    return out


def run_ideamaps_grid_pipeline(
    grid: gpd.GeoDataFrame,
    svi_gpkg: Path,
    waste_gpkg: Path,
    *,
    jenks_breaks: np.ndarray | None = None,
    raw_ratio_only: bool = False,
) -> gpd.GeoDataFrame:
    out = compute_ratios(grid, svi_gpkg, waste_gpkg)
    if raw_ratio_only:
        out["smoothed_waste_ratio"] = out["waste_ratio"]
        out["final_waste_ratio"] = out["waste_ratio"].fillna(0)
    if jenks_breaks is None:
        out["result"] = jenks_result(out["final_waste_ratio"])
    else:
        out["result"] = classify_with_breaks(out["final_waste_ratio"], jenks_breaks)
    return out


def attach_cell_keys(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    wgs84 = gdf.to_crs("EPSG:4326")
    out = gdf.copy()
    centroids = wgs84.geometry.centroid
    out["lat_r"] = centroids.y.round(5)
    out["lon_r"] = centroids.x.round(5)
    return out

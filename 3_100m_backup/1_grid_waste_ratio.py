"""
100 m grid waste/SVI ratio — gsvi vs gsvi_selfcollected arms.

Per cell: waste_points / total_svi_images (one row per image file, same dedupe
as waste detections), Empirical Bayes smoothing, linear spatial fill, then
IDEAMaps fixed probability bands (default) or optional Jenks → result column.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

from grid_classification import CLASS_LABELS, classify_result

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"

GRID_GPKG = INPUT_DIR / "Nairobi_grid_100m_32737.gpkg"
WGS84 = "EPSG:4326"
DEFAULT_METHOD = "fixed"

ARMS = {
    "gsvi": {
        "label": "GSVI only (Google)",
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg",
        "output_gpkg": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_32737.gpkg",
        "output_geojson": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi.geojson",
        "output_csv": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi.csv",
    },
    "gsvi_selfcollected": {
        "label": "GSVI + self-collected (Faith/ + ZWL/)",
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        "output_gpkg": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_selfcollected_32737.gpkg",
        "output_geojson": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_selfcollected.geojson",
        "output_csv": OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_selfcollected.csv",
    },
}


def count_points_in_grid(
    grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, value_col: str
) -> gpd.GeoDataFrame:
    """Spatial join points within grid cells; aggregate count per cell."""
    grid = grid.reset_index(drop=True).copy()
    grid["_grid_idx"] = grid.index

    joined = gpd.sjoin(points, grid[["_grid_idx", "geometry"]], how="inner", predicate="within")
    counts = joined.groupby("_grid_idx").size().rename(value_col)

    out = grid.drop(columns=["_grid_idx"], errors="ignore")
    out[value_col] = out.index.map(counts).fillna(0).astype(int)
    return out


def empirical_bayes_ratio(
    waste_points: pd.Series, total_svi_images: pd.Series
) -> pd.Series:
    """Beta-binomial Empirical Bayes smoothed proportion (notebook logic)."""
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
    smoothed = smoothed.where(n > 0, np.nan)
    return smoothed


def spatial_fill_ratio(grid: gpd.GeoDataFrame, values: pd.Series) -> pd.Series:
    """Linear interpolation on cell centroids; fall back to smoothed values."""
    coords = np.array([(g.centroid.x, g.centroid.y) for g in grid.geometry])
    vals = values.to_numpy(dtype=float)
    known = np.isfinite(vals)
    if known.sum() < 3:
        return values.copy()

    filled = griddata(coords[known], vals[known], coords, method="linear")
    out = pd.Series(filled, index=grid.index, dtype=float)
    out = out.fillna(values)
    return out


def to_submission_csv(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Tabular export: bbox + centre + result (no geometry, no continuous ratio)."""
    wgs84 = gdf.to_crs(WGS84).reset_index(drop=True)
    bounds = wgs84.geometry.bounds
    tab = pd.DataFrame(
        {
            "lon_min": bounds["minx"],
            "lat_min": bounds["miny"],
            "lon_max": bounds["maxx"],
            "lat_max": bounds["maxy"],
            "latitude": (bounds["miny"] + bounds["maxy"]) / 2,
            "longitude": (bounds["minx"] + bounds["maxx"]) / 2,
            "result": wgs84["result"].astype(int),
        }
    )
    tab.to_csv(path, index=False)


def process_arm(
    key: str, grid: gpd.GeoDataFrame, method: str = DEFAULT_METHOD
) -> tuple[gpd.GeoDataFrame, dict]:
    meta = ARMS[key]
    svi = gpd.read_file(meta["svi_gpkg"])
    waste = gpd.read_file(meta["waste_gpkg"])

    out = count_points_in_grid(grid, svi, "total_svi_images")
    waste_counts = count_points_in_grid(grid, waste, "waste_points")["waste_points"]
    out["waste_points"] = waste_counts.values

    out["waste_ratio"] = np.where(
        out["total_svi_images"] == 0,
        np.nan,
        out["waste_points"] / out["total_svi_images"],
    )
    out["smoothed_waste_ratio"] = empirical_bayes_ratio(
        out["waste_points"], out["total_svi_images"]
    )
    out["final_waste_ratio"] = spatial_fill_ratio(out, out["smoothed_waste_ratio"])
    has_svi = out["total_svi_images"] > 0
    out["result"] = classify_result(
        method,
        out["final_waste_ratio"],
        has_svi,
        smoothed_ratio=out["smoothed_waste_ratio"],
        raw_ratio=out["waste_ratio"],
    )

    summary = {
        "arm": key,
        "label": meta["label"],
        "classification_method": method,
        "n_cells": len(out),
        "n_cells_with_svi": int(has_svi.sum()),
        "n_cells_with_waste": int((out["waste_points"] > 0).sum()),
        "total_svi_images": int(out["total_svi_images"].sum()),
        "total_waste": int(out["waste_points"].sum()),
        "mean_final_waste_ratio": float(out["final_waste_ratio"].mean(skipna=True)),
        "median_final_waste_ratio": float(out["final_waste_ratio"].median(skipna=True)),
        "result_class_0": int((out["result"] == 0).sum()),
        "result_class_1": int((out["result"] == 1).sum()),
        "result_class_2": int((out["result"] == 2).sum()),
        "result_class_3": int((out["result"] == 3).sum()),
    }

    out.to_file(meta["output_gpkg"], driver="GPKG")
    out.to_crs(WGS84).to_file(meta["output_geojson"], driver="GeoJSON")
    to_submission_csv(out, meta["output_csv"])

    print(f"[{key}] {meta['label']} ({method} classification)")
    print(f"  Wrote {meta['output_gpkg'].name}")
    print(f"  Wrote {meta['output_geojson'].name}")
    print(f"  Wrote {meta['output_csv'].name}")
    print(f"  Cells with SVI images: {summary['n_cells_with_svi']:,} / {summary['n_cells']:,}")
    print(
        f"  Total waste/SVI images: {summary['total_waste']:,} / "
        f"{summary['total_svi_images']:,}"
    )
    for cls in range(4):
        print(f"  Class {cls} ({CLASS_LABELS[cls]}): {summary[f'result_class_{cls}']:,}")

    return out, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="100 m grid waste/SVI ratio by arm.")
    parser.add_argument(
        "--method",
        choices=["fixed", "jenks"],
        default=DEFAULT_METHOD,
        help="Classification method: fixed IDEAMaps bands (default) or Jenks k=3",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    grid = gpd.read_file(GRID_GPKG)

    summaries = []
    for key in ARMS:
        _, summary = process_arm(key, grid, method=args.method)
        summaries.append(summary)

    comparison_path = OUTPUT_DIR / "Nairobi_grid_waste_ratio_summary_comparison.csv"
    pd.DataFrame(summaries).to_csv(comparison_path, index=False)
    print(f"Wrote {comparison_path}")


if __name__ == "__main__":
    main()

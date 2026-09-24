#!/usr/bin/env python3
"""Step 6.1 — what self-collected imagery adds to the observation frame.

The chapter runs on GSVI. Self-collected (Faith/ + ZWL/) imagery was gathered
where Street View is thin, so the first question is not "does it change the
answer" but "what does it let us see that we could not see before". This script
answers that on the frame the rest of the chapter uses: the 100 m grid.

For every cell of the active grid it recomputes direct observation twice —
GSVI alone, then GSVI + self-collected — and reports the difference:

  n_images_gsvi / n_images_sc        images of each kind inside the cell
  observed_gsvi / observed_gsc       1 if the cell holds >=1 image of that arm
  newly_observed                     1 if the cell is observed only with SC
  dist_nearest_obs_gsvi_m            centroid -> nearest GSVI panorama (0 if observed)
  dist_nearest_obs_gsc_m             same, after adding self-collected locations

Self-collected images carry no panoid, so each image is its own observation
location (lib.arms.observation_key); "panorama" below means a GSVI panoid or a
single self-collected image.

Outputs (Data/Chapter_waste/6_selfcollected/1_sources/):
  1_Nairobi_sc_coverage_grid100m_32737.gpkg   per cell, columns above
  1_Nairobi_sc_coverage_summary.csv           one row, every number in the tables
  1_Nairobi_sc_new_cells_32737.gpkg           the newly covered cells only (for the map)
  thesis_table/table_6_1_sc_sources.csv       images / panoramas / waste by source
  thesis_table/table_6_1_sc_coverage.csv      GSVI -> GSVI+SC coverage change
  1_Nairobi_sc_new_cells_location.csv         where the new cells are
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.ops import unary_union

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, prep_dir, selfcollected_dir  # noqa: E402
from lib.arms import ARMS, GSVI, GSVI_SC, SELF_SOURCES  # noqa: E402

OUTPUT_DIR = selfcollected_dir() / "1_sources"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

CELLS_GPKG = OUTPUT_DIR / "1_Nairobi_sc_coverage_grid100m_32737.gpkg"
NEW_CELLS_GPKG = OUTPUT_DIR / "1_Nairobi_sc_new_cells_32737.gpkg"
SUMMARY_CSV = OUTPUT_DIR / "1_Nairobi_sc_coverage_summary.csv"
LOCATION_CSV = OUTPUT_DIR / "1_Nairobi_sc_new_cells_location.csv"
SOURCES_TABLE = TABLE_DIR / "table_6_1_sc_sources.csv"
COVERAGE_TABLE = TABLE_DIR / "table_6_1_sc_coverage.csv"

SLUM_GPKG = prep_dir() / "Nairobi_slum_polygon_32737.gpkg"

DEFAULT_FAR_M = 500.0
SNAP_MAX_M = 100.0  # grid slivers: assign the point to the nearest cell within this


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="What self-collected imagery adds to 100 m coverage.")
    parser.add_argument(
        "--far-m",
        type=float,
        default=DEFAULT_FAR_M,
        help="Threshold for 'far from any observation' (default: 500)",
    )
    return parser.parse_args()


def _to_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


# ---------------------------------------------------------------------------
# Cell assignment (same sliver handling as 2coverage_analysis/5_gridsvi.py)
# ---------------------------------------------------------------------------
def assign_cells(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, label: str) -> pd.Series:
    pts = points[["geometry"]].reset_index(drop=True)
    cells = grid[["cell_id", "geometry"]]
    within = gpd.sjoin(pts, cells, how="left", predicate="within")
    within = within[~within.index.duplicated(keep="first")]
    cell_id = within["cell_id"]
    missing = cell_id.isna()
    if missing.any():
        nearest = gpd.sjoin_nearest(
            pts.loc[missing], cells, how="left", max_distance=SNAP_MAX_M, distance_col="_d"
        )
        nearest = nearest[~nearest.index.duplicated(keep="first")]
        cell_id = cell_id.copy()
        cell_id.loc[missing] = nearest["cell_id"]
        n_snapped = int(nearest["cell_id"].notna().sum())
        n_dropped = int(missing.sum()) - n_snapped
        print(f"  {label}: {n_snapped:,} in grid slivers snapped to nearest cell"
              + (f"; {n_dropped:,} beyond {SNAP_MAX_M:.0f} m dropped" if n_dropped else ""))
    return cell_id


def count_in_cells(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, name: str) -> pd.Series:
    counts = assign_cells(grid, points, name).dropna().astype(int).value_counts()
    return grid["cell_id"].map(counts).fillna(0).astype(int).rename(name)


def distance_to_nearest(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> np.ndarray:
    tree = cKDTree(np.c_[points.geometry.x, points.geometry.y])
    centroids = grid.geometry.centroid
    dist, _ = tree.query(np.c_[centroids.x, centroids.y], k=1)
    return dist


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_sources() -> dict[str, gpd.GeoDataFrame]:
    """Images, observation locations and waste detections, split GSVI vs self-collected."""
    images = _to_32737(gpd.read_file(GSVI_SC.svi_image_gpkg()))
    points = _to_32737(gpd.read_file(GSVI_SC.svi_point_gpkg()))
    waste = _to_32737(gpd.read_file(GSVI_SC.waste_gpkg()))

    is_self = lambda df: df["source"].isin(SELF_SOURCES)  # noqa: E731
    return {
        "images_gsvi": images.loc[~is_self(images)],
        "images_sc": images.loc[is_self(images)],
        "points_gsvi": points.loc[~is_self(points)],
        "points_sc": points.loc[is_self(points)],
        "waste_gsvi": waste.loc[~is_self(waste)],
        "waste_sc": waste.loc[is_self(waste)],
    }


# ---------------------------------------------------------------------------
# Per-cell coverage, before and after
# ---------------------------------------------------------------------------
def compute_cells(grid: gpd.GeoDataFrame, src: dict[str, gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    cells = grid[["cell_id", "grid_source", "geometry"]].copy()

    cells["n_images_gsvi"] = count_in_cells(grid, src["images_gsvi"], "n_images_gsvi")
    cells["n_images_sc"] = count_in_cells(grid, src["images_sc"], "n_images_sc")
    cells["n_obs_gsvi"] = count_in_cells(grid, src["points_gsvi"], "n_obs_gsvi")
    cells["n_obs_sc"] = count_in_cells(grid, src["points_sc"], "n_obs_sc")

    cells["observed_gsvi"] = (cells["n_images_gsvi"] > 0).astype(int)
    cells["observed_gsc"] = ((cells["n_images_gsvi"] + cells["n_images_sc"]) > 0).astype(int)
    cells["newly_observed"] = ((cells["observed_gsc"] == 1) & (cells["observed_gsvi"] == 0)).astype(int)

    all_points = pd.concat([src["points_gsvi"], src["points_sc"]], ignore_index=True)
    all_points = gpd.GeoDataFrame(all_points, geometry="geometry", crs=src["points_gsvi"].crs)

    d_gsvi = distance_to_nearest(grid, src["points_gsvi"])
    d_gsc = distance_to_nearest(grid, all_points)
    cells["dist_nearest_obs_gsvi_m"] = np.where(cells["observed_gsvi"] == 1, 0.0, d_gsvi)
    cells["dist_nearest_obs_gsc_m"] = np.where(cells["observed_gsc"] == 1, 0.0, d_gsc)

    # Waste-positive cells, so the indicator's own frame can be read the same way
    cells["n_waste_gsvi"] = count_in_cells(grid, src["waste_gsvi"], "n_waste_gsvi")
    cells["n_waste_sc"] = count_in_cells(grid, src["waste_sc"], "n_waste_sc")
    return cells


def label_settlement(cells: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Distance from each cell centroid to the nearest mapped urban-poor settlement."""
    slums = _to_32737(gpd.read_file(SLUM_GPKG))
    union = unary_union(slums.geometry)
    centroids = gpd.GeoSeries(cells.geometry.centroid, crs=cells.crs)
    out = cells.copy()
    out["dist_settlement_m"] = centroids.distance(union).to_numpy(dtype=float)
    out["in_settlement"] = (out["dist_settlement_m"] <= 0).astype(int)
    return out


# ---------------------------------------------------------------------------
# Summary + tables
# ---------------------------------------------------------------------------
def compute_summary(cells: pd.DataFrame, src: dict[str, gpd.GeoDataFrame], far_m: float) -> pd.Series:
    n = len(cells)
    obs_gsvi = int(cells["observed_gsvi"].sum())
    obs_gsc = int(cells["observed_gsc"].sum())
    new = cells.loc[cells["newly_observed"] == 1]
    far_gsvi = int((cells["dist_nearest_obs_gsvi_m"] > far_m).sum())
    far_gsc = int((cells["dist_nearest_obs_gsc_m"] > far_m).sum())

    return pd.Series(
        {
            "far_m": far_m,
            "n_cells": n,
            "n_images_gsvi": len(src["images_gsvi"]),
            "n_images_sc": len(src["images_sc"]),
            "n_obs_gsvi": len(src["points_gsvi"]),
            "n_obs_sc": len(src["points_sc"]),
            "n_waste_gsvi": len(src["waste_gsvi"]),
            "n_waste_sc": len(src["waste_sc"]),
            "n_cells_with_sc": int((cells["n_images_sc"] > 0).sum()),
            "n_cells_observed_gsvi": obs_gsvi,
            "pct_cells_observed_gsvi": 100.0 * obs_gsvi / n,
            "n_cells_observed_gsc": obs_gsc,
            "pct_cells_observed_gsc": 100.0 * obs_gsc / n,
            "n_cells_newly_observed": len(new),
            "pct_cells_newly_observed": 100.0 * len(new) / n,
            "pct_gain_relative": 100.0 * len(new) / obs_gsvi if obs_gsvi else np.nan,
            "n_cells_beyond_far_gsvi": far_gsvi,
            "pct_cells_beyond_far_gsvi": 100.0 * far_gsvi / n,
            "n_cells_beyond_far_gsc": far_gsc,
            "pct_cells_beyond_far_gsc": 100.0 * far_gsc / n,
            # where the new cells are
            "n_new_in_settlement": int(new["in_settlement"].sum()),
            "pct_new_in_settlement": 100.0 * new["in_settlement"].mean() if len(new) else np.nan,
            "pct_all_cells_in_settlement": 100.0 * cells["in_settlement"].mean(),
            "median_dist_settlement_new_m": float(new["dist_settlement_m"].median()) if len(new) else np.nan,
            "median_dist_settlement_all_m": float(cells["dist_settlement_m"].median()),
            "median_prior_gsvi_dist_new_m": float(new["dist_nearest_obs_gsvi_m"].median()) if len(new) else np.nan,
            "p90_prior_gsvi_dist_new_m": float(new["dist_nearest_obs_gsvi_m"].quantile(0.9)) if len(new) else np.nan,
            "n_new_beyond_far_before": int((new["dist_nearest_obs_gsvi_m"] > far_m).sum()) if len(new) else 0,
        }
    )


def fmt_int(v: float) -> str:
    return f"{int(round(v)):,}"


def build_sources_table(s: pd.Series) -> pd.DataFrame:
    """One row per source: images, observation locations, waste detections."""
    rows = [
        ("GSVI (Google)", s["n_images_gsvi"], s["n_obs_gsvi"], s["n_waste_gsvi"]),
        ("Self-collected (Faith/ + ZWL/)", s["n_images_sc"], s["n_obs_sc"], s["n_waste_sc"]),
        (
            "GSVI + self-collected",
            s["n_images_gsvi"] + s["n_images_sc"],
            s["n_obs_gsvi"] + s["n_obs_sc"],
            s["n_waste_gsvi"] + s["n_waste_sc"],
        ),
    ]
    return pd.DataFrame(
        [
            {
                "Source": label,
                "SVI images": fmt_int(img),
                "Observation locations": fmt_int(obs),
                "Waste detections": fmt_int(waste),
            }
            for label, img, obs, waste in rows
        ]
    )


def build_coverage_table(s: pd.Series) -> pd.DataFrame:
    """The C_GSVI -> C_GSVI+SC change, on the 100 m grid."""
    far = int(s["far_m"])
    rows = [
        (
            "Directly observed cells",
            f"{fmt_int(s['n_cells_observed_gsvi'])} ({s['pct_cells_observed_gsvi']:.1f}%)",
            f"{fmt_int(s['n_cells_observed_gsc'])} ({s['pct_cells_observed_gsc']:.1f}%)",
            f"+{fmt_int(s['n_cells_newly_observed'])} ({s['pct_cells_observed_gsc'] - s['pct_cells_observed_gsvi']:+.1f} pp)",
        ),
        (
            f"Cells >{far} m from an observation",
            f"{fmt_int(s['n_cells_beyond_far_gsvi'])} ({s['pct_cells_beyond_far_gsvi']:.1f}%)",
            f"{fmt_int(s['n_cells_beyond_far_gsc'])} ({s['pct_cells_beyond_far_gsc']:.1f}%)",
            f"{int(s['n_cells_beyond_far_gsc'] - s['n_cells_beyond_far_gsvi']):+,} "
            f"({s['pct_cells_beyond_far_gsc'] - s['pct_cells_beyond_far_gsvi']:+.1f} pp)",
        ),
        (
            "Cells containing self-collected imagery",
            "—",
            fmt_int(s["n_cells_with_sc"]),
            "—",
        ),
        (
            "Cells observed only with self-collected imagery",
            "—",
            f"{fmt_int(s['n_cells_newly_observed'])} ({s['pct_cells_newly_observed']:.2f}% of the city)",
            f"+{s['pct_gain_relative']:.1f}% of the GSVI frame",
        ),
    ]
    return pd.DataFrame(
        [
            {"Metric": m, "GSVI": a, "GSVI + self-collected": b, "Change": c}
            for m, a, b, c in rows
        ]
    )


def build_location_table(cells: pd.DataFrame, s: pd.Series) -> pd.DataFrame:
    """Where the newly covered cells sit, against the city as a whole."""
    new = cells.loc[cells["newly_observed"] == 1]
    far = int(s["far_m"])
    if new.empty:
        return pd.DataFrame(columns=["Measure", "Newly covered cells", "All cells"])

    rows = [
        ("Cells", fmt_int(len(new)), fmt_int(len(cells))),
        (
            "Inside a mapped settlement",
            f"{100 * new['in_settlement'].mean():.1f}%",
            f"{100 * cells['in_settlement'].mean():.1f}%",
        ),
        (
            "Within 500 m of a settlement",
            f"{100 * (new['dist_settlement_m'] <= 500).mean():.1f}%",
            f"{100 * (cells['dist_settlement_m'] <= 500).mean():.1f}%",
        ),
        (
            "Median distance to a settlement",
            f"{new['dist_settlement_m'].median():,.0f} m",
            f"{cells['dist_settlement_m'].median():,.0f} m",
        ),
        (
            f"Was >{far} m from any GSVI observation",
            f"{100 * (new['dist_nearest_obs_gsvi_m'] > far).mean():.1f}%",
            f"{100 * (cells['dist_nearest_obs_gsvi_m'] > far).mean():.1f}%",
        ),
        (
            "Median prior distance to GSVI",
            f"{new['dist_nearest_obs_gsvi_m'].median():,.0f} m",
            f"{cells['dist_nearest_obs_gsvi_m'].median():,.0f} m",
        ),
    ]
    return pd.DataFrame(rows, columns=["Measure", "Newly covered cells", "All cells"])


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    grid = _to_32737(gpd.read_file(active_grid_gpkg()))
    print(f"Grid: {len(grid):,} cells ({active_grid_gpkg().name})")

    src = load_sources()
    print(f"  GSVI:           {len(src['images_gsvi']):,} images | {len(src['points_gsvi']):,} panoramas")
    print(f"  Self-collected: {len(src['images_sc']):,} images | {len(src['points_sc']):,} locations")

    cells = label_settlement(compute_cells(grid, src))
    s = compute_summary(cells.drop(columns="geometry"), src, args.far_m)

    cells.to_file(CELLS_GPKG, driver="GPKG")
    print(f"Wrote {CELLS_GPKG}")
    new_cells = cells.loc[cells["newly_observed"] == 1]
    new_cells.to_file(NEW_CELLS_GPKG, driver="GPKG")
    print(f"Wrote {NEW_CELLS_GPKG}")
    s.to_frame().T.to_csv(SUMMARY_CSV, index=False)
    print(f"Wrote {SUMMARY_CSV}")

    sources = build_sources_table(s)
    sources.to_csv(SOURCES_TABLE, index=False)
    coverage = build_coverage_table(s)
    coverage.to_csv(COVERAGE_TABLE, index=False)
    location = build_location_table(cells.drop(columns="geometry"), s)
    location.to_csv(LOCATION_CSV, index=False)

    print(f"\n{sources.to_string(index=False)}")
    print(f"\n{coverage.to_string(index=False)}")
    print(f"\nWhere the newly covered cells are:\n{location.to_string(index=False)}")
    print(f"\nWrote {SOURCES_TABLE}\nWrote {COVERAGE_TABLE}\nWrote {LOCATION_CSV}")


if __name__ == "__main__":
    main()

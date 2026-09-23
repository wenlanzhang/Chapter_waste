#!/usr/bin/env python3
"""Observation-opportunity metrics on the 100 m grid: citywide context + targeted SC effect.

A. Citywide context (per arm, GSVI vs GSVI + SC): direct coverage, road coverage,
   observation intensity, coverage inside/near/away from settlements, distance to
   nearest observation. Every metric goes to the long summary CSV; the thesis
   table keeps three headline rows with a percentage-point change column.

B. Targeted mitigation effect on S = {100 m cells receiving >=1 self-collected
   image}: what was their observation status *before* SC was added?
     P_new  = N(SC cells with no prior GSVI image) / N(SC cells)
     E_cov  = newly observed cells / SC images
   plus intensity uplift, distance reduction and settlement targeting, and a
   before/after comparison restricted to S.

Distance to nearest observation is measured from the cell centroid to the
nearest sampling point and set to 0 for cells that already contain an image.

Draft analysis, not wired into the Snakemake pipeline. Reads Step 1 layers and
the Step 2b road-coverage summaries; writes under Data/Chapter_waste/drafts/.

Outputs (Data/Chapter_waste/drafts/observation_opportunity/):
  Nairobi_coverage_metrics_cells_{arm}.csv         per-cell counts, class, distance
  Nairobi_coverage_metrics_sc_cells.csv            S only: before/after columns
  Nairobi_coverage_metrics_summary.csv             long table: arm|sc, metric, value
  thesis_table/table_5_coverage_metrics.csv        Metric | GSVI | GSVI + SC | Change
  thesis_table/table_6_sc_mitigation.csv           Metric | Definition | Value
  thesis_table/table_7_sc_cells_before_after.csv   Metric | Before SC | After SC | Change
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.ops import unary_union

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, coverage_dir, prep_dir  # noqa: E402
from lib.arms import ARM_KEYS, ARMS, SELF_SOURCES, Arm, add_arm_argument, select_arms  # noqa: E402
from lib.road_coverage import buffer_file_tag  # noqa: E402
from chapter_paths import chapter_data_root  # noqa: E402

INPUT_DIR = prep_dir()
COVERAGE_DIR = coverage_dir()  # Step 2b road-coverage summaries
OUTPUT_DIR = chapter_data_root() / "drafts" / "observation_opportunity"
THESIS_DIR = OUTPUT_DIR / "thesis_table"
SLUM_GPKG = INPUT_DIR / "Nairobi_slum_polygon_32737.gpkg"
SUMMARY_CSV = OUTPUT_DIR / "Nairobi_coverage_metrics_summary.csv"
SC_CELLS_CSV = OUTPUT_DIR / "Nairobi_coverage_metrics_sc_cells.csv"
TABLE_CITYWIDE = "table_5_coverage_metrics.csv"
TABLE_SC = "table_6_sc_mitigation.csv"
TABLE_SC_BEFORE_AFTER = "table_7_sc_cells_before_after.csv"
SC_KEY = "sc_mitigation"  # row group in the long summary

DEFAULT_NEAR_M = 200.0
DEFAULT_FAR_M = 500.0
DEFAULT_SVI_BUFFER_M = 50.0
DEFAULT_WEAK_MAX_IMAGES = 2  # <= this many images (incl. 0) = weak or no support

SETTLEMENT_CLASSES = ("inside", "near", "elsewhere")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="100 m grid observation-opportunity metrics per arm.")
    parser.add_argument(
        "--near-m",
        type=float,
        default=DEFAULT_NEAR_M,
        help="'Near settlement' band: centroid within this distance of a settlement (default: 200)",
    )
    parser.add_argument(
        "--far-m",
        type=float,
        default=DEFAULT_FAR_M,
        help="Threshold for 'far from any observation' share (default: 500)",
    )
    parser.add_argument(
        "--svi-buffer-m",
        type=float,
        default=DEFAULT_SVI_BUFFER_M,
        help="Which Step 2b road-coverage buffer to report (default: 50)",
    )
    parser.add_argument(
        "--weak-max-images",
        type=int,
        default=DEFAULT_WEAK_MAX_IMAGES,
        help="Cells with at most this many images (incl. 0) count as weak/no support (default: 2)",
    )
    add_arm_argument(parser)
    return parser.parse_args()


def cells_csv(arm: Arm) -> Path:
    return OUTPUT_DIR / arm.filename("Nairobi_coverage_metrics_cells", suffix="", ext="csv")


# ---------------------------------------------------------------------------
# Per-cell building blocks (arm independent)
# ---------------------------------------------------------------------------
def _to_32737(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        return gdf.to_crs(epsg=32737)
    return gdf


def classify_settlement(grid: gpd.GeoDataFrame, slums: gpd.GeoDataFrame, near_m: float) -> pd.Series:
    """inside / near (<= near_m of boundary) / elsewhere, by cell centroid."""
    slum_union = unary_union(slums.geometry)
    centroids = grid.geometry.centroid
    dist = centroids.distance(slum_union).to_numpy()
    inside = centroids.within(slum_union).to_numpy()
    cls = np.where(inside, "inside", np.where(dist <= near_m, "near", "elsewhere"))
    return pd.Series(cls, index=grid.index, name="settlement_class")


def count_points_in_cells(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, name: str) -> pd.Series:
    joined = gpd.sjoin(
        points[["geometry"]], grid[["cell_id", "geometry"]], how="inner", predicate="within"
    )
    counts = joined.groupby("cell_id").size()
    return grid["cell_id"].map(counts).fillna(0).astype(int).rename(name)


def distance_to_nearest(grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> pd.Series:
    tree = cKDTree(np.c_[points.geometry.x, points.geometry.y])
    centroids = grid.geometry.centroid
    dist, _ = tree.query(np.c_[centroids.x, centroids.y], k=1)
    return pd.Series(dist, index=grid.index, name="dist_nearest_obs_m")


def gini(values: np.ndarray) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    if v.size == 0 or v.sum() == 0:
        return float("nan")
    n = v.size
    return float((2 * np.sum(np.arange(1, n + 1) * v) / (n * v.sum())) - (n + 1) / n)


# ---------------------------------------------------------------------------
# Per-arm metrics
# ---------------------------------------------------------------------------
def build_cells(grid: gpd.GeoDataFrame, arm: Arm) -> gpd.GeoDataFrame:
    images = _to_32737(gpd.read_file(arm.svi_image_gpkg()))
    points = _to_32737(gpd.read_file(arm.svi_point_gpkg()))
    cells = grid.copy()
    cells["n_images"] = count_points_in_cells(grid, images, "n_images")
    cells["n_points"] = count_points_in_cells(grid, points, "n_points")
    cells["observed"] = (cells["n_images"] > 0).astype(int)
    dist = distance_to_nearest(grid, points)
    cells["dist_nearest_obs_m"] = dist.where(cells["observed"] == 0, 0.0)
    return cells


def road_coverage_pct(arm: Arm, svi_buffer_m: float) -> float:
    path = COVERAGE_DIR / f"Nairobi_roadsvi_summary_{arm.tagged(buffer_file_tag(svi_buffer_m))}.csv"
    if not path.exists():
        print(f"  ! {path.name} missing; run 2roadsvi.py --arm {arm.key} first (road coverage = NaN)")
        return float("nan")
    return float(pd.read_csv(path)["pct_road_length_covered"].iloc[0])


def summarise(cells: gpd.GeoDataFrame, arm: Arm, args: argparse.Namespace) -> dict[str, float]:
    n = len(cells)
    observed = cells.loc[cells["observed"] == 1]
    unobserved = cells.loc[cells["observed"] == 0]
    m: dict[str, float] = {
        "n_cells": n,
        "n_cells_observed": len(observed),
        "direct_coverage_pct": 100.0 * len(observed) / n,
        "road_coverage_pct": road_coverage_pct(arm, args.svi_buffer_m),
        "images_total": int(cells["n_images"].sum()),
        "points_total": int(cells["n_points"].sum()),
        "images_per_observed_cell_mean": float(observed["n_images"].mean()),
        "images_per_observed_cell_median": float(observed["n_images"].median()),
        "images_per_observed_cell_gini": gini(observed["n_images"].to_numpy()),
        "points_per_observed_cell_mean": float(observed["n_points"].mean()),
    }
    for cls in SETTLEMENT_CLASSES:
        sub = cells.loc[cells["settlement_class"] == cls]
        m[f"n_cells_{cls}"] = len(sub)
        m[f"direct_coverage_pct_{cls}"] = 100.0 * sub["observed"].mean() if len(sub) else float("nan")
        obs_sub = sub.loc[sub["observed"] == 1]
        m[f"images_per_observed_cell_mean_{cls}"] = (
            float(obs_sub["n_images"].mean()) if len(obs_sub) else float("nan")
        )
    inside, elsewhere = m["direct_coverage_pct_inside"], m["direct_coverage_pct_elsewhere"]
    m["coverage_ratio_inside_vs_elsewhere"] = inside / elsewhere if elsewhere else float("nan")
    m["dist_nearest_obs_median_m"] = float(cells["dist_nearest_obs_m"].median())
    m["dist_nearest_obs_mean_m"] = float(cells["dist_nearest_obs_m"].mean())
    m["dist_nearest_obs_p90_m"] = float(cells["dist_nearest_obs_m"].quantile(0.9))
    m["dist_nearest_obs_median_unobserved_m"] = (
        float(unobserved["dist_nearest_obs_m"].median()) if len(unobserved) else float("nan")
    )
    m["pct_cells_beyond_far_m"] = 100.0 * (cells["dist_nearest_obs_m"] > args.far_m).mean()
    return m


def run_arm(
    grid: gpd.GeoDataFrame, arm: Arm, args: argparse.Namespace
) -> tuple[dict[str, float], gpd.GeoDataFrame]:
    print(f"\n[{arm.key}] {arm.label}")
    cells = build_cells(grid, arm)
    metrics = summarise(cells, arm, args)

    out_cols = [
        "cell_id",
        "grid_source",
        "settlement_class",
        "n_images",
        "n_points",
        "observed",
        "dist_nearest_obs_m",
    ]
    cells[[c for c in out_cols if c in cells.columns]].to_csv(cells_csv(arm), index=False)
    print(f"  Wrote {cells_csv(arm).name}")
    print(
        f"  Direct coverage {metrics['direct_coverage_pct']:.1f}%  |  "
        f"road coverage {metrics['road_coverage_pct']:.1f}%  |  "
        f"images/observed cell {metrics['images_per_observed_cell_mean']:.1f}  |  "
        f"inside/near/elsewhere {metrics['direct_coverage_pct_inside']:.1f}/"
        f"{metrics['direct_coverage_pct_near']:.1f}/{metrics['direct_coverage_pct_elsewhere']:.1f}%  |  "
        f"median dist (unobserved) {metrics['dist_nearest_obs_median_unobserved_m']:.0f} m"
    )
    return metrics, cells


# ---------------------------------------------------------------------------
# B. Targeted mitigation effect on SC-covered cells
# ---------------------------------------------------------------------------
def sc_image_counts(grid: gpd.GeoDataFrame) -> pd.Series:
    images = _to_32737(gpd.read_file(ARMS["gsvi_selfcollected"].svi_image_gpkg()))
    sc_images = images.loc[images["source"].isin(SELF_SOURCES)]
    return count_points_in_cells(grid, sc_images, "n_sc_images")


def sc_mitigation(
    grid: gpd.GeoDataFrame,
    before: gpd.GeoDataFrame,
    after: gpd.GeoDataFrame,
    args: argparse.Namespace,
) -> tuple[dict[str, float], pd.DataFrame]:
    """Before = GSVI-only cells, after = GSVI + SC cells, restricted to S."""
    n_sc = sc_image_counts(grid)
    in_s = n_sc > 0
    s = pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "grid_source": grid["grid_source"],
            "settlement_class": grid["settlement_class"],
            "n_sc_images": n_sc,
            "n_images_before": before["n_images"],
            "n_images_after": after["n_images"],
            "observed_before": before["observed"],
            "observed_after": after["observed"],
            "dist_before_m": before["dist_nearest_obs_m"],
            "dist_after_m": after["dist_nearest_obs_m"],
        }
    ).loc[in_s]
    weak = args.weak_max_images
    s["weak_before"] = s["n_images_before"] <= weak
    s["weak_after"] = s["n_images_after"] <= weak
    newly = s.loc[s["observed_before"] == 0]

    n_cells = len(s)
    n_new = len(newly)
    n_sc_images_total = int(s["n_sc_images"].sum())
    targeted = s["settlement_class"].isin(["inside", "near"])
    m: dict[str, float] = {
        "sc_cells": n_cells,
        "sc_images": n_sc_images_total,
        "sc_cells_previously_unobserved": n_new,
        "pct_sc_cells_previously_unobserved": 100.0 * n_new / n_cells if n_cells else float("nan"),
        "new_coverage_yield_pct": 100.0 * n_new / n_cells if n_cells else float("nan"),
        "pct_sc_cells_redundant": 100.0 * (n_cells - n_new) / n_cells if n_cells else float("nan"),
        "newly_observed_cells_per_sc_image": n_new / n_sc_images_total if n_sc_images_total else float("nan"),
        "sc_images_per_newly_observed_cell": n_sc_images_total / n_new if n_new else float("nan"),
        "intensity_uplift_median_images": float(s["n_sc_images"].median()),
        "intensity_uplift_mean_images": float(s["n_sc_images"].mean()),
        "distance_reduction_median_m": (
            float((newly["dist_before_m"] - newly["dist_after_m"]).median()) if n_new else float("nan")
        ),
        "pct_sc_cells_inside_settlement": 100.0 * (s["settlement_class"] == "inside").mean(),
        "pct_sc_cells_near_settlement": 100.0 * (s["settlement_class"] == "near").mean(),
        "pct_sc_cells_inside_or_near": 100.0 * targeted.mean(),
        # before / after on S
        "before_pct_observed": 100.0 * s["observed_before"].mean(),
        "after_pct_observed": 100.0 * s["observed_after"].mean(),
        "before_median_images": float(s["n_images_before"].median()),
        "after_median_images": float(s["n_images_after"].median()),
        "before_median_dist_m": float(s["dist_before_m"].median()),
        "after_median_dist_m": float(s["dist_after_m"].median()),
        "before_mean_dist_m": float(s["dist_before_m"].mean()),
        "after_mean_dist_m": float(s["dist_after_m"].mean()),
        "before_pct_weak": 100.0 * s["weak_before"].mean(),
        "after_pct_weak": 100.0 * s["weak_after"].mean(),
        "weak_max_images": weak,
    }
    return m, s


# ---------------------------------------------------------------------------
# Thesis tables
# ---------------------------------------------------------------------------
def _fmt(value, decimals: int, unit: str = "") -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return f"{value:,.{decimals}f}{unit}"


MINUS = "\u2212"


def _signed(delta: float, decimals: int, unit: str = "") -> str:
    """Signed change with a proper minus sign."""
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return "—"
    sign = "+" if delta >= 0 else MINUS
    return f"{sign}{abs(delta):,.{decimals}f}{unit}"


def _pp(after: float, before: float, decimals: int = 1) -> str:
    return _signed(after - before, decimals, " pp")


def build_citywide_table(metrics: dict[str, dict[str, float]], args: argparse.Namespace) -> pd.DataFrame:
    g, sc = metrics["gsvi"], metrics["gsvi_selfcollected"]
    far = int(args.far_m)
    rows = [
        ("Directly observed urban cells", "direct_coverage_pct"),
        ("Road coverage", "road_coverage_pct"),
        (f"Cells >{far} m from observation", "pct_cells_beyond_far_m"),
    ]
    return pd.DataFrame(
        {
            "Metric": [r[0] for r in rows],
            ARMS["gsvi"].column: [_fmt(g[r[1]], 1, "%") for r in rows],
            ARMS["gsvi_selfcollected"].column: [_fmt(sc[r[1]], 1, "%") for r in rows],
            "Change": [_pp(sc[r[1]], g[r[1]]) for r in rows],
        }
    )


def build_sc_table(m: dict[str, float], args: argparse.Namespace) -> pd.DataFrame:
    near = int(args.near_m)
    rows = [
        ("SC-covered cells", "Number of 100 m cells receiving \u22651 SC image", _fmt(m["sc_cells"], 0)),
        ("SC images", "Self-collected images placed in those cells", _fmt(m["sc_images"], 0)),
        (
            "Previously unobserved cells",
            "% of SC-covered cells with no GSVI image before SC (P_new)",
            _fmt(m["pct_sc_cells_previously_unobserved"], 1, "%"),
        ),
        (
            "New direct-coverage yield",
            "Previously unobserved cells converted to directly observed / all SC-covered cells",
            _fmt(m["new_coverage_yield_pct"], 1, "%"),
        ),
        (
            "Redundant observations",
            "% of SC-covered cells already containing GSVI imagery",
            _fmt(m["pct_sc_cells_redundant"], 1, "%"),
        ),
        (
            "Coverage gain efficiency",
            "Newly observed cells per SC image (E_coverage)",
            _fmt(m["newly_observed_cells_per_sc_image"], 3),
        ),
        (
            "Observation-intensity uplift",
            "Median (mean) SC images added per SC-covered cell",
            f"{_signed(m['intensity_uplift_median_images'], 0, ' images')} "
            f"(mean {_signed(m['intensity_uplift_mean_images'], 1)})",
        ),
        (
            "Distance reduction",
            "Median reduction in distance to nearest observation, previously unobserved SC cells",
            _fmt(m["distance_reduction_median_m"], 0, " m"),
        ),
        (
            "Settlement targeting",
            f"% of SC-covered cells inside / within {near} m of urban-poor settlements",
            f"{_fmt(m['pct_sc_cells_inside_or_near'], 1, '%')} "
            f"({_fmt(m['pct_sc_cells_inside_settlement'], 1, '%')} inside)",
        ),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Definition", "Value"])


def build_sc_before_after_table(m: dict[str, float]) -> pd.DataFrame:
    weak = int(m["weak_max_images"])
    rows = [
        (
            "Cells directly observed",
            _fmt(m["before_pct_observed"], 1, "%"),
            _fmt(m["after_pct_observed"], 1, "%"),
            _pp(m["after_pct_observed"], m["before_pct_observed"]),
        ),
        (
            "Median images / cell",
            _fmt(m["before_median_images"], 0),
            _fmt(m["after_median_images"], 0),
            _signed(m["after_median_images"] - m["before_median_images"], 0, ""),
        ),
        (
            # Mean, not median: with most of S already observed the median is 0 on both sides
            "Mean distance to observation",
            _fmt(m["before_mean_dist_m"], 0, " m"),
            _fmt(m["after_mean_dist_m"], 0, " m"),
            _signed(m["after_mean_dist_m"] - m["before_mean_dist_m"], 0, " m"),
        ),
        (
            f"Cells with weak or no observation support (\u2264{weak} images)",
            _fmt(m["before_pct_weak"], 1, "%"),
            _fmt(m["after_pct_weak"], 1, "%"),
            _pp(m["after_pct_weak"], m["before_pct_weak"]),
        ),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Before SC", "After SC", "Change"])


def save_thesis_table(table: pd.DataFrame, filename: str) -> Path:
    THESIS_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_DIR / filename
    table.to_csv(path, index=False)
    return path


def load_existing_summary() -> dict[str, dict[str, float]]:
    if not SUMMARY_CSV.exists():
        return {}
    df = pd.read_csv(SUMMARY_CSV)
    return {arm: dict(zip(sub["metric"], sub["value"])) for arm, sub in df.groupby("arm")}


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_path = active_grid_gpkg()
    print(f"Grid: {grid_path.name}")
    grid = _to_32737(gpd.read_file(grid_path))
    if "grid_source" not in grid.columns:
        grid["grid_source"] = "angela_original"
    slums = _to_32737(gpd.read_file(SLUM_GPKG))
    grid["settlement_class"] = classify_settlement(grid, slums, args.near_m)
    print(
        f"  {len(grid):,} cells; settlement class: "
        + ", ".join(f"{c} {int((grid['settlement_class'] == c).sum()):,}" for c in SETTLEMENT_CLASSES)
    )

    metrics = load_existing_summary()
    cells_by_arm: dict[str, gpd.GeoDataFrame] = {}
    for arm in select_arms(args.arm):
        metrics[arm.key], cells_by_arm[arm.key] = run_arm(grid, arm, args)

    # Targeted effect needs both arms' cells; reload any arm not computed this run
    for key in ARM_KEYS:
        if key not in cells_by_arm and cells_csv(ARMS[key]).exists():
            cells_by_arm[key] = pd.read_csv(cells_csv(ARMS[key])).set_index(grid.index)
    if all(k in cells_by_arm for k in ARM_KEYS):
        print("\n[SC mitigation] cells receiving \u22651 self-collected image")
        sc_m, sc_cells = sc_mitigation(grid, cells_by_arm["gsvi"], cells_by_arm["gsvi_selfcollected"], args)
        metrics[SC_KEY] = sc_m
        sc_cells.to_csv(SC_CELLS_CSV, index=False)
        print(
            f"  S = {sc_m['sc_cells']:,} cells, {sc_m['sc_images']:,} SC images  |  "
            f"P_new = {sc_m['pct_sc_cells_previously_unobserved']:.1f}%  |  "
            f"inside/near settlement {sc_m['pct_sc_cells_inside_or_near']:.1f}%"
        )

    long = pd.DataFrame(
        [
            {"arm": k, "metric": name, "value": val}
            for k in [*ARM_KEYS, SC_KEY]
            if k in metrics
            for name, val in metrics[k].items()
        ]
    )
    long.to_csv(SUMMARY_CSV, index=False)
    print(f"\nWrote {SUMMARY_CSV.name}")

    if all(k in metrics for k in ARM_KEYS):
        t = build_citywide_table(metrics, args)
        print(f"Wrote {save_thesis_table(t, TABLE_CITYWIDE).name}\n{t.to_string(index=False)}\n")
    if SC_KEY in metrics:
        t = build_sc_table(metrics[SC_KEY], args)
        print(f"Wrote {save_thesis_table(t, TABLE_SC).name}\n{t.drop(columns='Definition').to_string(index=False)}\n")
        t = build_sc_before_after_table(metrics[SC_KEY])
        print(f"Wrote {save_thesis_table(t, TABLE_SC_BEFORE_AFTER).name}\n{t.to_string(index=False)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""HDBSCAN cluster × urban-poor settlement context (panoid unit).

Uses existing panoid-level HDBSCAN labels and signed/unsigned distance to
mapped urban-poor settlements (same boundaries as Step 5 settlement analyses).

Writes:
  - enriched point GeoPackages (distance + category)
  - cluster composition tables (counts + proportions)
  - short summary of clusters near settlement (notebook metrics)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.ops import unary_union

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    label_inside_settlement,
    load_slums,
)

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

DISTANCE_CATEGORIES = [
    "Within Urban Poor",
    "0-250m buffer",
    "250-500m buffer",
    ">500m outside",
]

ARMS = {
    "gsvi": {
        "clustered_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        "enriched_gpkg": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_gsvi_settlement_context_32737.gpkg",
        "prop_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_cluster_distance_composition_gsvi.csv",
        "count_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_cluster_distance_counts_gsvi.csv",
        "summary_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_settlement_context_summary_gsvi.csv",
        "thesis_csv": TABLE_DIR
        / "table_hdbscan_cluster_distance_composition_gsvi.csv",
        "label": "GSVI waste-positive panoids",
    },
    "gsvi_selfcollected": {
        "clustered_gpkg": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        "enriched_gpkg": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_gsvi_selfcollected_settlement_context_32737.gpkg",
        "prop_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_cluster_distance_composition_gsvi_selfcollected.csv",
        "count_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_cluster_distance_counts_gsvi_selfcollected.csv",
        "summary_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_settlement_context_summary_gsvi_selfcollected.csv",
        "thesis_csv": TABLE_DIR
        / "table_hdbscan_cluster_distance_composition_gsvi_selfcollected.csv",
        "label": "GSVI panoids + self-collected locations",
    },
}


def min_distance_to_slums(points, slums) -> np.ndarray:
    """Unsigned distance (m): 0 inside / on boundary, >0 outside."""
    slum_union = unary_union(slums.geometry)
    return points.geometry.distance(slum_union).to_numpy(dtype=float)


def categorize_distance(
    inside: np.ndarray, distance_m: np.ndarray
) -> np.ndarray:
    """Mutually exclusive proximity bins (notebook convention)."""
    cats = np.full(len(distance_m), ">500m outside", dtype=object)
    cats[distance_m <= 500] = "250-500m buffer"
    cats[distance_m <= 250] = "0-250m buffer"
    cats[inside.astype(bool) | (distance_m <= 1e-6)] = "Within Urban Poor"
    return cats


def composition_tables(gdf: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = (
        gdf.groupby(["HDB_cluster", "distance_category"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    for cat in DISTANCE_CATEGORIES:
        if cat not in counts.columns:
            counts[cat] = 0
    counts = counts[DISTANCE_CATEGORIES]
    counts["n_locations"] = counts.sum(axis=1)
    props = counts[DISTANCE_CATEGORIES].div(counts["n_locations"], axis=0)
    props = props.sort_values("Within Urban Poor", ascending=False)
    counts = counts.loc[props.index]
    return counts.reset_index(), props.reset_index()


def summary_metrics(gdf: pd.DataFrame, prop_df: pd.DataFrame, label: str) -> dict:
    n = len(gdf)
    n_clusters = len(set(gdf["HDB_cluster"]) - {-1})
    n_noise = int((gdf["HDB_cluster"] == -1).sum())
    inside = gdf["inside_settlement"].to_numpy() == 1
    dist = gdf["distance_to_settlement_m"].to_numpy(dtype=float)

    # Cluster-level proximity (include noise as a bar, matching notebook)
    within_250 = (
        prop_df["Within Urban Poor"] + prop_df["0-250m buffer"]
    ).to_numpy(dtype=float)
    within_500 = (
        prop_df["Within Urban Poor"]
        + prop_df["0-250m buffer"]
        + prop_df["250-500m buffer"]
    ).to_numpy(dtype=float)
    n_bars = len(prop_df)
    n_ge50_within250 = int((within_250 >= 0.5).sum())
    n_ge50_within500 = int((within_500 >= 0.5).sum())

    return {
        "dataset": label,
        "n_locations": n,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "n_inside_settlement": int(inside.sum()),
        "pct_inside_settlement": 100.0 * float(inside.mean()),
        "median_distance_m": float(np.median(dist)),
        "mean_distance_m": float(np.mean(dist)),
        "pct_within_250m": 100.0 * float((dist <= 250).mean()),
        "pct_within_500m": 100.0 * float((dist <= 500).mean()),
        "n_cluster_bars": n_bars,
        "n_bars_ge50pct_within_250m": n_ge50_within250,
        "pct_bars_ge50pct_within_250m": 100.0 * n_ge50_within250 / n_bars
        if n_bars
        else np.nan,
        "n_bars_ge50pct_within_500m": n_ge50_within500,
        "pct_bars_ge50pct_within_500m": 100.0 * n_ge50_within500 / n_bars
        if n_bars
        else np.nan,
    }


def process_arm(key: str, slums) -> dict:
    meta = ARMS[key]
    path = meta["clustered_gpkg"]
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Run 3_hdbscan_waste.py first."
        )

    import geopandas as gpd

    gdf = gpd.read_file(path)
    gdf = label_inside_settlement(gdf, slums)
    gdf["distance_to_settlement_m"] = min_distance_to_slums(gdf, slums)
    # Keep distance 0 for points labelled inside (floating-point safety)
    gdf.loc[gdf["inside_settlement"] == 1, "distance_to_settlement_m"] = 0.0
    gdf["distance_category"] = categorize_distance(
        gdf["inside_settlement"].to_numpy(),
        gdf["distance_to_settlement_m"].to_numpy(dtype=float),
    )

    gdf.to_file(meta["enriched_gpkg"], driver="GPKG")

    counts, props = composition_tables(gdf.drop(columns="geometry", errors="ignore"))
    counts.to_csv(meta["count_csv"], index=False)
    props.to_csv(meta["prop_csv"], index=False)
    props.to_csv(meta["thesis_csv"], index=False)

    summary = summary_metrics(gdf, props, meta["label"])
    summary["arm"] = key
    pd.DataFrame([summary]).to_csv(meta["summary_csv"], index=False)

    print(f"[{key}] {meta['label']}")
    print(f"  Locations: {summary['n_locations']:,} | clusters: {summary['n_clusters']}")
    print(
        f"  Inside settlement: {summary['n_inside_settlement']:,} "
        f"({summary['pct_inside_settlement']:.1f}%)"
    )
    print(
        f"  Bars ≥50% within 250 m: {summary['n_bars_ge50pct_within_250m']}/"
        f"{summary['n_cluster_bars']} "
        f"({summary['pct_bars_ge50pct_within_250m']:.0f}%)"
    )
    print(f"  Wrote {meta['enriched_gpkg'].name}")
    print(f"  Wrote {meta['prop_csv'].name}")
    return summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("HDBSCAN × settlement context (panoid-level)...")
    slums = load_slums()
    summaries = [process_arm("gsvi", slums), process_arm("gsvi_selfcollected", slums)]

    comparison = OUTPUT_DIR / "Nairobi_hdbscan_settlement_context_summary_comparison.csv"
    pd.DataFrame(summaries).to_csv(comparison, index=False)
    print(f"Wrote {comparison}")


if __name__ == "__main__":
    main()

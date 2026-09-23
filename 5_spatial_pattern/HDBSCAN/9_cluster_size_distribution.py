#!/usr/bin/env python3
"""Cluster-size stats for HDBSCAN × settlement (notebook violin + histogram).

Ported from del/SVI_distance_use.ipynb (cells ~101–102) and
del/SVI_PPP_Stats_USE.ipynb (cells ~69–74).

Cluster type rule (any overlap): a non-noise cluster is
"Associated with urban-poor settlements" if at least one of its
waste-positive panoramas lies inside a mapped urban-poor settlement
polygon; otherwise "Other clusters".

Writes (per arm):
  - cluster size table (excluding noise), with the labels above
  - summary with n_clusters, clustered/unclustered counts, silhouette score
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.panoids import PATTERN_DIR  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

ARMS = {
    "gsvi": {
        "enriched_gpkg": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_gsvi_settlement_context_32737.gpkg",
        "sizes_csv": OUTPUT_DIR / "Nairobi_hdbscan_cluster_sizes_gsvi.csv",
        "summary_csv": OUTPUT_DIR
        / "Nairobi_hdbscan_cluster_size_summary_gsvi.csv",
        "thesis_sizes": TABLE_DIR / "table_hdbscan_cluster_sizes_gsvi.csv",
        "label": "GSVI waste-positive panoramas",
    },
}


TYPE_ASSOCIATED = "Associated with urban-poor settlements"
TYPE_OTHER = "Other clusters"


def cluster_size_table(gdf: pd.DataFrame) -> pd.DataFrame:
    """One row per non-noise cluster.

    Associated if at least one panorama is inside an urban-poor settlement.
    """
    sub = gdf.loc[gdf["HDB_cluster"] != -1].copy()
    if sub.empty:
        return pd.DataFrame(
            columns=["HDB_cluster", "n_points", "n_inside", "cluster_type"]
        )

    counts = (
        sub.groupby("HDB_cluster", dropna=False)
        .agg(
            n_points=("HDB_cluster", "size"),
            n_inside=("inside_settlement", "sum"),
        )
        .reset_index()
    )
    counts["cluster_type"] = np.where(
        counts["n_inside"] > 0, TYPE_ASSOCIATED, TYPE_OTHER
    )
    return counts.sort_values("HDB_cluster").reset_index(drop=True)


def silhouette_excluding_noise(gdf) -> float:
    mask = gdf["HDB_cluster"].to_numpy() != -1
    labels = gdf.loc[mask, "HDB_cluster"].to_numpy()
    if len(set(labels)) < 2:
        return float("nan")
    coords = np.column_stack(
        [gdf.geometry.x.to_numpy()[mask], gdf.geometry.y.to_numpy()[mask]]
    )
    return float(silhouette_score(coords, labels))


def summarise(gdf, sizes: pd.DataFrame, label: str, arm: str) -> dict:
    n_points = len(gdf)
    n_noise = int((gdf["HDB_cluster"] == -1).sum())
    n_clustered = n_points - n_noise
    n_clusters = len(sizes)

    by_type = (
        sizes.groupby("cluster_type")["n_points"]
        .agg(n_clusters="count", mean_size="mean", median_size="median")
        .reindex([TYPE_ASSOCIATED, TYPE_OTHER])
    )

    def _val(row_label, col):
        if row_label not in by_type.index:
            return np.nan
        v = by_type.loc[row_label, col]
        return v if pd.notna(v) else np.nan

    n_assoc = _val(TYPE_ASSOCIATED, "n_clusters")
    n_other = _val(TYPE_OTHER, "n_clusters")

    return {
        "arm": arm,
        "dataset": label,
        "n_points": n_points,
        "n_clusters": n_clusters,
        "n_clustered": n_clustered,
        "n_noise": n_noise,
        "noise_ratio": n_noise / n_points if n_points else np.nan,
        "silhouette_score": silhouette_excluding_noise(gdf),
        "cluster_rule": "any_panorama_inside_urban_poor_settlement",
        "n_clusters_associated": int(n_assoc) if pd.notna(n_assoc) else 0,
        "n_clusters_other": int(n_other) if pd.notna(n_other) else 0,
        "mean_size_associated": float(_val(TYPE_ASSOCIATED, "mean_size"))
        if pd.notna(_val(TYPE_ASSOCIATED, "mean_size"))
        else np.nan,
        "mean_size_other": float(_val(TYPE_OTHER, "mean_size"))
        if pd.notna(_val(TYPE_OTHER, "mean_size"))
        else np.nan,
    }


def process_arm(key: str) -> dict:
    import geopandas as gpd

    meta = ARMS[key]
    path = meta["enriched_gpkg"]
    if not path.exists():
        raise SystemExit(
            f"Missing {path}. Run 7_hdbscan_settlement_context.py first."
        )

    gdf = gpd.read_file(path)
    if "inside_settlement" not in gdf.columns:
        raise SystemExit(
            f"{path.name} lacks inside_settlement; re-run "
            "7_hdbscan_settlement_context.py."
        )

    sizes = cluster_size_table(gdf)
    sizes.to_csv(meta["sizes_csv"], index=False)
    sizes.to_csv(meta["thesis_sizes"], index=False)

    summary = summarise(gdf, sizes, meta["label"], key)
    pd.DataFrame([summary]).to_csv(meta["summary_csv"], index=False)

    print(f"[{key}] {meta['label']}")
    print(
        f"  Clusters: {summary['n_clusters']} "
        f"(associated={summary['n_clusters_associated']}, "
        f"other={summary['n_clusters_other']})"
    )
    print(
        f"  Clustered: {summary['n_clustered']:,} | "
        f"unclustered: {summary['n_noise']:,}/{summary['n_points']:,} "
        f"({100 * summary['noise_ratio']:.1f}%)"
    )
    print(f"  Silhouette: {summary['silhouette_score']:.3f}")
    print(f"  Wrote {meta['sizes_csv'].name}")
    return summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("HDBSCAN cluster-size distribution tables...")
    summaries = [
        process_arm("gsvi"),
    ]
    comparison = OUTPUT_DIR / "Nairobi_hdbscan_cluster_size_summary_comparison.csv"
    pd.DataFrame(summaries).to_csv(comparison, index=False)
    print(f"Wrote {comparison}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 6.4a (second half) — are the hotspots still settlement hotspots?

1_sc_hdbscan.py answers how many hotspots there are and whether they survive.
This script answers what they are *near*, which is the claim Step 5a actually
makes: 22 of the 24 GSVI clusters contain at least one waste-positive location
inside a mapped urban-poor settlement, and 18.6% of all positives fall inside
one.

Each clustered location is binned into the same four mutually exclusive
proximity categories Step 5a uses, and the per-cluster composition is computed
for both arms. The headline is the share of clusters with a majority of their
locations within 250 m of a settlement — if self-collected imagery were finding
waste somewhere else entirely, that share would fall.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/HDBSCAN/):
  2_Nairobi_sc_cluster_context_{arm}_32737.gpkg   clustered points + category
  2_Nairobi_sc_cluster_composition_{arm}.csv      per-cluster shares
  2_sc_cluster_context_summary.csv                both arms, one row each
  thesis_table/table_6_4_cluster_context.csv      the chapter table
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.panoids import label_inside_settlement, load_slums  # noqa: E402
from sc_frames import ARM_LABELS, DISTANCE_CATEGORIES, PATTERN_DIR, categorize_distance  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

SUMMARY_CSV = OUTPUT_DIR / "2_sc_cluster_context_summary.csv"
CONTEXT_TABLE = TABLE_DIR / "table_6_4_cluster_context.csv"


def clustered_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_sc_hdbscan_{key}_32737.gpkg"


def context_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"2_Nairobi_sc_cluster_context_{key}_32737.gpkg"


def composition_csv(key: str) -> Path:
    return OUTPUT_DIR / f"2_Nairobi_sc_cluster_composition_{key}.csv"


def label_context(gdf: gpd.GeoDataFrame, slums: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = label_inside_settlement(gdf, slums)
    slum_union = unary_union(slums.geometry)
    out["distance_to_settlement_m"] = out.geometry.distance(slum_union).to_numpy(dtype=float)
    out.loc[out["inside_settlement"] == 1, "distance_to_settlement_m"] = 0.0
    out["distance_category"] = categorize_distance(
        out["inside_settlement"].to_numpy(), out["distance_to_settlement_m"].to_numpy()
    ).to_numpy()
    return out


def composition(df: pd.DataFrame) -> pd.DataFrame:
    """Per-cluster share in each proximity category (noise excluded)."""
    clustered = df[df["HDB_cluster"] != -1]
    counts = (
        clustered.groupby(["HDB_cluster", "distance_category"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    for cat in DISTANCE_CATEGORIES:
        if cat not in counts.columns:
            counts[cat] = 0
    counts = counts[DISTANCE_CATEGORIES]
    counts["n_locations"] = counts.sum(axis=1)
    props = counts[DISTANCE_CATEGORIES].div(counts["n_locations"], axis=0)
    props["n_locations"] = counts["n_locations"]
    return props.sort_values("Within Urban Poor", ascending=False).reset_index()


def summarise(df: pd.DataFrame, props: pd.DataFrame, key: str) -> dict:
    clustered = df[df["HDB_cluster"] != -1]
    dist = clustered["distance_to_settlement_m"].to_numpy(dtype=float)
    inside = clustered["inside_settlement"].to_numpy() == 1
    n_clusters = len(props)

    within_250 = (props["Within Urban Poor"] + props["0-250m buffer"]).to_numpy()
    within_500 = within_250 + props["250-500m buffer"].to_numpy()
    # Step 5a's headline: clusters that touch a settlement at all.
    n_touching = int((props["Within Urban Poor"] > 0).sum())

    return {
        "arm": key,
        "n_clusters": n_clusters,
        "n_clustered_locations": len(clustered),
        "n_clusters_touching_settlement": n_touching,
        "pct_clusters_touching_settlement": 100.0 * n_touching / n_clusters if n_clusters else np.nan,
        "n_clusters_majority_within_250m": int((within_250 >= 0.5).sum()),
        "pct_clusters_majority_within_250m": 100.0 * (within_250 >= 0.5).mean() if n_clusters else np.nan,
        "n_clusters_majority_within_500m": int((within_500 >= 0.5).sum()),
        "pct_clusters_majority_within_500m": 100.0 * (within_500 >= 0.5).mean() if n_clusters else np.nan,
        "n_clustered_inside_settlement": int(inside.sum()),
        "pct_clustered_inside_settlement": 100.0 * float(inside.mean()) if len(clustered) else np.nan,
        "median_distance_m": float(np.median(dist)) if len(dist) else np.nan,
        "pct_clustered_within_250m": 100.0 * float((dist <= 250).mean()) if len(dist) else np.nan,
        "pct_clustered_within_500m": 100.0 * float((dist <= 500).mean()) if len(dist) else np.nan,
    }


def build_table(by_arm: dict[str, dict]) -> pd.DataFrame:
    g, s = by_arm["gsvi"], by_arm["gsvi_selfcollected"]
    rows = [
        ("Clusters", f"{g['n_clusters']}", f"{s['n_clusters']}"),
        ("Clustered locations", f"{g['n_clustered_locations']:,}", f"{s['n_clustered_locations']:,}"),
        ("Clusters containing a location inside a settlement",
         f"{g['n_clusters_touching_settlement']} / {g['n_clusters']} ({g['pct_clusters_touching_settlement']:.0f}%)",
         f"{s['n_clusters_touching_settlement']} / {s['n_clusters']} ({s['pct_clusters_touching_settlement']:.0f}%)"),
        ("Clusters with a majority within 250 m",
         f"{g['n_clusters_majority_within_250m']} / {g['n_clusters']} ({g['pct_clusters_majority_within_250m']:.0f}%)",
         f"{s['n_clusters_majority_within_250m']} / {s['n_clusters']} ({s['pct_clusters_majority_within_250m']:.0f}%)"),
        ("Clusters with a majority within 500 m",
         f"{g['n_clusters_majority_within_500m']} / {g['n_clusters']} ({g['pct_clusters_majority_within_500m']:.0f}%)",
         f"{s['n_clusters_majority_within_500m']} / {s['n_clusters']} ({s['pct_clusters_majority_within_500m']:.0f}%)"),
        ("Clustered locations inside a settlement",
         f"{g['pct_clustered_inside_settlement']:.1f}%", f"{s['pct_clustered_inside_settlement']:.1f}%"),
        ("Clustered locations within 250 m",
         f"{g['pct_clustered_within_250m']:.1f}%", f"{s['pct_clustered_within_250m']:.1f}%"),
        ("Clustered locations within 500 m",
         f"{g['pct_clustered_within_500m']:.1f}%", f"{s['pct_clustered_within_500m']:.1f}%"),
        ("Median distance to a settlement",
         f"{g['median_distance_m']:,.0f} m", f"{s['median_distance_m']:,.0f} m"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "GSVI", "GSVI + SC"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CONTEXT_TABLE, index=False)
    print(f"\n6.4a — cluster settlement context:\n{out.to_string(index=False)}")
    print(f"Wrote {CONTEXT_TABLE}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slums = load_slums()

    summaries: dict[str, dict] = {}
    for key in ARM_LABELS:
        path = clustered_gpkg(key)
        if not path.exists():
            raise SystemExit(
                f"Missing {path.name} — run "
                "6_selfcollected/4_pattern/HDBSCAN/1_sc_hdbscan.py first"
            )
        gdf = label_context(gpd.read_file(path), slums)
        gdf.to_file(context_gpkg(key), driver="GPKG")

        props = composition(gdf.drop(columns="geometry", errors="ignore"))
        props.to_csv(composition_csv(key), index=False)

        summaries[key] = summarise(gdf.drop(columns="geometry", errors="ignore"), props, key)
        print(f"[{key}] {summaries[key]['n_clusters']} clusters | "
              f"{summaries[key]['pct_clusters_majority_within_250m']:.0f}% with a majority within 250 m")
        print(f"  Wrote {context_gpkg(key).name}, {composition_csv(key).name}")

    pd.DataFrame(list(summaries.values())).to_csv(SUMMARY_CSV, index=False)
    print(f"Wrote {SUMMARY_CSV}")
    build_table(summaries)


if __name__ == "__main__":
    main()

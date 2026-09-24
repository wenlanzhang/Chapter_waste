#!/usr/bin/env python3
"""Step 6.4a — do the waste hotspots change when self-collected imagery is added?

Step 5a clusters the 2,696 waste-positive GSVI panoramas with HDBSCAN
(min_cluster_size 25, min_samples 6) and finds 24 hotspots. This script fits the
same clusterer, with the same parameters, to the same points plus the 149
self-collected waste locations, and compares the two results side by side:

  how many hotspots, how much of the sample is clustered, how much area
  whether the two labellings agree on the points they share
  what happens to the 149 added locations

Stability is measured on cluster labels, not on footprint geometry. Every one of
the 2,696 GSVI waste locations is present in both runs, so each carries a label
from each — and the agreement between those two labellings is the whole answer.
Adjusted Rand Index and normalised mutual information summarise it; the
GSVI-cluster x combined-cluster transition matrix shows exactly which hotspots
merged into which. Nothing here depends on a hand-set overlap threshold or on
the convex hull, both of which are choices rather than findings.

The 149 added locations are classified the same way, by the label they receive:
joining a cluster that also holds GSVI locations reinforces an existing hotspot,
joining a cluster made only of self-collected points creates a new one, and a
noise label means it does not cluster at all.

Unit: panorama location, not image — a GSVI panoid, or one self-collected image
(which carries no panoid). Hotspot area is the sum of per-cluster convex hulls,
reported for scale only; no result depends on it.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/HDBSCAN/):
  1_Nairobi_sc_hdbscan_{gsvi,gsvi_selfcollected}_32737.gpkg   clustered points
  1_Nairobi_sc_hotspots_{gsvi,gsvi_selfcollected}_32737.gpkg  convex-hull footprints
  1_sc_hdbscan_label_transitions.csv                          GSVI label x combined label
  1_sc_hdbscan_new_locations.csv                              what the 149 added points join
  1_sc_hdbscan_comparison.csv                                 counts and hull area
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir  # noqa: E402
from lib.hdbscan_fit import MIN_CLUSTER_SIZE, MIN_SAMPLES, cluster_convex_hull, cluster_points  # noqa: E402
from lib.panoids import (  # noqa: E402
    load_gsvi_selfcollected_locations,
    load_gsvi_waste_panoids,
    location_keys,
)

OUTPUT_DIR = selfcollected_dir() / "4_pattern" / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

NEW_LOCATIONS_CSV = OUTPUT_DIR / "1_sc_hdbscan_new_locations.csv"
TRANSITIONS_CSV = OUTPUT_DIR / "1_sc_hdbscan_label_transitions.csv"
# Counts and area are descriptive; the chapter's hotspot claim rests on the
# stability table, so this stays a working output.
COMPARISON_TABLE = OUTPUT_DIR / "1_sc_hdbscan_comparison.csv"

ARMS = {
    "gsvi": {"column": "GSVI", "loader": load_gsvi_waste_panoids},
    "gsvi_selfcollected": {"column": "GSVI + SC", "loader": load_gsvi_selfcollected_locations},
}


def points_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_sc_hdbscan_{key}_32737.gpkg"


def hotspots_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_sc_hotspots_{key}_32737.gpkg"


def run_arm(key: str) -> dict:
    meta = ARMS[key]
    points = meta["loader"]()
    clustered, summary = cluster_points(points)
    hulls = cluster_convex_hull(clustered)
    summary["total_hotspot_area_km2"] = float(hulls["area_km2"].sum()) if len(hulls) else 0.0

    clustered.to_file(points_gpkg(key), driver="GPKG")
    hulls.to_file(hotspots_gpkg(key), driver="GPKG")
    print(f"[{key}] {summary['n_points']:,} locations | {summary['n_clusters']} clusters | "
          f"{summary['n_noise']:,} noise ({100 - summary['pct_waste_points_clustered']:.1f}%) | "
          f"{summary['total_hotspot_area_km2']:.3f} km²")
    print(f"  Wrote {points_gpkg(key).name}, {hotspots_gpkg(key).name}")
    return {"points": clustered, "hulls": hulls, "summary": summary}


def fmt(value: float, *, area: bool = False) -> str:
    return f"{value:,.3f}" if area else f"{int(round(value)):,}"


def pct_change(a: float, b: float) -> str:
    return "—" if a == 0 else f"{100.0 * (b - a) / a:+.1f}%"


def build_comparison(a: dict, b: dict) -> pd.DataFrame:
    sa, sb = a["summary"], b["summary"]
    rows = [
        ("Waste locations", sa["n_points"], sb["n_points"], False),
        ("Clustered locations", sa["n_clustered"], sb["n_clustered"], False),
        ("Noise locations", sa["n_noise"], sb["n_noise"], False),
        ("Number of hotspots", sa["n_clusters"], sb["n_clusters"], False),
        ("Total hotspot area (km²)", sa["total_hotspot_area_km2"], sb["total_hotspot_area_km2"], True),
    ]
    records = [
        {
            "Metric": metric,
            "GSVI": fmt(va, area=is_area),
            "GSVI + SC": fmt(vb, area=is_area),
            "Change": (f"{vb - va:+.3f}" if is_area else f"{int(round(vb - va)):+,}"),
            "Change %": pct_change(va, vb),
        }
        for metric, va, vb, is_area in rows
    ]
    out = pd.DataFrame(records)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(COMPARISON_TABLE, index=False)
    print(f"\n{out.to_string(index=False)}")
    print(f"Wrote {COMPARISON_TABLE}")
    return out


def label_frame(points, tag: str):
    """Cluster label per location, keyed so the two arms can be joined."""
    return pd.DataFrame(
        {"key": location_keys(points).astype(str), f"cluster_{tag}": points["HDB_cluster"].to_numpy()}
    )


def paired_labels(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> pd.DataFrame:
    """The locations present in both runs, with the label each run gave them."""
    merged = label_frame(a, "gsvi").merge(label_frame(b, "gsc"), on="key", how="inner")
    return merged.drop_duplicates(subset="key")


def agreement_scores(paired: pd.DataFrame) -> dict:
    """Threshold-free agreement between the two labellings of the shared points.

    Noise (-1) is kept as its own label rather than dropped: a location moving
    between noise and a cluster is a real change in the result, not a missing
    value.
    """
    a = paired["cluster_gsvi"].to_numpy()
    b = paired["cluster_gsc"].to_numpy()
    same_noise = int(((a == -1) & (b == -1)).sum())
    gained = int(((a == -1) & (b != -1)).sum())
    lost = int(((a != -1) & (b == -1)).sum())
    both_clustered = (a != -1) & (b != -1)
    return {
        "n_shared": len(paired),
        "adjusted_rand_index": float(adjusted_rand_score(a, b)),
        "normalised_mutual_info": float(normalized_mutual_info_score(a, b)),
        "n_clustered_in_both": int(both_clustered.sum()),
        "n_noise_in_both": same_noise,
        "n_noise_to_cluster": gained,
        "n_cluster_to_noise": lost,
        # Among points clustered in both runs, how often do two locations that
        # shared a GSVI cluster still share a combined cluster?
        "ari_clustered_only": float(adjusted_rand_score(a[both_clustered], b[both_clustered])),
    }


def transition_matrix(paired: pd.DataFrame) -> pd.DataFrame:
    """GSVI cluster (rows) x combined cluster (columns), counts of shared locations."""
    label = lambda v: "Noise" if v == -1 else str(int(v))  # noqa: E731
    out = paired.assign(
        gsvi=paired["cluster_gsvi"].map(label), gsc=paired["cluster_gsc"].map(label)
    )
    ct = pd.crosstab(out["gsvi"], out["gsc"], margins=True, margins_name="Total")

    def order(values):
        nums = sorted((v for v in values if v not in {"Noise", "Total"}), key=int)
        return [*nums, *(v for v in ("Noise", "Total") if v in values)]

    ct = ct.reindex(index=order(ct.index), columns=order(ct.columns)).fillna(0).astype(int)
    ct.to_csv(TRANSITIONS_CSV)
    print(f"Wrote {TRANSITIONS_CSV}")
    return ct


def cluster_fates(paired: pd.DataFrame) -> pd.DataFrame:
    """Per GSVI cluster: which combined cluster took its locations, and was it a merge?

    Written onto the GSVI hull layer so the map can show the merge directly
    instead of leaving it to the transition matrix alone.
    """
    clustered = paired[paired["cluster_gsvi"] != -1]
    dest = clustered.groupby("cluster_gsvi")["cluster_gsc"].agg(
        lambda s: s.value_counts().idxmax()
    )
    purity = clustered.groupby("cluster_gsvi")["cluster_gsc"].agg(
        lambda s: s.value_counts().iloc[0] / len(s)
    )
    absorbed = dest[dest != -1].value_counts()
    merged_dests = set(absorbed[absorbed > 1].index)
    return pd.DataFrame(
        {
            "HDB_cluster": dest.index.astype(int),
            "dest_cluster": dest.to_numpy(),
            "dest_purity": purity.to_numpy(),
            "fate": [
                "Dissolved into noise" if d == -1
                else ("Merged with other hotspots" if d in merged_dests else "Preserved one-to-one")
                for d in dest.to_numpy()
            ],
        }
    )


def merge_summary(paired: pd.DataFrame) -> dict:
    """How the 24 GSVI clusters map onto the combined ones."""
    clustered = paired[(paired["cluster_gsvi"] != -1)]
    # Each GSVI cluster's dominant destination among the combined labels.
    dest = (
        clustered.groupby("cluster_gsvi")["cluster_gsc"]
        .agg(lambda s: s.value_counts().idxmax())
    )
    purity = (
        clustered.groupby("cluster_gsvi")["cluster_gsc"]
        .agg(lambda s: s.value_counts().iloc[0] / len(s))
    )
    real_dest = dest[dest != -1]
    absorbed = real_dest.value_counts()
    return {
        "n_gsvi_clusters": int(clustered["cluster_gsvi"].nunique()),
        "n_gsvi_clusters_to_noise": int((dest == -1).sum()),
        "n_combined_clusters_absorbing": int(real_dest.nunique()),
        "n_merged_pairs": int((absorbed > 1).sum()),
        "n_gsvi_clusters_in_merges": int(absorbed[absorbed > 1].sum()),
        "median_destination_purity": float(purity.median()),
        "min_destination_purity": float(purity.min()),
    }


def share(part: int, whole: int) -> str:
    return "0 (0.0%)" if whole == 0 else f"{part:,} ({100.0 * part / whole:.1f}%)"


def new_locations(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Locations present in the combined arm but not in GSVI."""
    gsvi_keys = set(location_keys(a))
    return b.loc[~location_keys(b).isin(gsvi_keys)].copy()


def build_new_locations_table(a: dict, b: dict, paired: pd.DataFrame) -> pd.DataFrame:
    """What the 149 added locations join, by label rather than by geometry."""
    new = new_locations(a["points"], b["points"])
    n_new = len(new)

    # Which combined clusters contain at least one location GSVI already had?
    established = set(paired.loc[paired["cluster_gsc"] != -1, "cluster_gsc"].unique())
    labels = new["HDB_cluster"].to_numpy()

    n_noise = int((labels == -1).sum())
    n_existing = int(np.isin(labels, list(established)).sum())
    n_novel = n_new - n_noise - n_existing
    novel_clusters = sorted(set(labels) - established - {-1})

    out = pd.DataFrame(
        [
            {"Metric": "New locations added", "Value": f"{n_new:,}"},
            {"Metric": "Joined a cluster that already held GSVI locations",
             "Value": share(n_existing, n_new)},
            {"Metric": "Formed a cluster with no GSVI locations in it",
             "Value": share(n_novel, n_new)},
            {"Metric": "Did not cluster (noise)", "Value": share(n_noise, n_new)},
            {"Metric": "Clusters made only of self-collected locations",
             "Value": f"{len(novel_clusters):,}"},
        ]
    )
    out.to_csv(NEW_LOCATIONS_CSV, index=False)
    print(f"\n{out.to_string(index=False)}")
    print(f"Wrote {NEW_LOCATIONS_CSV}")
    return out


def build_stability_table(scores: dict, merges: dict) -> pd.DataFrame:
    rows = [
        ("Locations present in both runs", f"{scores['n_shared']:,}"),
        ("Adjusted Rand Index", f"{scores['adjusted_rand_index']:.3f}"),
        ("Normalised mutual information", f"{scores['normalised_mutual_info']:.3f}"),
        ("ARI among locations clustered in both", f"{scores['ari_clustered_only']:.3f}"),
        ("Clustered in both runs", f"{scores['n_clustered_in_both']:,}"),
        ("Noise in both runs", f"{scores['n_noise_in_both']:,}"),
        ("Noise → clustered", f"{scores['n_noise_to_cluster']:,}"),
        ("Clustered → noise", f"{scores['n_cluster_to_noise']:,}"),
        ("GSVI clusters whose locations mostly became noise",
         f"{merges['n_gsvi_clusters_to_noise']} / {merges['n_gsvi_clusters']}"),
        ("Combined clusters absorbing them", f"{merges['n_combined_clusters_absorbing']}"),
        ("Combined clusters absorbing 2+ GSVI clusters", f"{merges['n_merged_pairs']}"),
        ("GSVI clusters involved in a merge", f"{merges['n_gsvi_clusters_in_merges']}"),
        ("Median destination purity", f"{100 * merges['median_destination_purity']:.1f}%"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "Value"])
    print(f"\nCluster-label stability on the shared locations:\n{out.to_string(index=False)}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"HDBSCAN (min_cluster_size={MIN_CLUSTER_SIZE}, min_samples={MIN_SAMPLES}), "
          "identical on both arms\n")

    gsvi = run_arm("gsvi")
    combined = run_arm("gsvi_selfcollected")

    build_comparison(gsvi, combined)

    paired = paired_labels(gsvi["points"], combined["points"])
    scores = agreement_scores(paired)
    merges = merge_summary(paired)
    fates = cluster_fates(paired)
    hulls = gsvi["hulls"].merge(fates, on="HDB_cluster", how="left")
    hulls["fate"] = hulls["fate"].fillna("Preserved one-to-one")
    hulls.to_file(hotspots_gpkg("gsvi"), driver="GPKG")
    print(f"\nGSVI hull fates written to {hotspots_gpkg('gsvi').name}:")
    print(hulls["fate"].value_counts().to_string())

    ct = transition_matrix(paired)
    print(f"\nGSVI cluster (rows) x combined cluster (columns), shared locations:")
    print(ct.to_string())
    stability = build_stability_table(scores, merges)
    stability.to_csv(TABLE_DIR / "table_6_4_hdbscan_stability.csv", index=False)
    print(f"Wrote {TABLE_DIR / 'table_6_4_hdbscan_stability.csv'}")

    build_new_locations_table(gsvi, combined, paired)


if __name__ == "__main__":
    main()

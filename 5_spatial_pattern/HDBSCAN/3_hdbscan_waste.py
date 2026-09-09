"""
HDBSCAN clustering of Nairobi waste locations — panorama level.

Arms (identical HDBSCAN settings):
  - gsvi: waste-positive GSVI panoids from Step 2c (n ≈ 2,696)
  - gsvi_selfcollected: those panoids + Faith/ZWL locations (n ≈ 2,845)
"""

from __future__ import annotations

import sys
from pathlib import Path

import hdbscan
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    load_gsvi_selfcollected_locations,
    load_gsvi_waste_panoids,
)

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"

MIN_CLUSTER_SIZE = 25
MIN_SAMPLES = 6

DATASETS = {
    "gsvi": {
        "label": "GSVI waste-positive panoids",
        "loader": load_gsvi_waste_panoids,
        "output_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        "output_summary": OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_gsvi.csv",
    },
    "gsvi_selfcollected": {
        "label": "GSVI panoids + self-collected locations",
        "loader": load_gsvi_selfcollected_locations,
        "output_gpkg": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        "output_summary": OUTPUT_DIR
        / "Nairobi_waste_hdbscan_summary_gsvi_selfcollected.csv",
    },
}


def run_hdbscan(gdf):
    coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        gen_min_span_tree=True,
    )
    labels = clusterer.fit_predict(coords)

    out = gdf.copy()
    out["HDB_cluster"] = labels

    n_noise = int((labels == -1).sum())
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    summary = {
        "min_cluster_size": MIN_CLUSTER_SIZE,
        "min_samples": MIN_SAMPLES,
        "n_points": len(labels),
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "noise_ratio": n_noise / len(labels),
        "unit": "panorama_location",
    }
    return out, summary


def process_dataset(key: str) -> dict:
    meta = DATASETS[key]
    gdf = meta["loader"]()
    clustered, summary = run_hdbscan(gdf)
    summary["dataset"] = key
    summary["label"] = meta["label"]

    clustered.to_file(meta["output_gpkg"], driver="GPKG")
    pd.DataFrame([summary]).to_csv(meta["output_summary"], index=False)

    print(f"[{key}] {meta['label']}")
    print(f"  Wrote {meta['output_gpkg']}")
    print(f"  Locations: {summary['n_points']:,}")
    print(f"  Clusters:  {summary['n_clusters']}")
    print(f"  Noise:     {summary['n_noise']:,} ({100 * summary['noise_ratio']:.1f}%)")
    if "location_kind" in clustered.columns:
        counts = clustered["location_kind"].value_counts()
        print(
            "  By kind:",
            ", ".join(f"{k}={v:,}" for k, v in counts.items()),
        )

    return summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summaries = [
        process_dataset("gsvi"),
        process_dataset("gsvi_selfcollected"),
    ]

    comparison_path = OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_comparison.csv"
    pd.DataFrame(summaries).to_csv(comparison_path, index=False)
    print(f"Wrote {comparison_path}")


if __name__ == "__main__":
    main()

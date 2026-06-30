"""
3. HDBSCAN clustering of Nairobi waste points — gsvi vs gsvi_selfcollected arms.

Runs two comparable analyses with identical HDBSCAN settings:
  - gsvi: Google Street View only (Step 1 harmonised layer)
  - gsvi_selfcollected: full Correct_SVI including Faith/ and ZWL/
"""

from pathlib import Path

import geopandas as gpd
import hdbscan
import numpy as np
import pandas as pd

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_cluster_mitigation"

GSVI_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
GSVI_SELF_COLLECTED_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg"

MIN_CLUSTER_SIZE = 25
MIN_SAMPLES = 6

DATASETS = {
    "gsvi": {
        "label": "GSVI only (Google)",
        "input_gpkg": GSVI_GPKG,
        "output_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        "output_summary": OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_gsvi.csv",
    },
    "gsvi_selfcollected": {
        "label": "GSVI + self-collected (Faith/ + ZWL/)",
        "input_gpkg": GSVI_SELF_COLLECTED_GPKG,
        "output_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        "output_summary": OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_gsvi_selfcollected.csv",
    },
}


def run_hdbscan(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
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
    }
    return out, summary


def process_dataset(key: str) -> dict:
    meta = DATASETS[key]
    gdf = gpd.read_file(meta["input_gpkg"])
    clustered, summary = run_hdbscan(gdf)
    summary["dataset"] = key
    summary["label"] = meta["label"]

    clustered.to_file(meta["output_gpkg"], driver="GPKG")
    pd.DataFrame([summary]).to_csv(meta["output_summary"], index=False)

    print(f"[{key}] {meta['label']}")
    print(f"  Wrote {meta['output_gpkg']}")
    print(f"  Points:   {summary['n_points']:,}")
    print(f"  Clusters: {summary['n_clusters']}")
    print(f"  Noise:    {summary['n_noise']:,} ({100 * summary['noise_ratio']:.1f}%)")
    if "source" in clustered.columns:
        counts = clustered["source"].value_counts()
        print("  By source:", ", ".join(f"{k}={v:,}" for k, v in counts.items()))

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

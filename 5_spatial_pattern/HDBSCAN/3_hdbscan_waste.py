"""
HDBSCAN clustering of Nairobi waste locations — panorama level (GSVI arm).

Arms (identical HDBSCAN settings):
  - gsvi: waste-positive GSVI panoids from Step 2c (n ≈ 2,696)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.hdbscan_fit import cluster_points  # noqa: E402
from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    load_gsvi_waste_panoids,
)

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"

DATASETS = {
    "gsvi": {
        "label": "GSVI waste-positive panoids",
        "loader": load_gsvi_waste_panoids,
        "output_gpkg": OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        "output_summary": OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_gsvi.csv",
    },
}


def process_dataset(key: str) -> dict:
    meta = DATASETS[key]
    gdf = meta["loader"]()
    clustered, summary = cluster_points(gdf)
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
    ]

    comparison_path = OUTPUT_DIR / "Nairobi_waste_hdbscan_summary_comparison.csv"
    pd.DataFrame(summaries).to_csv(comparison_path, index=False)
    print(f"Wrote {comparison_path}")


if __name__ == "__main__":
    main()

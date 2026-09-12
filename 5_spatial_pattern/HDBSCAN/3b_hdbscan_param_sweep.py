"""
HDBSCAN parameter sweep for the GSVI waste-positive panoids.

Sweeps min_cluster_size 15–40 and min_samples 4–10, reporting:
  noise_ratio, n_clusters, avg_persistence, silhouette_score.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import hdbscan
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.panoids import PATTERN_DIR, load_gsvi_waste_panoids  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"

MIN_CLUSTER_SIZES = [15, 20, 25, 30, 35, 40]
MIN_SAMPLES_LIST = [4, 5, 6, 8, 10]


def sweep_one(coords: np.ndarray, mcs: int, ms: int) -> dict:
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=mcs,
        min_samples=ms,
        gen_min_span_tree=True,
    )
    labels = clusterer.fit_predict(coords)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    noise_ratio = n_noise / len(labels)

    avg_persistence = float(np.mean(clusterer.cluster_persistence_)) if n_clusters > 0 else 0.0

    mask = labels != -1
    if mask.sum() > 1 and n_clusters > 1:
        sil = float(silhouette_score(coords[mask], labels[mask]))
    else:
        sil = np.nan

    return {
        "min_cluster_size": mcs,
        "min_samples": ms,
        "noise_ratio": round(noise_ratio, 4),
        "n_clusters": n_clusters,
        "avg_persistence": round(avg_persistence, 4),
        "silhouette_score": round(sil, 4) if not np.isnan(sil) else np.nan,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    gdf = load_gsvi_waste_panoids()
    coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    print(f"Loaded {len(coords):,} waste-positive panoid locations")

    combos = list(itertools.product(MIN_CLUSTER_SIZES, MIN_SAMPLES_LIST))
    print(f"Running {len(combos)} parameter combinations …")

    rows = []
    for mcs, ms in combos:
        row = sweep_one(coords, mcs, ms)
        rows.append(row)
        print(
            f"  mcs={mcs:3d}  ms={ms:2d}  →  "
            f"clusters={row['n_clusters']:3d}  "
            f"noise={row['noise_ratio']:.4f}  "
            f"persist={row['avg_persistence']:.4f}  "
            f"silhouette={row['silhouette_score']}"
        )

    df = pd.DataFrame(rows)
    out_csv = OUTPUT_DIR / "Nairobi_hdbscan_param_sweep.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

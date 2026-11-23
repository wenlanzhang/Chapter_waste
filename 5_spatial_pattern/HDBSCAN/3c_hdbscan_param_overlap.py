"""
Does the HDBSCAN result change *where* the hotspots are, or only how they are split?

3b_hdbscan_param_sweep.py shows the number of clusters ranging from 15 to 49
across min_cluster_size 15–40 x min_samples 4–10. A count can change in two
very different ways: hotspots appear or disappear, or the same hotspot areas
are cut into more or fewer pieces. This script separates the two by comparing
every alternative labelling with the primary one (min_cluster_size 25,
min_samples 6) on the same 2,696 waste-positive panoramas.

Same approach as Step 6.4a: agreement is measured on the cluster label each
panorama receives, not on hull geometry, so there is no overlap threshold and
no dependence on how a footprint is drawn. Noise (-1) is a label of its own.

Per parameter combination:
  n_clusters, pct_clustered       as in the sweep
  jaccard_clustered               |clustered in both| / |clustered in either|
  primary_retained                share of primary-clustered panoramas still in a cluster
  alt_from_primary                share of alternative-clustered panoramas that were
                                  in a primary cluster (1 - share drawn from primary noise)
  split_nesting                   among panoramas clustered in both: share whose
                                  alternative cluster lies mainly inside their own
                                  primary cluster (high = alternative clusters are
                                  subdivisions of primary ones)
  merge_nesting                   the reverse: share whose primary cluster lies mainly
                                  inside their own alternative cluster (high = primary
                                  clusters are pieces of larger alternative ones)
  primary_dissolved               primary clusters whose panoramas mostly became noise
  alt_new                         alternative clusters whose panoramas were mostly
                                  primary noise (new hotspot areas)
  ari, nmi                        adjusted Rand index / normalised mutual information,
                                  noise kept as a label

Outputs (PATTERN_DIR/HDBSCAN/):
  Nairobi_hdbscan_param_overlap.csv          one row per combination
  thesis_table/hdbscan_param_overlap.csv     summary across combinations
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.hdbscan_fit import MIN_CLUSTER_SIZE, MIN_SAMPLES, cluster_labels  # noqa: E402
from lib.panoids import PATTERN_DIR, load_gsvi_waste_panoids  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
OUT_CSV = OUTPUT_DIR / "Nairobi_hdbscan_param_overlap.csv"
THESIS_CSV = OUTPUT_DIR / "thesis_table" / "hdbscan_param_overlap.csv"

# Same grid as 3b_hdbscan_param_sweep.py.
MIN_CLUSTER_SIZES = [15, 20, 25, 30, 35, 40]
MIN_SAMPLES_LIST = [4, 5, 6, 8, 10]


def nesting(inner: np.ndarray, outer: np.ndarray) -> float:
    """Share of points whose `inner` cluster lies mainly inside their own `outer` cluster.

    For each inner cluster, find the outer cluster holding most of its points;
    a point counts as nested if that dominant outer cluster is its own. This is
    the point-weighted purity of the inner labelling with respect to the outer.
    """
    df = pd.DataFrame({"inner": inner, "outer": outer})
    dominant = df.groupby("inner")["outer"].agg(lambda s: s.value_counts().idxmax())
    return float((df["inner"].map(dominant) == df["outer"]).mean())


def compare(primary: np.ndarray, alt: np.ndarray) -> dict:
    p_cl, a_cl = primary != -1, alt != -1
    both = p_cl & a_cl

    # Fate of each primary cluster: where do most of its panoramas go?
    p_df = pd.DataFrame({"p": primary[p_cl], "a": alt[p_cl]})
    p_dest = p_df.groupby("p")["a"].agg(lambda s: s.value_counts().idxmax())
    # Origin of each alternative cluster: where did most of its panoramas come from?
    a_df = pd.DataFrame({"a": alt[a_cl], "p": primary[a_cl]})
    a_orig = a_df.groupby("a")["p"].agg(lambda s: s.value_counts().idxmax())

    return {
        "n_clusters": int(len(set(alt)) - (1 if -1 in alt else 0)),
        "pct_clustered": 100.0 * a_cl.mean(),
        "jaccard_clustered": both.sum() / (p_cl | a_cl).sum(),
        "primary_retained": both.sum() / p_cl.sum(),
        "alt_from_primary": both.sum() / a_cl.sum() if a_cl.any() else np.nan,
        "split_nesting": nesting(alt[both], primary[both]),
        "merge_nesting": nesting(primary[both], alt[both]),
        "primary_dissolved": int((p_dest == -1).sum()),
        "alt_new": int((a_orig == -1).sum()),
        "ari": adjusted_rand_score(primary, alt),
        "nmi": normalized_mutual_info_score(primary, alt),
    }


def main() -> None:
    gdf = load_gsvi_waste_panoids()
    print(f"Loaded {len(gdf):,} waste-positive panoramas")
    primary = cluster_labels(gdf)
    n_primary = len(set(primary)) - (1 if -1 in primary else 0)
    print(f"Primary (min_cluster_size {MIN_CLUSTER_SIZE}, min_samples {MIN_SAMPLES}): {n_primary} clusters")

    rows = []
    for mcs, ms in itertools.product(MIN_CLUSTER_SIZES, MIN_SAMPLES_LIST):
        alt = cluster_labels(gdf, min_cluster_size=mcs, min_samples=ms)
        row = {"min_cluster_size": mcs, "min_samples": ms,
               "primary": (mcs, ms) == (MIN_CLUSTER_SIZE, MIN_SAMPLES), **compare(primary, alt)}
        rows.append(row)
        print(
            f"  mcs={mcs:2d} ms={ms:2d}: {row['n_clusters']:2d} clusters  "
            f"Jaccard {row['jaccard_clustered']:.3f}  retained {row['primary_retained']:.3f}  "
            f"split-nest {row['split_nesting']:.3f}  merge-nest {row['merge_nesting']:.3f}  "
            f"dissolved {row['primary_dissolved']}  new {row['alt_new']}"
        )

    out = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")

    alt = out[~out["primary"]]

    def rng(col: str, fmt: str = "{:.2f}") -> str:
        return f"{fmt.format(alt[col].median())} ({fmt.format(alt[col].min())}–{fmt.format(alt[col].max())})"

    thesis = pd.DataFrame(
        [
            ("Parameter combinations compared with the primary", f"{len(alt)}", ""),
            ("Number of clusters", rng("n_clusters", "{:.0f}"), f"primary {n_primary}"),
            ("Panoramas clustered (%)", rng("pct_clustered", "{:.1f}"), f"primary {100 * (primary != -1).mean():.1f}"),
            ("Jaccard overlap of clustered panoramas", rng("jaccard_clustered"), "1 = identical hotspot membership"),
            ("Primary-clustered panoramas still clustered", rng("primary_retained"), ""),
            ("Alternative-clustered panoramas that were in a primary cluster", rng("alt_from_primary"), ""),
            ("Alternative clusters nested in one primary cluster (point share)", rng("split_nesting"), "splits"),
            ("Primary clusters nested in one alternative cluster (point share)", rng("merge_nesting"), "merges"),
            ("Primary clusters dissolved into noise", rng("primary_dissolved", "{:.0f}"), f"of {n_primary}"),
            ("New hotspot areas (alternative clusters mostly from primary noise)", rng("alt_new", "{:.0f}"), ""),
            ("Adjusted Rand index", rng("ari"), "noise kept as a label"),
            ("Normalised mutual information", rng("nmi"), "noise kept as a label"),
        ],
        columns=["Measure", "Median (min–max) across combinations", "Note"],
    )
    THESIS_CSV.parent.mkdir(parents=True, exist_ok=True)
    thesis.to_csv(THESIS_CSV, index=False)
    print(f"Wrote {THESIS_CSV}")
    print(thesis.to_string(index=False))


if __name__ == "__main__":
    main()

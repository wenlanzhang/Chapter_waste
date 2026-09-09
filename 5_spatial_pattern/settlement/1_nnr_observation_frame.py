#!/usr/bin/env python3
"""Observation-frame nearest-neighbour ratio (NNR) for waste-positive panoids.

Primary null: mean 1-NN distance among the 2,696 waste-positive GSVI panoids
compared with random draws of the same size from the 76,605 available GSVI
panoramas (road / platform observation frame).

Optional appendix: classic Clark–Evans CSR over the city polygon area.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    load_boundary,
    load_sviwaste_points,
)

OUTPUT_DIR = PATTERN_DIR / "settlement"
TABLE_DIR = OUTPUT_DIR / "thesis_table"
N_PERM = 999
RNG_SEED = 42


def mean_nn_distance(coords: np.ndarray) -> float:
    nbrs = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(coords)
    distances, _ = nbrs.kneighbors(coords)
    return float(distances[:, 1].mean())


def clark_evans_csr(n_points: int, study_area_m2: float, d_obs: float) -> dict:
    intensity = n_points / study_area_m2
    d_csr = 0.5 / np.sqrt(intensity)
    se = 0.26136 / np.sqrt(n_points * intensity)
    z = (d_obs - d_csr) / se
    return {
        "d_csr_m": d_csr,
        "nnr_csr": d_obs / d_csr,
        "z_csr": z,
        "study_area_km2": study_area_m2 / 1e6,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Observation-frame NNR (waste-positive panoids vs GSVI sampling frame)...")
    points = load_sviwaste_points()
    coords_all = np.column_stack([points.geometry.x.values, points.geometry.y.values])
    waste_mask = points["waste_positive"].to_numpy() == 1
    coords_waste = coords_all[waste_mask]

    n_all = len(points)
    n_waste = int(waste_mask.sum())
    d_obs = mean_nn_distance(coords_waste)

    rng = np.random.default_rng(RNG_SEED)
    null_means = np.empty(N_PERM, dtype=float)
    for i in range(N_PERM):
        idx = rng.choice(n_all, size=n_waste, replace=False)
        null_means[i] = mean_nn_distance(coords_all[idx])

    null_mean = float(null_means.mean())
    null_std = float(null_means.std(ddof=1))
    null_lo, null_hi = np.quantile(null_means, [0.025, 0.975])
    nnr_obs_frame = d_obs / null_mean
    # One-sided: more clustered than random draws → smaller mean NN
    p_value = float((np.sum(null_means <= d_obs) + 1) / (N_PERM + 1))

    boundary = load_boundary()
    study_area = float(boundary.geometry.area.sum())
    csr = clark_evans_csr(n_waste, study_area, d_obs)

    summary = {
        "n_gsvi_panoids": n_all,
        "n_waste_positive_panoids": n_waste,
        "d_obs_m": d_obs,
        "null_mean_m": null_mean,
        "null_std_m": null_std,
        "null_ci_low_m": float(null_lo),
        "null_ci_high_m": float(null_hi),
        "nnr_observation_frame": nnr_obs_frame,
        "p_value_one_sided": p_value,
        "n_permutations": N_PERM,
        "rng_seed": RNG_SEED,
        **csr,
    }

    summary_path = OUTPUT_DIR / "Nairobi_nnr_observation_frame_summary.csv"
    pd.DataFrame([summary]).to_csv(summary_path, index=False)

    null_path = OUTPUT_DIR / "Nairobi_nnr_null_mean_nn_distances.csv"
    pd.DataFrame({"d_null_m": null_means}).to_csv(null_path, index=False)

    thesis = pd.DataFrame(
        [
            ("GSVI panoids (sampling frame)", f"{n_all:,}", ""),
            ("Waste-positive panoids", f"{n_waste:,}", ""),
            ("Observed mean NN distance", f"{d_obs:.1f}", "m"),
            ("Null mean NN distance", f"{null_mean:.1f}", "m"),
            ("Null SD", f"{null_std:.1f}", "m"),
            ("Null 2.5th percentile", f"{null_lo:.1f}", "m"),
            ("Null 97.5th percentile", f"{null_hi:.1f}", "m"),
            ("Observation-conditioned ratio (NNR)", f"{nnr_obs_frame:.3f}", ""),
            ("Empirical one-sided p-value", f"{p_value:.4f}", ""),
            ("Permutations", f"{N_PERM:,}", ""),
            ("CSR expected mean NN (appendix)", f"{csr['d_csr_m']:.1f}", "m"),
            ("Clark–Evans NNR (appendix)", f"{csr['nnr_csr']:.3f}", ""),
            ("Clark–Evans Z (appendix)", f"{csr['z_csr']:.2f}", ""),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / "nnr_observation_frame.csv"
    thesis.to_csv(thesis_path, index=False)

    print(f"  Waste-positive panoids: {n_waste:,} / {n_all:,}")
    print(f"  d_obs:                  {d_obs:.2f} m")
    print(f"  null mean ± SD:         {null_mean:.2f} ± {null_std:.2f} m")
    print(f"  null 95% interval:      {null_lo:.2f}–{null_hi:.2f} m")
    print(f"  observation-frame NNR:  {nnr_obs_frame:.4f}")
    print(f"  one-sided p-value:      {p_value:.4f}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {null_path}")
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

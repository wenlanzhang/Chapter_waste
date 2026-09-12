#!/usr/bin/env python3
"""Experiment 5: temporal robustness at panorama level.

Within each capture year (pooling rare years), recompute:
  - settlement positive rates / prevalence ratio / odds ratio
  - observation-frame NNR (if enough waste-positive panoramas)

Unit: one row per GSVI panoid (not directional images).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
)

OUTPUT_DIR = PATTERN_DIR / "settlement"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

MIN_YEAR_N = 200
MIN_WASTE_FOR_NNR = 50
N_PERM = 999
RNG_SEED = 42


def odds_ratio_with_ci(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    if min(a, b, c, d) <= 0:
        return np.nan, np.nan, np.nan
    odds_ratio = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    lo = math.exp(math.log(odds_ratio) - 1.96 * se)
    hi = math.exp(math.log(odds_ratio) + 1.96 * se)
    return float(odds_ratio), float(lo), float(hi)


def mean_nn_distance(coords: np.ndarray) -> float:
    nbrs = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(coords)
    distances, _ = nbrs.kneighbors(coords)
    return float(distances[:, 1].mean())


def observation_frame_nnr(
    coords_all: np.ndarray,
    waste_mask: np.ndarray,
    rng: np.random.Generator,
) -> dict:
    n_all = len(coords_all)
    n_waste = int(waste_mask.sum())
    if n_waste < MIN_WASTE_FOR_NNR or n_waste >= n_all:
        return {
            "n_waste_positive": n_waste,
            "d_obs_m": np.nan,
            "null_mean_m": np.nan,
            "nnr_observation_frame": np.nan,
            "p_value_one_sided": np.nan,
            "nnr_ran": 0,
        }

    coords_waste = coords_all[waste_mask]
    d_obs = mean_nn_distance(coords_waste)
    null_means = np.empty(N_PERM, dtype=float)
    for i in range(N_PERM):
        idx = rng.choice(n_all, size=n_waste, replace=False)
        null_means[i] = mean_nn_distance(coords_all[idx])
    null_mean = float(null_means.mean())
    p_value = float((np.sum(null_means <= d_obs) + 1) / (N_PERM + 1))
    return {
        "n_waste_positive": n_waste,
        "d_obs_m": d_obs,
        "null_mean_m": null_mean,
        "nnr_observation_frame": d_obs / null_mean if null_mean > 0 else np.nan,
        "p_value_one_sided": p_value,
        "nnr_ran": 1,
    }


def settlement_rates(waste: np.ndarray, inside: np.ndarray) -> dict:
    a = int((waste & inside).sum())
    b = int((~waste & inside).sum())
    c = int((waste & ~inside).sum())
    d = int((~waste & ~inside).sum())
    n_inside = a + b
    n_outside = c + d
    p_inside = a / n_inside if n_inside else np.nan
    p_outside = c / n_outside if n_outside else np.nan
    pr = p_inside / p_outside if p_outside and p_outside > 0 else np.nan
    odds_ratio, or_lo, or_hi = odds_ratio_with_ci(a, b, c, d)
    return {
        "n_panoids": a + b + c + d,
        "n_waste_positive": a + c,
        "waste_inside_a": a,
        "nonwaste_inside_b": b,
        "waste_outside_c": c,
        "nonwaste_outside_d": d,
        "positive_rate_inside": p_inside,
        "positive_rate_outside": p_outside,
        "prevalence_ratio": pr,
        "odds_ratio": odds_ratio,
        "odds_ratio_ci_low": or_lo,
        "odds_ratio_ci_high": or_hi,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Temporal robustness (panorama unit, by year)...")
    points = enrich_sviwaste_frame()
    slums = load_slums()
    points = label_inside_settlement(points, slums)
    points["year"] = pd.to_numeric(points["year"], errors="coerce")
    points = points.dropna(subset=["year"]).copy()
    points["year"] = points["year"].astype(int)

    year_counts = points["year"].value_counts()
    rare = set(year_counts[year_counts < MIN_YEAR_N].index.tolist())
    points["year_period"] = points["year"].astype(str)
    if rare:
        points.loc[points["year"].isin(rare), "year_period"] = "other"
        print(f"  Pooled rare years into 'other': {sorted(rare)}")

    coords_all = np.column_stack([points.geometry.x.values, points.geometry.y.values])
    waste_all = points["waste_positive"].to_numpy() == 1
    inside_all = points["inside_settlement"].to_numpy() == 1

    rng = np.random.default_rng(RNG_SEED)
    rows = []

    # Overall (all years) for reference
    overall = settlement_rates(waste_all, inside_all)
    overall_nnr = observation_frame_nnr(coords_all, waste_all, rng)
    rows.append({"year_period": "all", **overall, **overall_nnr})

    for period in sorted(points["year_period"].unique().tolist()):
        mask = points["year_period"].to_numpy() == period
        rates = settlement_rates(waste_all[mask], inside_all[mask])
        nnr = observation_frame_nnr(coords_all[mask], waste_all[mask], rng)
        rows.append({"year_period": period, **rates, **nnr})
        print(
            f"  {period}: n={rates['n_panoids']:,} | waste+={rates['n_waste_positive']:,} | "
            f"PR={rates['prevalence_ratio']:.2f}"
            + (
                f" | NNR={nnr['nnr_observation_frame']:.3f}"
                if nnr["nnr_ran"]
                else " | NNR=skipped"
            )
        )

    out = pd.DataFrame(rows)
    out_path = OUTPUT_DIR / "Nairobi_temporal_robustness_by_year.csv"
    out.to_csv(out_path, index=False)

    thesis = out[
        [
            "year_period",
            "n_panoids",
            "n_waste_positive",
            "positive_rate_inside",
            "positive_rate_outside",
            "prevalence_ratio",
            "odds_ratio",
            "nnr_observation_frame",
            "p_value_one_sided",
        ]
    ].copy()
    thesis_path = TABLE_DIR / "temporal_robustness.csv"
    thesis.to_csv(thesis_path, index=False)

    print(f"Wrote {out_path}")
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

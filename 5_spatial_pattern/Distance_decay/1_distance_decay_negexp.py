#!/usr/bin/env python3
"""Distance-decay and NegExp modelling to urban-poor settlement boundaries.

Panorama (panoid) unit. Supplement to settlement association (χ² / density):

  - unsigned distance group summaries and threshold table
  - two-sample KS (waste+ vs non+)
  - empirical CDFs + NegExp P(x)=a(1-e^{-bx}) fits (waste+ vs all GSVI)
  - panoid-level distance export (unsigned + signed)

Outputs under Data/.../5_spatial_pattern/Distance_decay/ (not the code tree).
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import ks_2samp
from shapely.ops import unary_union

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

OUTPUT_DIR = PATTERN_DIR / "Distance_decay"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

DIST_MAX_M = 3000
DIST_STEP_M = 10
DIST_THRESHOLDS_M = (0, 250, 500, 1000)


def negexp(x: np.ndarray, a: float, b: float) -> np.ndarray:
    return a * (1.0 - np.exp(-b * x))


def fit_negexp(distances_m: np.ndarray, grid_m: np.ndarray) -> dict:
    emp = np.array([(distances_m <= d).mean() for d in grid_m], dtype=float)
    if emp.max() <= 0 or np.isnan(emp).any():
        return {
            "a": np.nan,
            "b": np.nan,
            "half_distance_m": np.nan,
            "r2": np.nan,
            "empirical": emp,
            "fitted": np.full_like(emp, np.nan),
        }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            params, _ = curve_fit(
                negexp,
                grid_m,
                emp,
                p0=(min(0.99, float(emp.max())), 0.002),
                bounds=([0.0, 1e-6], [1.0, 1.0]),
                maxfev=20000,
            )
        a, b = (float(params[0]), float(params[1]))
        fitted = negexp(grid_m, a, b)
        ss_res = float(np.sum((emp - fitted) ** 2))
        ss_tot = float(np.sum((emp - emp.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        half = float(np.log(2.0) / b) if b > 0 else np.nan
    except Exception:
        a = b = half = r2 = np.nan
        fitted = np.full_like(emp, np.nan)

    return {
        "a": a,
        "b": b,
        "half_distance_m": half,
        "r2": r2,
        "empirical": emp,
        "fitted": fitted,
    }


def min_distance_to_slums(
    points: gpd.GeoDataFrame, slums: gpd.GeoDataFrame
) -> np.ndarray:
    slum_union = unary_union(slums.geometry)
    return points.geometry.distance(slum_union).to_numpy(dtype=float)


def distance_group_summary(distances_m: np.ndarray, label: str) -> dict:
    q25, q50, q75 = np.percentile(distances_m, [25, 50, 75])
    out = {
        "group": label,
        "n": int(len(distances_m)),
        "median_m": float(q50),
        "p25_m": float(q25),
        "p75_m": float(q75),
        "mean_m": float(np.mean(distances_m)),
    }
    for thr in DIST_THRESHOLDS_M:
        key = "pct_inside_0m" if thr == 0 else f"pct_within_{thr}m"
        out[key] = 100.0 * float((distances_m <= thr).mean())
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Distance-decay / NegExp (GSVI panoids)...")
    print(f"Output directory: {OUTPUT_DIR}")
    points = enrich_sviwaste_frame()
    slums = load_slums()
    points = label_inside_settlement(points, slums)
    waste = points["waste_positive"].to_numpy() == 1

    print("  Computing distances to settlements...")
    dist_all = min_distance_to_slums(points, slums)
    signed_all = signed_distance_to_slums(points, slums)
    dist_pos = dist_all[waste]
    dist_non = dist_all[~waste]

    dist_group = pd.DataFrame(
        [
            distance_group_summary(dist_pos, "waste_positive"),
            distance_group_summary(dist_non, "non_positive"),
        ]
    )
    dist_group_path = OUTPUT_DIR / "Nairobi_distance_group_summary.csv"
    dist_group.to_csv(dist_group_path, index=False)

    thr_rows = []
    for thr in DIST_THRESHOLDS_M:
        label = "Inside settlement, 0 m" if thr == 0 else f"Within {thr} m"
        key = "pct_inside_0m" if thr == 0 else f"pct_within_{thr}m"
        thr_rows.append(
            {
                "Distance threshold": label,
                "Positive panoramas": f"{dist_group.loc[0, key]:.1f}%",
                "Non-positive panoramas": f"{dist_group.loc[1, key]:.1f}%",
            }
        )
    thr_rows.append(
        {
            "Distance threshold": "Median distance",
            "Positive panoramas": f"{dist_group.loc[0, 'median_m']:.1f} m",
            "Non-positive panoramas": f"{dist_group.loc[1, 'median_m']:.1f} m",
        }
    )
    thr_rows.append(
        {
            "Distance threshold": "IQR",
            "Positive panoramas": (
                f"{dist_group.loc[0, 'p25_m']:.1f}–{dist_group.loc[0, 'p75_m']:.1f} m"
            ),
            "Non-positive panoramas": (
                f"{dist_group.loc[1, 'p25_m']:.1f}–{dist_group.loc[1, 'p75_m']:.1f} m"
            ),
        }
    )
    thr_table_path = TABLE_DIR / "distance_thresholds.csv"
    pd.DataFrame(thr_rows).to_csv(thr_table_path, index=False)

    ks = ks_2samp(dist_pos, dist_non, alternative="two-sided")
    ks_summary = {
        "comparison": "waste_positive_vs_non_positive",
        "n_positive": int(len(dist_pos)),
        "n_non_positive": int(len(dist_non)),
        "ks_statistic_D": float(ks.statistic),
        "p_value": float(ks.pvalue),
        "median_positive_m": float(dist_group.loc[0, "median_m"]),
        "median_non_positive_m": float(dist_group.loc[1, "median_m"]),
    }
    ks_path = OUTPUT_DIR / "Nairobi_ks_distance.csv"
    pd.DataFrame([ks_summary]).to_csv(ks_path, index=False)

    grid = np.arange(0, DIST_MAX_M + DIST_STEP_M, DIST_STEP_M, dtype=float)
    emp_pos = np.array([(dist_pos <= d).mean() for d in grid], dtype=float)
    emp_non = np.array([(dist_non <= d).mean() for d in grid], dtype=float)
    emp_all = np.array([(dist_all <= d).mean() for d in grid], dtype=float)

    fit_waste = fit_negexp(dist_pos, grid)
    fit_all = fit_negexp(dist_all, grid)

    cdf = pd.DataFrame(
        {
            "distance_m": grid,
            "emp_waste_positive": emp_pos,
            "emp_non_positive": emp_non,
            "emp_all_gsvi": emp_all,
            "fit_waste_positive": fit_waste["fitted"],
            "fit_all_gsvi": fit_all["fitted"],
        }
    )
    cdf_path = OUTPUT_DIR / "Nairobi_distance_decay_cdf.csv"
    cdf.to_csv(cdf_path, index=False)

    negexp_params = pd.DataFrame(
        [
            {
                "series": "waste_positive",
                "n_points": int(len(dist_pos)),
                "mean_dist_m": float(np.mean(dist_pos)),
                "median_dist_m": float(np.median(dist_pos)),
                "pct_within_500m": 100.0 * float((dist_pos <= 500).mean()),
                "a": fit_waste["a"],
                "b": fit_waste["b"],
                "half_distance_m": fit_waste["half_distance_m"],
                "r2": fit_waste["r2"],
            },
            {
                "series": "all_gsvi",
                "n_points": int(len(dist_all)),
                "mean_dist_m": float(np.mean(dist_all)),
                "median_dist_m": float(np.median(dist_all)),
                "pct_within_500m": 100.0 * float((dist_all <= 500).mean()),
                "a": fit_all["a"],
                "b": fit_all["b"],
                "half_distance_m": fit_all["half_distance_m"],
                "r2": fit_all["r2"],
            },
        ]
    )
    negexp_path = OUTPUT_DIR / "Nairobi_negexp_params.csv"
    negexp_params.to_csv(negexp_path, index=False)

    point_dist = points[
        ["panoid", "waste_positive", "inside_settlement", "year", "n_positive_views"]
    ].copy()
    point_dist["dist_to_slum_m"] = dist_all
    point_dist["signed_distance_m"] = signed_all
    point_dist_path = OUTPUT_DIR / "Nairobi_sviwaste_dist_to_settlement.csv"
    point_dist.to_csv(point_dist_path, index=False)

    thesis = pd.DataFrame(
        [
            ("n waste-positive", f"{int(len(dist_pos)):,}", ""),
            ("n non-positive", f"{int(len(dist_non)):,}", ""),
            ("KS D (positive vs non-positive)", f"{ks.statistic:.3f}", ""),
            ("KS p-value", f"{ks.pvalue:.4g}", ""),
            (
                "Median distance (waste+)",
                f"{dist_group.loc[0, 'median_m']:.1f}",
                "m",
            ),
            (
                "Median distance (non-positive)",
                f"{dist_group.loc[1, 'median_m']:.1f}",
                "m",
            ),
            (
                "NegExp half-distance (waste+)",
                f"{fit_waste['half_distance_m']:.0f}",
                "m",
            ),
            ("NegExp R² (waste+)", f"{fit_waste['r2']:.3f}", ""),
            (
                "NegExp half-distance (all GSVI)",
                f"{fit_all['half_distance_m']:.0f}",
                "m",
            ),
            ("NegExp R² (all GSVI)", f"{fit_all['r2']:.3f}", ""),
            ("Model", "P(x)=a(1-exp(-b x))", "NegExp"),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / "distance_decay_negexp.csv"
    thesis.to_csv(thesis_path, index=False)

    print(
        f"  KS D={ks.statistic:.3f}, p={ks.pvalue:.4g} "
        f"(median pos {dist_group.loc[0, 'median_m']:.1f} m vs "
        f"nonpos {dist_group.loc[1, 'median_m']:.1f} m)"
    )
    print(
        f"  NegExp half-distance waste+={fit_waste['half_distance_m']:.0f} m "
        f"(R²={fit_waste['r2']:.3f})"
    )
    for p in (
        dist_group_path,
        thr_table_path,
        ks_path,
        cdf_path,
        negexp_path,
        point_dist_path,
        thesis_path,
    ):
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()

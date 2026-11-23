#!/usr/bin/env python3
"""Positional uncertainty near settlement boundaries.

A panorama is placed by its camera position, but the waste it shows can lie a
few tens of metres away, across a mapped settlement boundary. Near the
boundary the inside/outside label (and the signed distance) may therefore
describe the camera rather than the waste. This script drops every panorama
within d m of a mapped settlement boundary (|signed distance| <= d), positives
and negatives alike, for d = 25, 50 and 100 m, and recomputes:

  - inside / outside counts, waste-positive rates, prevalence ratio and odds
    ratio, with 2 km spatial block bootstrap intervals
  - the nested population-adjusted GAMs (MP vs MDP) on the remaining panoramas
  - the pop- and year-standardised MDP distance curve, summarised by adjusted
    P(waste) at 250 m and 2 km outside (both clear of every exclusion band)

This tests whether the association depends on panoramas whose label is most
exposed to boundary error. It does not locate waste piles: it only removes
the observations for which camera position and waste position are most likely
to fall on different sides of a boundary.

Runs on the manuscript sample (worldpop_2020/) by default; --data-subdir picks another run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in SCRIPT_DIR.parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.gam import BOOT_SEED, PRED_GRID_N  # noqa: E402
from lib.script_loader import load_script  # noqa: E402


pag = load_script(SCRIPT_DIR / "1_pop_adjusted_gam.py")
bb = load_script(SCRIPT_DIR / "3_spatial_block_bootstrap.py")
cy = load_script(SCRIPT_DIR / "4_capture_year_sensitivity.py")

EXCLUSION_M = (0.0, 25.0, 50.0, 100.0)
BLOCK_M = 2000.0
N_BOOT = 500  # as 3_spatial_block_bootstrap.py
CURVE_PTS_M = (250.0, 2000.0)


def counts(df: pd.DataFrame) -> dict:
    y = df["waste_positive"].astype(int)
    ins = df["inside_settlement"].astype(int) == 1
    depth = -df.loc[ins, "signed_distance_m"]
    return {
        "n_panoramas": len(df),
        "n_positive": int(y.sum()),
        "n_inside": int(ins.sum()),
        "n_positive_inside": int(y[ins].sum()),
        "n_outside": int((~ins).sum()),
        "n_positive_outside": int(y[~ins].sum()),
        "median_depth_inside_m": float(depth.median()) if len(depth) else np.nan,
    }


def curve_points(df: pd.DataFrame, grid: np.ndarray, seed: int) -> tuple[np.ndarray, dict]:
    curve, _ = bb.curve_stats(df, grid, seed)
    p250, p2k = np.interp(CURVE_PTS_M, grid, curve)
    return curve, {
        "curve_p_at_250m_pct": 100 * p250,
        "curve_p_at_2000m_pct": 100 * p2k,
        "curve_ratio_250m_vs_2000m": p250 / p2k if p2k > 0 else np.nan,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-subdir", default=pag.MANUSCRIPT_SUBDIR,
                    help="run folder under pop_adjusted/ (default: worldpop_2020, the manuscript sample)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    base = pag.POP_ADJ_ROOT / args.data_subdir
    out_dir, table_dir = base / "boundary_exclusion", base / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    full = pd.read_csv(base / "Nairobi_pop_adjusted_gam_frame.csv", dtype={"year_fe": str, "panoid": str})
    full["year"] = pd.to_numeric(full["year"], errors="coerce").astype(int)

    grid = np.linspace(
        float(full["signed_distance_m"].quantile(0.01)),
        float(full["signed_distance_m"].quantile(0.99)),
        PRED_GRID_N,
    )

    rows, curves = [], []
    for d in EXCLUSION_M:
        df = full if d == 0 else full.loc[full["signed_distance_m"].abs() > d].reset_index(drop=True)
        c = counts(df)
        print(f"Exclude |signed distance| <= {d:.0f} m: n={c['n_panoramas']:,}, "
              f"inside {c['n_inside']:,} ({c['n_positive_inside']} waste+)")
        fit = cy.fit_all(df)
        curve, cpts = curve_points(df, grid, BOOT_SEED)
        ratios = bb.ratio_measures(df)

        # Same replicate stream as 3_spatial_block_bootstrap.py, so the row with no
        # exclusion reproduces that table's 2 km intervals exactly.
        rng = np.random.default_rng(pag.block_bootstrap_seed(BLOCK_M))
        xy = df[["x", "y"]].to_numpy(dtype=float)
        draws, pr, orr, c250 = [], [], [], []
        for r in range(args.n_boot):
            boot = df.iloc[bb.block_sample(xy, BLOCK_M, rng)].reset_index(drop=True)
            if boot["waste_positive"].nunique() < 2 or boot["inside_settlement"].nunique() < 2:
                continue
            m = bb.ratio_measures(boot)
            pr.append(m["prevalence_ratio"])
            orr.append(m["odds_ratio"])
            try:
                cv, cp = curve_points(boot, grid, BOOT_SEED + r)
            except Exception:
                continue
            draws.append(cv)
            c250.append(cp["curve_ratio_250m_vs_2000m"])
        draws = np.vstack(draws)
        q = lambda a: (float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5)))
        print(f"  block bootstrap: {len(pr)} ratio draws, {len(draws)} curve draws")

        rows.append({
            "exclusion_m": d, **c,
            **ratios,
            "prevalence_ratio_lo": q(pr)[0], "prevalence_ratio_hi": q(pr)[1],
            "odds_ratio_lo": q(orr)[0], "odds_ratio_hi": q(orr)[1],
            **{k: v for k, v in fit.items() if k != "frame"},
            **cpts,
            "curve_ratio_lo": q(c250)[0], "curve_ratio_hi": q(c250)[1],
            "n_boot_ratio": len(pr), "n_boot_curve": len(draws), "block_m": BLOCK_M,
        })
        band = np.abs(grid) <= d if d > 0 else np.zeros(len(grid), dtype=bool)
        curves.append(pd.DataFrame({
            "exclusion_m": d, "signed_distance_m": grid, "prob": curve,
            "prob_lo": np.percentile(draws, 2.5, axis=0), "prob_hi": np.percentile(draws, 97.5, axis=0),
            "in_excluded_band": band,
        }))

    res = pd.DataFrame(rows)
    res.to_csv(out_dir / "Nairobi_boundary_exclusion_summary.csv", index=False)
    pd.concat(curves, ignore_index=True).to_csv(out_dir / "Nairobi_boundary_exclusion_curves.csv", index=False)

    thesis = pd.DataFrame({
        "Panoramas excluded": ["None" if d == 0 else f"Within {d:.0f} m of a boundary" for d in res.exclusion_m],
        "Panoramas retained": res.n_panoramas.map("{:,}".format),
        "Inside: panoramas / waste-positive": [f"{a:,} / {b:,}" for a, b in zip(res.n_inside, res.n_positive_inside)],
        "Outside: panoramas / waste-positive": [f"{a:,} / {b:,}" for a, b in zip(res.n_outside, res.n_positive_outside)],
        "Rate inside (%)": res.rate_inside_pct.map("{:.1f}".format),
        "Rate outside (%)": res.rate_outside_pct.map("{:.2f}".format),
        "Prevalence ratio (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(res.prevalence_ratio, res.prevalence_ratio_lo, res.prevalence_ratio_hi)],
        "Odds ratio (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in zip(res.odds_ratio, res.odds_ratio_lo, res.odds_ratio_hi)],
        "ΔAIC MP − MDP": res.delta_aic_MP_minus_MDP.map("{:,.0f}".format),
        "LRT p (MP vs MDP)": res.lrt_MP_vs_MDP_p.map("{:.1e}".format),
        "Adjusted P(waste) 250 m → 2 km (%)": [
            f"{a:.2f} → {b:.2f}" for a, b in zip(res.curve_p_at_250m_pct, res.curve_p_at_2000m_pct)],
        "250 m ÷ 2 km (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(res.curve_ratio_250m_vs_2000m, res.curve_ratio_lo, res.curve_ratio_hi)],
    })
    path = table_dir / "boundary_exclusion_sensitivity.csv"
    thesis.to_csv(path, index=False)
    print(f"Thesis table: {path}\nWrote outputs to {out_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Spatial block bootstrap for the settlement ratio and the MDP curve.

The population-adjusted GAM (MDP) leaves small but significant residual spatial
autocorrelation (Moran's I ≈ 0.06, k = 8). Nearby panoramas are therefore not
independent, and intervals that assume they are (the analytic Wald/Katz
intervals for the settlement ratios, a panorama-level bootstrap of the MDP
curve) can be too narrow. This script keeps the GAM exactly as specified
and only changes how its uncertainty is estimated.

  Spatial block bootstrap
    Overlay a square grid of side B on the panoramas, with a fresh uniform
    random offset in each replicate so no single grid placement drives the
    result. Draw as many blocks as are occupied, with replacement, and take
    every panorama in each drawn block. Refit and recompute on that sample.
    Dependence within a block is kept intact; only blocks are treated as
    independent. B = 250, 500, 1,000, 2,000 and 4,000 m.

  Reference: the same procedure with single panoramas as the unit (``iid``),
  which assumes panoramas are independent.

Per replicate:
  - inside/outside settlement prevalence ratio and odds ratio
  - the MDP signed-distance curve, standardised over population and year
    (same model and standardisation as 1_pop_adjusted_gam.py)
  - a scalar contrast: adjusted P(waste) at the settlement edge vs 2 km

Intervals are bootstrap percentiles (2.5–97.5%). A residual correlogram of the
full-sample MDP Pearson residuals is written alongside, to show over what
distance the residual dependence decays and so which block sizes are relevant.

The 2 km replicates are the same draws as the bands of the main figure
(1_pop_adjusted_gam.py uses the same sampler and seed).

Runs on the manuscript sample (worldpop_2020/, 76,578 panoramas) by default;
--data-subdir picks another run.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import norm

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in SCRIPT_DIR.parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.gam import BOOT_SEED, assign_year_fe  # noqa: E402
from lib.script_loader import load_script  # noqa: E402


pag = load_script(SCRIPT_DIR / "1_pop_adjusted_gam.py")
thin = load_script(SCRIPT_DIR / "2_thinning_sensitivity.py")

BLOCK_SIZES_M = (250.0, 500.0, 1000.0, 2000.0, 4000.0)
N_BOOT = 500
CURVE_REF_M = (0.0, 2000.0)
CORR_SAMPLE_N = 8000
CORR_BINS_M = np.array([0, 25, 50, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 4000, 5000])
Z = norm.ppf(0.975)


# --------------------------------------------------------------------------- pieces


def ratio_measures(df: pd.DataFrame) -> dict:
    m = thin.settlement_measures(df)
    return {
        "rate_inside_pct": m["rate_inside_pct"],
        "rate_outside_pct": m["rate_outside_pct"],
        "prevalence_ratio": m["prevalence_ratio"],
        "odds_ratio": m["odds_ratio"],
    }


def analytic_intervals(df: pd.DataFrame) -> dict:
    """The independence-based intervals: Katz log interval (PR), Woolf (OR)."""
    y = df["waste_positive"].astype(int).to_numpy()
    ins = df["inside_settlement"].astype(int).to_numpy() == 1
    a, b = int(y[ins].sum()), int((1 - y[ins]).sum())
    c, d = int(y[~ins].sum()), int((1 - y[~ins]).sum())
    pr = (a / (a + b)) / (c / (c + d))
    se_pr = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    orr = (a * d) / (b * c)
    se_or = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {
        "prevalence_ratio": (pr * np.exp(-Z * se_pr), pr * np.exp(Z * se_pr)),
        "odds_ratio": (orr * np.exp(-Z * se_or), orr * np.exp(Z * se_or)),
    }


def curve_stats(df: pd.DataFrame, grid: np.ndarray, seed: int = 0) -> tuple[np.ndarray, dict]:
    """Fit MDP on df (year FE reassigned) and return the standardised curve."""
    d, res, cols = pag.refit_mdp(df)
    curve = pag.mdp_distance_curve(d, res, cols, grid)
    p0, p2 = np.interp(CURVE_REF_M, grid, curve)
    return curve, {
        "curve_p_at_0m_pct": 100.0 * p0,
        "curve_p_at_2000m_pct": 100.0 * p2,
        "curve_ratio_0m_vs_2000m": p0 / p2 if p2 > 0 else np.nan,
    }


def residual_correlogram(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Correlation of MDP Pearson residuals between panorama pairs, by distance band."""
    d = assign_year_fe(df.drop(columns=["year_fe"], errors="ignore"), verbose=False)
    res, _ = pag.fit_mdp(d)
    r = np.asarray(res.resid_pearson, dtype=float)
    r = (r - r.mean()) / r.std()
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(d), size=min(CORR_SAMPLE_N, len(d)), replace=False)
    xy, rs = d[["x", "y"]].to_numpy(dtype=float)[idx], r[idx]
    tree = cKDTree(xy)
    pairs = tree.query_pairs(CORR_BINS_M[-1], output_type="ndarray")
    dist = np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1)
    prod = rs[pairs[:, 0]] * rs[pairs[:, 1]]
    band = np.digitize(dist, CORR_BINS_M) - 1
    rows = []
    for k in range(len(CORR_BINS_M) - 1):
        m = band == k
        rows.append(
            {
                "dist_lo_m": CORR_BINS_M[k],
                "dist_hi_m": CORR_BINS_M[k + 1],
                "n_pairs": int(m.sum()),
                "residual_correlation": float(prod[m].mean()) if m.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


# One implementation, shared with the bands of the main figure (1_pop_adjusted_gam.py).
block_sample = pag.block_sample


# --------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-subdir", default=pag.MANUSCRIPT_SUBDIR,
                    help="run folder under pop_adjusted/ (default: worldpop_2020, the manuscript sample)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    base = pag.POP_ADJ_ROOT / args.data_subdir
    out_dir, table_dir = base / "block_bootstrap", base / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(base / "Nairobi_pop_adjusted_gam_frame.csv", dtype={"year_fe": str, "panoid": str})
    print(f"Frame {base.name}: n={len(df):,}, waste+={int(df['waste_positive'].sum()):,}")

    grid = pag.distance_grid(df)
    xy = df[["x", "y"]].to_numpy(dtype=float)

    print("Residual correlogram...")
    residual_correlogram(df, BOOT_SEED).to_csv(out_dir / "Nairobi_mdp_residual_correlogram.csv", index=False)

    print("Full-sample estimates...")
    full_curve, full_c = curve_stats(df, grid, BOOT_SEED)
    full = {**ratio_measures(df), **full_c}
    analytic = analytic_intervals(df)

    schemes = [("iid", 0.0)] + [("block", b) for b in BLOCK_SIZES_M]
    reps, curves = [], []
    for scheme, bsize in schemes:
        label = "panorama (iid)" if scheme == "iid" else f"{bsize:.0f} m blocks"
        t0 = time.time()
        rng = np.random.default_rng(pag.block_bootstrap_seed(bsize))
        n_blocks = None
        if scheme == "block":
            n_blocks = len(np.unique(np.floor(xy / bsize).astype(np.int64), axis=0))
        for r in range(args.n_boot):
            idx = rng.integers(0, len(df), size=len(df)) if scheme == "iid" else block_sample(xy, bsize, rng)
            boot = df.iloc[idx].reset_index(drop=True)
            if boot["waste_positive"].nunique() < 2:
                continue
            try:
                curve, cstats = curve_stats(boot, grid, BOOT_SEED + r)
            except Exception as exc:  # keep going; failures are counted below
                print(f"  {label} rep {r}: fit failed ({exc})")
                continue
            reps.append({"scheme": scheme, "block_m": bsize, "rep": r, "n": len(boot),
                         **ratio_measures(boot), **cstats})
            curves.append(curve)
        print(f"  {label}: {sum(1 for x in reps if x['block_m'] == bsize and x['scheme'] == scheme)} reps"
              f"{'' if n_blocks is None else f', ~{n_blocks:,} occupied blocks'} ({time.time() - t0:.0f}s)")

    rep_df = pd.DataFrame(reps)
    rep_df.to_csv(out_dir / "Nairobi_block_bootstrap_replicates.csv", index=False)

    # Curve envelopes
    curve_mat = np.vstack(curves)
    env_rows = [pd.DataFrame({"scheme": "full_sample", "block_m": np.nan, "signed_distance_m": grid,
                              "prob": full_curve, "prob_lo": np.nan, "prob_hi": np.nan})]
    for (scheme, bsize), g in rep_df.groupby(["scheme", "block_m"], sort=False):
        m = curve_mat[g.index.to_numpy()]
        env_rows.append(pd.DataFrame({
            "scheme": scheme, "block_m": bsize, "signed_distance_m": grid, "prob": full_curve,
            "prob_lo": np.percentile(m, 2.5, axis=0), "prob_hi": np.percentile(m, 97.5, axis=0),
        }))
    env = pd.concat(env_rows, ignore_index=True)
    env.to_csv(out_dir / "Nairobi_block_bootstrap_curves.csv", index=False)

    # Summary per scheme
    metrics = ["prevalence_ratio", "odds_ratio", "rate_inside_pct", "rate_outside_pct",
               "curve_p_at_0m_pct", "curve_p_at_2000m_pct", "curve_ratio_0m_vs_2000m"]
    rows = [{"scheme": "analytic", "block_m": np.nan, "n_reps": np.nan, "metric": k,
             "estimate": full[k], "lo": lo, "hi": hi} for k, (lo, hi) in analytic.items()]
    for (scheme, bsize), g in rep_df.groupby(["scheme", "block_m"], sort=False):
        for k in metrics:
            rows.append({"scheme": scheme, "block_m": bsize, "n_reps": len(g), "metric": k,
                         "estimate": full[k], "lo": g[k].quantile(0.025), "hi": g[k].quantile(0.975)})
    summ = pd.DataFrame(rows)
    # width relative to the panorama-level bootstrap of the same statistic
    iid_w = summ[summ.scheme == "iid"].set_index("metric").eval("hi - lo")
    summ["width"] = summ["hi"] - summ["lo"]
    summ["width_vs_iid"] = summ["width"] / summ["metric"].map(iid_w)
    # does the interval still exclude "no association"?
    null = {"prevalence_ratio": 1.0, "odds_ratio": 1.0, "curve_ratio_0m_vs_2000m": 1.0}
    summ["excludes_null"] = [
        (r.lo > null[r.metric]) if r.metric in null else np.nan for r in summ.itertuples()
    ]
    summ.to_csv(out_dir / "Nairobi_block_bootstrap_summary.csv", index=False)

    write_thesis_table(summ, table_dir / "block_bootstrap_intervals.csv")
    print(f"Wrote outputs to {out_dir}")


def write_thesis_table(summ: pd.DataFrame, path: Path) -> None:
    label = {
        "prevalence_ratio": ("Prevalence ratio (inside/outside)", ".2f"),
        "odds_ratio": ("Odds ratio (inside vs outside)", ".2f"),
        "curve_p_at_0m_pct": ("Adjusted P(waste) at settlement edge (%)", ".2f"),
        "curve_p_at_2000m_pct": ("Adjusted P(waste) at 2 km (%)", ".2f"),
        "curve_ratio_0m_vs_2000m": ("Adjusted ratio, edge vs 2 km", ".2f"),
    }
    def method(r):
        if r.scheme == "analytic":
            return "Analytic (independence)"
        if r.scheme == "iid":
            return "Panorama bootstrap"
        return f"Spatial block bootstrap, {r.block_m:,.0f} m"
    out = []
    for r in summ[summ.metric.isin(label)].itertuples():
        name, spec = label[r.metric]
        out.append({
            "Quantity": name,
            "Interval method": method(r),
            "Estimate": format(r.estimate, spec),
            "95% interval": f"{format(r.lo, spec)}–{format(r.hi, spec)}",
            "Width vs panorama bootstrap": "" if pd.isna(r.width_vs_iid) else f"{r.width_vs_iid:.2f}×",
            "Excludes no association": "" if pd.isna(r.excludes_null) else ("yes" if r.excludes_null else "no"),
        })
    pd.DataFrame(out).to_csv(path, index=False)
    print(f"Thesis table: {path}")


if __name__ == "__main__":
    main()

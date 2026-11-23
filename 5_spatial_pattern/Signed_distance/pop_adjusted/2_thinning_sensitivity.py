#!/usr/bin/env python3
"""Spatial-thinning sensitivity for the population-adjusted GAM (R1.5 / R3.1).

The earlier check (``dedup_sensitivity``, since removed from 1_pop_adjusted_gam.py) thinned
**waste-positive panoramas only**: positives were grouped with DBSCAN
(eps = 50 / 100 m, min_samples = 1, i.e. chained single-linkage components),
one positive was kept per group, and **every negative was retained**. Because
which panoramas are dropped depends on the outcome, that lowers prevalence
(3.6% → 2.8% / 1.9%) and changes the positive-to-negative ratio near
settlements, where positives cluster most. It is not a neutral test.

This script redoes the check **label-blind**: thinning is applied to the
complete panorama frame, and the outcome is never consulted.

  Label-blind minimum-distance thinning
    Visit all panoramas in a random order; keep a panorama unless a panorama
    already kept lies within d metres; then block every panorama within d of
    it. No two retained panoramas are closer than d, whatever their label.
    Repeated over N_REPS random orders per threshold, because a single draw
    is one arbitrary realisation.

For each thinned frame the same nested GAMs are refitted (MP, MD, MDP, with
year FE reassigned on the retained data), and the following are recomputed on
the retained panoramas only:

  - counts of positives and negatives retained (the denominators)
  - settlement prevalence ratio and odds ratio (inside vs outside)
  - observed positive rate by signed-distance band
  - the pop- and year-standardised MDP signed-distance curve

The original positive-only scheme is reproduced alongside, so the table shows
baseline / original / revised side by side.

Which sample: the GAM frame of one population-raster variant, read from its
Nairobi_pop_adjusted_gam_frame.csv. ``--data-subdir worldpop_2020`` uses the
unconstrained WorldPop 2020 frame (76,578 panoramas), which is the sample in
the submitted manuscript. With no subdir it uses the constrained 2024 frame
(74,882), whose raster has no value outside built-up areas, so 1,720 remote,
all-negative panoramas drop out. Every rate is retained positives / retained
panoramas in that scheme.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in SCRIPT_DIR.parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.gam import BOOT_SEED, PRED_GRID_N, assign_year_fe  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "pop_adjusted_gam", SCRIPT_DIR / "1_pop_adjusted_gam.py"
)
pag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pag)

THRESHOLDS_M = (25.0, 50.0, 75.0, 100.0)
N_REPS = 100
CURVE_REF_M = (0.0, 2000.0)  # settlement edge vs 2 km outside, for a scalar summary
DISTANCE_BANDS = [
    (-np.inf, 0.0, "Inside a settlement"),
    (0.0, 250.0, "0–250 m"),
    (250.0, 500.0, "250–500 m"),
    (500.0, 1000.0, "500–1,000 m"),
    (1000.0, 2000.0, "1,000–2,000 m"),
    (2000.0, 5000.0, "2,000–5,000 m"),
    (5000.0, np.inf, ">5,000 m"),
]

OUT_DIR = pag.OUTPUT_DIR / "thinning"
TABLE_DIR = pag.TABLE_DIR
FRAME_CSV = pag.OUTPUT_DIR / "Nairobi_pop_adjusted_gam_frame.csv"


def configure(data_subdir: str) -> None:
    """Point inputs and outputs at one population-raster variant's folder."""
    global OUT_DIR, TABLE_DIR, FRAME_CSV
    base = pag.POP_ADJ_ROOT / data_subdir
    OUT_DIR = base / "thinning"
    TABLE_DIR = base / "thesis_table"
    FRAME_CSV = base / "Nairobi_pop_adjusted_gam_frame.csv"


# --------------------------------------------------------------------------- thinning


def thin_label_blind(xy: np.ndarray, tree: cKDTree, dist_m: float, seed: int) -> np.ndarray:
    """Indices kept by random-order minimum-distance thinning of *all* points."""
    rng = np.random.default_rng(seed)
    blocked = np.zeros(len(xy), dtype=bool)
    keep: list[int] = []
    for i in rng.permutation(len(xy)):
        if blocked[i]:
            continue
        keep.append(int(i))
        blocked[tree.query_ball_point(xy[i], dist_m)] = True
    return np.sort(np.asarray(keep, dtype=int))


def thin_positive_only(df: pd.DataFrame, dist_m: float, seed: int) -> pd.DataFrame:
    """The superseded scheme: one waste+ panorama per DBSCAN group, every negative kept.

    The selection depends on the outcome, so it is biased. It is reproduced
    here only so the table can set it beside the label-blind scheme.
    """
    pos = df.loc[df["waste_positive"] == 1]
    neg = df.loc[df["waste_positive"] == 0]
    if len(pos) == 0:
        return df.copy()
    coords = pos[["x", "y"]].to_numpy(dtype=float)
    labels = DBSCAN(eps=float(dist_m), min_samples=1, metric="euclidean").fit(coords).labels_
    rng = np.random.default_rng(seed)
    keep_idx = [int(rng.choice(np.where(labels == lab)[0])) for lab in np.unique(labels)]
    return pd.concat([pos.iloc[keep_idx], neg], ignore_index=True)


# --------------------------------------------------------------------------- measures


def settlement_measures(df: pd.DataFrame) -> dict:
    y = df["waste_positive"].astype(int)
    ins = df["inside_settlement"].astype(int) == 1
    a, b = int(y[ins].sum()), int((1 - y[ins]).sum())
    c, d = int(y[~ins].sum()), int((1 - y[~ins]).sum())
    rate_in = a / (a + b) if a + b else np.nan
    rate_out = c / (c + d) if c + d else np.nan
    return {
        "n_panoramas": int(len(df)),
        "n_positive": int(y.sum()),
        "n_negative": int((1 - y).sum()),
        "prevalence_pct": 100.0 * y.mean(),
        "n_inside": a + b,
        "n_positive_inside": a,
        "rate_inside_pct": 100.0 * rate_in,
        "rate_outside_pct": 100.0 * rate_out,
        "prevalence_ratio": rate_in / rate_out if rate_out else np.nan,
        "odds_ratio": (a * d) / (b * c) if b * c else np.nan,
    }


def band_rates(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sd = df["signed_distance_m"].to_numpy(dtype=float)
    y = df["waste_positive"].to_numpy(dtype=int)
    for lo, hi, label in DISTANCE_BANDS:
        m = (sd > lo) & (sd <= hi)  # inside a settlement = signed distance ≤ 0
        rows.append(
            {
                "band": label,
                "n_panoramas": int(m.sum()),
                "n_positive": int(y[m].sum()),
                "rate_pct": 100.0 * y[m].mean() if m.any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def standardised_distance_curve(
    df: pd.DataFrame, result, year_cols: list[str], grid: np.ndarray, seed: int = 0
) -> np.ndarray:
    """MDP P(waste+) over `grid`, averaged over the pop distribution and year shares.

    Delegates to pag.mdp_distance_curve, the single definition of the curve.
    `seed` is kept for call compatibility and is unused: the standardisation
    is over evenly spaced quantiles, not a random sample.
    """
    return pag.mdp_distance_curve(df, result, year_cols, grid)


def fit_models(df: pd.DataFrame) -> dict:
    """MP, MD, MDP on one frame; LRTs as in 1_pop_adjusted_gam.py."""
    df = assign_year_fe(df.drop(columns=["year_fe"], errors="ignore"), verbose=False)

    def stable(fitter):
        res, cols, _, _ = fitter(df)
        if not np.isfinite(float(res.llf)):
            res, cols, _, _ = fitter(df, alpha=1.0)
        return res, cols

    m_p, _ = stable(pag.fit_mp)
    m_d, _ = stable(pag.fit_md)
    m_dp, cols_dp = stable(pag.fit_mdp)
    lrt_p = pag.likelihood_ratio_test(m_dp, m_p, "MP_vs_MDP")
    lrt_d = pag.likelihood_ratio_test(m_dp, m_d, "MD_vs_MDP")
    return {
        "frame": df,
        "mdp": m_dp,
        "mdp_cols": cols_dp,
        "n_year_fe": int(df["year_fe"].nunique()),
        "aic_MP": pag._safe_aic(m_p),
        "aic_MD": pag._safe_aic(m_d),
        "aic_MDP": pag._safe_aic(m_dp),
        "delta_aic_MP_minus_MDP": lrt_p["delta_aic_nested_minus_full"],
        "lrt_MP_vs_MDP": lrt_p["lr_stat"],
        "lrt_MP_vs_MDP_df": lrt_p["df_diff"],
        "lrt_MP_vs_MDP_p": lrt_p["p_value"],
        "delta_aic_MD_minus_MDP": lrt_d["delta_aic_nested_minus_full"],
        "lrt_MD_vs_MDP_p": lrt_d["p_value"],
        "pseudo_r2_MDP": pag._model_metrics(m_dp, "MDP", len(df))["pseudo_r2_mcfadden"],
    }


def evaluate(df: pd.DataFrame, grid: np.ndarray, seed: int) -> tuple[dict, np.ndarray, pd.DataFrame]:
    fit = fit_models(df)
    curve = standardised_distance_curve(fit["frame"], fit["mdp"], fit["mdp_cols"], grid, seed)
    ref = np.interp(CURVE_REF_M, grid, curve)
    row = {
        **settlement_measures(df),
        **{k: v for k, v in fit.items() if k not in ("frame", "mdp", "mdp_cols")},
        "curve_p_at_0m_pct": 100.0 * ref[0],
        "curve_p_at_2000m_pct": 100.0 * ref[1],
        "curve_ratio_0m_vs_2000m": ref[0] / ref[1] if ref[1] > 0 else np.nan,
    }
    return row, curve, band_rates(df)


# --------------------------------------------------------------------------- main


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--data-subdir",
        default=pag.MANUSCRIPT_SUBDIR,
        help="run folder under pop_adjusted/ (default: worldpop_2020, the manuscript "
        "sample; worldpop_2024_constrained for the 2024 constrained layer)",
    )
    configure(ap.parse_args().data_subdir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    if not FRAME_CSV.is_file():
        raise SystemExit(f"Missing {FRAME_CSV}; run 1_pop_adjusted_gam.py first.")
    df = pd.read_csv(FRAME_CSV, dtype={"year_fe": str, "panoid": str})
    print(f"GAM frame: n={len(df):,}, waste+={int(df['waste_positive'].sum()):,}")

    # Fixed distance grid so every curve is evaluated at the same points.
    grid = np.linspace(
        float(df["signed_distance_m"].quantile(0.01)),
        float(df["signed_distance_m"].quantile(0.99)),
        PRED_GRID_N,
    )
    xy = df[["x", "y"]].to_numpy(dtype=float)
    tree = cKDTree(xy)

    reps, curves, bands = [], [], []

    def record(scheme: str, thr: float, rep: int, sub: pd.DataFrame, seed: int) -> None:
        row, curve, br = evaluate(sub, grid, seed)
        reps.append({"scheme": scheme, "threshold_m": thr, "rep": rep, **row})
        curves.append(
            pd.DataFrame(
                {
                    "scheme": scheme,
                    "threshold_m": thr,
                    "rep": rep,
                    "signed_distance_m": grid,
                    "prob_waste_positive": curve,
                }
            )
        )
        bands.append(br.assign(scheme=scheme, threshold_m=thr, rep=rep))

    print("Baseline (no thinning)...")
    record("baseline", 0.0, 0, df, BOOT_SEED)

    for thr in THRESHOLDS_M:
        print(f"Original positive-only thinning, {thr:.0f} m...")
        record("positive_only", thr, 0, thin_positive_only(df, thr, BOOT_SEED + int(thr)), BOOT_SEED)

        print(f"Label-blind thinning, {thr:.0f} m, {N_REPS} replicates...")
        for r in range(N_REPS):
            seed = BOOT_SEED + 10_000 * int(thr) + r
            keep = thin_label_blind(xy, tree, thr, seed)
            record("label_blind", thr, r, df.iloc[keep].reset_index(drop=True), seed)

    rep_df = pd.DataFrame(reps)
    curve_df = pd.concat(curves, ignore_index=True)
    band_df = pd.concat(bands, ignore_index=True)

    rep_df.to_csv(OUT_DIR / "Nairobi_thinning_replicates.csv", index=False)
    band_df.to_csv(OUT_DIR / "Nairobi_thinning_band_rates_replicates.csv", index=False)

    # Curves: median and 2.5–97.5% envelope across replicates.
    curve_sum = (
        curve_df.groupby(["scheme", "threshold_m", "signed_distance_m"])["prob_waste_positive"]
        .agg(
            prob_median="median",
            prob_lo=lambda s: s.quantile(0.025),
            prob_hi=lambda s: s.quantile(0.975),
            n_reps="size",
        )
        .reset_index()
    )
    curve_sum.to_csv(OUT_DIR / "Nairobi_thinning_curves.csv", index=False)

    band_sum = (
        band_df.groupby(["scheme", "threshold_m", "band"], sort=False)
        .agg(
            n_panoramas=("n_panoramas", "median"),
            n_positive=("n_positive", "median"),
            rate_pct=("rate_pct", "median"),
            rate_lo=("rate_pct", lambda s: s.quantile(0.025)),
            rate_hi=("rate_pct", lambda s: s.quantile(0.975)),
        )
        .reset_index()
    )
    band_sum.to_csv(OUT_DIR / "Nairobi_thinning_band_rates.csv", index=False)

    # Summary: median and 2.5–97.5% range per scheme × threshold.
    metrics = [c for c in rep_df.columns if c not in ("scheme", "threshold_m", "rep")]
    grp = rep_df.groupby(["scheme", "threshold_m"], sort=False)
    summary = grp[metrics].median().add_suffix("_median")
    summary = summary.join(grp[metrics].quantile(0.025).add_suffix("_lo"))
    summary = summary.join(grp[metrics].quantile(0.975).add_suffix("_hi"))
    summary["n_reps"] = grp.size()
    summary["share_reps_lrt_p_lt_0.001"] = grp["lrt_MP_vs_MDP_p"].apply(lambda s: (s < 0.001).mean())
    # How often a draw's prevalence ratio falls below the unthinned value: checks
    # whether a dip at one threshold is systematic or one side of the spread.
    base_pr = float(rep_df.loc[rep_df["scheme"] == "baseline", "prevalence_ratio"].iloc[0])
    summary["share_reps_pr_below_unthinned"] = grp["prevalence_ratio"].apply(
        lambda s: (s < base_pr).mean()
    )
    summary["share_retained_inside_pct_median"] = (
        100.0 * grp["n_inside"].median() / grp["n_panoramas"].median()
    )
    summary = summary.reset_index()
    summary.to_csv(OUT_DIR / "Nairobi_thinning_summary.csv", index=False)

    write_thesis_table(summary)
    print(f"\nWrote outputs to {OUT_DIR}")


def _fmt(row: pd.Series, col: str, spec: str, rng: bool) -> str:
    med = row[f"{col}_median"]
    s = format(med, spec)
    if rng and row["n_reps"] > 1:
        s += f" ({format(row[f'{col}_lo'], spec)}–{format(row[f'{col}_hi'], spec)})"
    return s


def write_thesis_table(summary: pd.DataFrame) -> None:
    label = {
        "baseline": "No thinning",
        "positive_only": "Original: positives thinned, all negatives kept",
        "label_blind": "Revised: all panoramas thinned, label-blind",
    }
    rows = []
    for _, r in summary.iterrows():
        multi = r["n_reps"] > 1
        rows.append(
            {
                "Scheme": label[r["scheme"]],
                "Threshold": "—" if r["threshold_m"] == 0 else f"{r['threshold_m']:.0f} m",
                "Replicates": int(r["n_reps"]),
                "Panoramas retained": _fmt(r, "n_panoramas", ",.0f", multi),
                "Positives retained": _fmt(r, "n_positive", ",.0f", multi),
                "Negatives retained": _fmt(r, "n_negative", ",.0f", multi),
                "Prevalence (%)": _fmt(r, "prevalence_pct", ".2f", multi),
                "Rate inside settlements (%)": _fmt(r, "rate_inside_pct", ".1f", multi),
                "Rate outside settlements (%)": _fmt(r, "rate_outside_pct", ".2f", multi),
                "Prevalence ratio (inside/outside)": _fmt(r, "prevalence_ratio", ".2f", multi),
                "Adjusted P(waste) at settlement edge (%)": _fmt(r, "curve_p_at_0m_pct", ".1f", multi),
                "Adjusted P(waste) at 2 km (%)": _fmt(r, "curve_p_at_2000m_pct", ".2f", multi),
                "ΔAIC (MP − MDP)": _fmt(r, "delta_aic_MP_minus_MDP", ",.0f", multi),
                "LRT χ² (MP vs MDP)": _fmt(r, "lrt_MP_vs_MDP", ",.0f", multi),
                "Share of replicates with LRT p < 0.001": f"{r['share_reps_lrt_p_lt_0.001']:.0%}",
                "McFadden pseudo-R² (MDP)": _fmt(r, "pseudo_r2_MDP", ".3f", multi),
            }
        )
    out = pd.DataFrame(rows)
    path = TABLE_DIR / "thinning_sensitivity.csv"
    out.to_csv(path, index=False)
    print(f"Thesis table: {path}")


if __name__ == "__main__":
    main()

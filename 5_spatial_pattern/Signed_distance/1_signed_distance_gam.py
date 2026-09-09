#!/usr/bin/env python3
"""Primary year-adjusted signed-distance logistic GAM (panorama unit).

Full GSVI sample (analysis unit = panoid):

  logit{P(Waste_i = 1)} = α + s(signed_distance_i) + γ_{year_i}

Controls for capture year while estimating the settlement-distance gradient.
Period-stratified curves / HDBSCAN are supporting robustness only.

Sparse years (n < MIN_YEAR_N) are pooled as "other". Year FE levels with zero
waste-positives cannot stand alone in a logit (complete separation); those
panoramas are reassigned to the nearest calendar year that has positives so the
full panorama set is retained.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.gam.api import BSplines, GLMGam

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

# Always write under the external data root (not the code tree).
OUTPUT_DIR = PATTERN_DIR / "Signed_distance"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

MIN_YEAR_N = 200
SPLINE_DF = 8
SPLINE_DEGREE = 3
PRED_GRID_N = 200
CI_ALPHA = 0.05
BOOT_B = 80
BOOT_SEED = 42


def prepare_analysis_frame() -> pd.DataFrame:
    points = enrich_sviwaste_frame()
    slums = load_slums()
    points = label_inside_settlement(points, slums)
    points["signed_distance_m"] = signed_distance_to_slums(points, slums)

    df = points[
        [
            "panoid",
            "waste_positive",
            "inside_settlement",
            "year",
            "n_positive_views",
            "signed_distance_m",
        ]
    ].copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year", "signed_distance_m", "waste_positive"]).copy()
    df["year"] = df["year"].astype(int)
    df["waste_positive"] = df["waste_positive"].astype(int)

    year_counts = df["year"].value_counts()
    rare = set(year_counts[year_counts < MIN_YEAR_N].index.tolist())
    df["year_fe"] = df["year"].astype(str)
    if rare:
        df.loc[df["year"].isin(rare), "year_fe"] = "other"
        print(f"  Pooling rare years (n<{MIN_YEAR_N}) as 'other': {sorted(rare)}")

    # Avoid complete separation: reassign zero-positive FE levels to nearest
    # calendar year that has at least one waste-positive (keeps all panoids).
    pos_by_fe = df.groupby("year_fe")["waste_positive"].sum()
    zero_pos = [lv for lv, n in pos_by_fe.items() if int(n) == 0]
    if zero_pos:
        # Representative year for each FE level (median of member years)
        rep_year = (
            df.groupby("year_fe")["year"].median().astype(float).to_dict()
        )
        positive_levels = [lv for lv, n in pos_by_fe.items() if int(n) > 0]
        pos_reps = {lv: rep_year[lv] for lv in positive_levels}
        for lv in zero_pos:
            y0 = rep_year[lv]
            nearest = min(pos_reps.items(), key=lambda kv: abs(kv[1] - y0))[0]
            n_move = int((df["year_fe"] == lv).sum())
            print(
                f"  Reassigning year_fe='{lv}' ({n_move:,} panoids, 0 waste+) "
                f"→ '{nearest}' (nearest year FE with positives)"
            )
            df.loc[df["year_fe"] == lv, "year_fe"] = nearest

    return df.reset_index(drop=True)


def _year_exog(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    year_dummies = pd.get_dummies(df["year_fe"], drop_first=True, prefix="year")
    year_cols = year_dummies.columns.tolist()
    exog = sm.add_constant(year_dummies.astype(float), has_constant="add")
    return exog, year_cols


def fit_year_only(df: pd.DataFrame):
    """Nested model for LRT: logit(p) = α + γ_year (no distance)."""
    y = df["waste_positive"].to_numpy(dtype=float)
    exog, year_cols = _year_exog(df)
    model = sm.GLM(y, exog, family=sm.families.Binomial())
    return model.fit(), year_cols


def fit_year_and_distance(df: pd.DataFrame):
    """Primary model: logit(p) = α + s(signed_distance) + γ_year."""
    y = df["waste_positive"].to_numpy(dtype=float)
    x_smooth = df[["signed_distance_m"]].astype(float)
    smoother = BSplines(x_smooth, df=[SPLINE_DF], degree=[SPLINE_DEGREE])
    exog, year_cols = _year_exog(df)

    model = GLMGam(
        y,
        exog=exog,
        smoother=smoother,
        family=sm.families.Binomial(),
    )
    return model.fit(), year_cols


def _exog_at_year(grid_n: int, year_cols: list[str], fixed_year: str) -> np.ndarray:
    exog = pd.DataFrame({"const": np.ones(grid_n, dtype=float)})
    for col in year_cols:
        level = col.replace("year_", "", 1)
        exog[col] = 1.0 if level == fixed_year else 0.0
    return exog.to_numpy(dtype=float)


def year_standardisation_weights(df: pd.DataFrame) -> pd.Series:
    """Observed share of each year FE level (sums to 1)."""
    w = df["year_fe"].astype(str).value_counts(normalize=True).sort_index()
    return w


def _predict_year_standardised(
    result,
    year_cols: list[str],
    weights: pd.Series,
    grid: np.ndarray,
    available_levels: set[str] | None = None,
) -> np.ndarray:
    """Average predicted P(Y=1|d, year) over year FE shares.

    p_std(d) = Σ_y w_y · p(d | year = y), restricted to year FE levels present
    in the fitted model, with weights renormalised to sum to 1 on that set.
    """
    xs = grid.reshape(-1, 1)
    n = len(grid)

    w = weights.astype(float).copy()
    w.index = w.index.astype(str)
    if available_levels is not None:
        keep = [lv for lv in w.index if lv in available_levels]
        w = w.reindex(keep).dropna()
    w = w[w > 0]
    if w.empty:
        raise ValueError("No valid year weights for standardisation")
    w = w / w.sum()

    pred = np.zeros(n, dtype=float)
    for level, weight in w.items():
        exog = _exog_at_year(n, year_cols, str(level))
        pred += float(weight) * np.asarray(
            result.predict(exog=exog, exog_smooth=xs), dtype=float
        )
    return pred


def prediction_curve(
    df: pd.DataFrame,
    result,
    year_cols: list[str],
) -> pd.DataFrame:
    """Year-standardised distance-response curve + bootstrap 95% CI.

    At each signed distance, average predicted waste probability over the
    observed year FE distribution (marginal / year-standardised prediction).
    Bootstrap resamples re-fit the model and re-standardise using the same
    full-sample year weights restricted to FE levels present in the draw.
    """
    weights = year_standardisation_weights(df)
    full_levels = set(df["year_fe"].astype(str).unique())
    d_min = float(df["signed_distance_m"].quantile(0.01))
    d_max = float(df["signed_distance_m"].quantile(0.99))
    grid = np.linspace(d_min, d_max, PRED_GRID_N)

    mean = _predict_year_standardised(
        result, year_cols, weights, grid, available_levels=full_levels
    )

    n = len(df)
    rng = np.random.default_rng(BOOT_SEED)
    draws: list[np.ndarray] = []
    print(
        "  Bootstrap CI for year-standardised prediction curve "
        f"(B={BOOT_B}; year FE weights: "
        + ", ".join(f"{lv}={w:.1%}" for lv, w in weights.items())
        + ")..."
    )
    for _ in range(BOOT_B):
        idx = rng.integers(0, n, size=n)
        boot = df.iloc[idx]
        if boot["waste_positive"].nunique() < 2 or boot["year_fe"].nunique() < 2:
            continue
        try:
            boot_fit, boot_cols = fit_year_and_distance(boot)
            boot_levels = set(boot["year_fe"].astype(str).unique())
            draws.append(
                _predict_year_standardised(
                    boot_fit,
                    boot_cols,
                    weights,
                    grid,
                    available_levels=boot_levels,
                )
            )
        except Exception:
            continue

    lo = np.full(PRED_GRID_N, np.nan)
    hi = np.full(PRED_GRID_N, np.nan)
    ci_method = "none"
    if draws:
        arr = np.vstack(draws)
        q_lo = 100.0 * (CI_ALPHA / 2.0)
        q_hi = 100.0 * (1.0 - CI_ALPHA / 2.0)
        lo = np.nanpercentile(arr, q_lo, axis=0)
        hi = np.nanpercentile(arr, q_hi, axis=0)
        ci_method = f"bootstrap_B{len(draws)}_year_standardised"
        print(f"  Bootstrap CI from {len(draws)}/{BOOT_B} draws")
    else:
        print("  Bootstrap CI failed; bands left as NA")

    return pd.DataFrame(
        {
            "signed_distance_m": grid,
            "prob_waste_positive": mean,
            "prob_ci_low": lo,
            "prob_ci_high": hi,
            "prediction_type": "year_standardised",
            "year_weights": "|".join(
                f"{lv}:{w:.6f}" for lv, w in weights.items()
            ),
            "ci_method": ci_method,
            "ci_alpha": CI_ALPHA,
            "prediction_note": (
                "Year-standardised (marginal) predicted probabilities: at each "
                "signed distance, average p(waste+|distance, year) over the "
                "observed capture-year distribution. Model uses year FE; "
                "estimation uses panoramas from all available years."
            ),
        }
    )


def _param_ci(result, name: str) -> tuple[float, float, float] | None:
    params = result.params
    conf = result.conf_int()
    if name in params.index:
        return float(params[name]), float(conf.loc[name, 0]), float(conf.loc[name, 1])
    return None


def year_effects_table(df: pd.DataFrame, result, year_cols: list[str]) -> pd.DataFrame:
    all_levels = sorted(df["year_fe"].unique().tolist())
    dummy_levels = [c.replace("year_", "", 1) for c in year_cols]
    ref_candidates = [lv for lv in all_levels if lv not in dummy_levels]
    ref_level = ref_candidates[0] if ref_candidates else all_levels[0]

    rows = [
        {
            "year_fe": ref_level,
            "coef": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "or": 1.0,
            "is_reference": 1,
            "n_panoids": int((df["year_fe"] == ref_level).sum()),
            "n_waste_positive": int(
                ((df["year_fe"] == ref_level) & (df["waste_positive"] == 1)).sum()
            ),
        }
    ]

    for col, level in zip(year_cols, dummy_levels):
        got = _param_ci(result, col)
        if got is None:
            names = list(result.params.index.astype(str))
            match = next((n for n in names if n == col or n.endswith(level)), None)
            if match is None:
                continue
            got = _param_ci(result, match)
        if got is None:
            continue
        coef, lo, hi = got
        rows.append(
            {
                "year_fe": level,
                "coef": coef,
                "ci_low": lo,
                "ci_high": hi,
                "or": float(np.exp(coef)),
                "is_reference": 0,
                "n_panoids": int((df["year_fe"] == level).sum()),
                "n_waste_positive": int(
                    ((df["year_fe"] == level) & (df["waste_positive"] == 1)).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def smooth_coef_table(result) -> pd.DataFrame:
    """Signed-distance spline basis coefficients (for residual association check)."""
    rows = []
    for name in result.params.index.astype(str):
        if "signed_distance" not in name.lower() and not name.endswith(
            tuple(f"_s{i}" for i in range(20))
        ):
            # keep only smoother terms (statsmodels labels like signed_distance_m_s0)
            if "_s" not in name or name.startswith("year_") or name == "const":
                continue
        if name in ("const",) or name.startswith("year_"):
            continue
        got = _param_ci(result, name)
        if got is None:
            continue
        coef, lo, hi = got
        # z from conf if available
        se = (hi - lo) / (2 * 1.96) if hi > lo else np.nan
        z = coef / se if se and se > 0 and np.isfinite(se) else np.nan
        p = float(2 * (1 - stats.norm.cdf(abs(z)))) if np.isfinite(z) else np.nan
        rows.append(
            {
                "term": name,
                "coef": coef,
                "ci_low": lo,
                "ci_high": hi,
                "z": z,
                "p": p,
            }
        )
    return pd.DataFrame(rows)


def likelihood_ratio_test(result_full, result_nested) -> dict:
    """Compare full (year + s(distance)) vs nested (year-only)."""
    ll_full = float(result_full.llf)
    ll_nested = float(result_nested.llf)
    # df difference ≈ effective extra parameters from smooth
    df_full = float(getattr(result_full, "df_model", np.nan))
    df_nested = float(getattr(result_nested, "df_model", np.nan))
    if np.isfinite(df_full) and np.isfinite(df_nested):
        df_diff = max(df_full - df_nested, 1.0)
    else:
        # B-spline basis adds SPLINE_DF - 1 free smooth coeffs (identifiability)
        df_diff = float(max(SPLINE_DF - 1, 1))

    lr_stat = 2.0 * (ll_full - ll_nested)
    if lr_stat < 0:
        # numerical wobble
        lr_stat = 0.0
    p_value = float(stats.chi2.sf(lr_stat, df_diff))
    return {
        "ll_full": ll_full,
        "ll_year_only": ll_nested,
        "lr_stat": lr_stat,
        "df_diff": df_diff,
        "p_value": p_value,
        "aic_full": float(result_full.aic),
        "aic_year_only": float(result_nested.aic),
        "delta_aic_year_only_minus_full": float(result_nested.aic - result_full.aic),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print(
        "Primary year-adjusted signed-distance logistic GAM "
        "(panorama unit; control for capture year)..."
    )

    df = prepare_analysis_frame()
    print(
        f"  n={len(df):,} panoramas | waste+={int(df['waste_positive'].sum()):,} | "
        f"year_fe={sorted(df['year_fe'].unique().tolist())}"
    )
    by_year = (
        df.groupby("year")
        .agg(n=("panoid", "size"), waste_pos=("waste_positive", "sum"))
        .reset_index()
        .sort_values("year")
    )
    print("  Year counts (raw year before FE pooling/reassignment already applied):")
    for _, r in by_year.iterrows():
        print(f"    {int(r['year'])}: n={int(r['n']):,} | waste+={int(r['waste_pos']):,}")

    frame_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_frame.csv"
    df.to_csv(frame_path, index=False)

    print("\n  Fitting nested model: year FE only...")
    result_year, _ = fit_year_only(df)
    print(result_year.summary())

    print("\n  Fitting primary model: s(signed_distance) + year FE...")
    result, year_cols = fit_year_and_distance(df)
    print(result.summary())

    lrt = likelihood_ratio_test(result, result_year)
    print(
        f"\n  LRT (year-only vs year + s(distance)): "
        f"LR={lrt['lr_stat']:.2f}, df={lrt['df_diff']:.1f}, p={lrt['p_value']:.3e}"
    )
    print(
        f"  AIC year-only={lrt['aic_year_only']:.1f} | "
        f"AIC full={lrt['aic_full']:.1f} | "
        f"ΔAIC={lrt['delta_aic_year_only_minus_full']:.1f}"
    )

    remains = bool(lrt["p_value"] < 0.05 or lrt["delta_aic_year_only_minus_full"] > 2)
    conclusion = (
        "Signed-distance relationship remained after adjustment for panorama capture year "
        "(year FE); the distance smooth improved fit vs a year-only model."
        if remains
        else "After year adjustment, evidence for an additional signed-distance association "
        "was weaker; interpret with care."
    )
    print(f"  Conclusion: {conclusion}")

    curve = prediction_curve(df, result, year_cols)
    curve_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_curve.csv"
    curve.to_csv(curve_path, index=False)

    year_tab = year_effects_table(df, result, year_cols)
    year_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_year_effects.csv"
    year_tab.to_csv(year_path, index=False)

    smooth_tab = smooth_coef_table(result)
    smooth_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_smooth_coefs.csv"
    smooth_tab.to_csv(smooth_path, index=False)

    llnull = getattr(result, "llnull", None)
    pseudo_r2 = (
        float(1.0 - (result.llf / llnull))
        if llnull not in (None, 0) and np.isfinite(llnull)
        else np.nan
    )

    summary = {
        "role": "primary_year_adjusted_temporal_robustness",
        "n_panoids": int(len(df)),
        "n_waste_positive": int(df["waste_positive"].sum()),
        "n_year_levels": int(df["year_fe"].nunique()),
        "year_levels": "|".join(sorted(df["year_fe"].unique().astype(str))),
        "min_year_n_pool": MIN_YEAR_N,
        "spline_df": SPLINE_DF,
        "spline_degree": SPLINE_DEGREE,
        "aic_full": float(result.aic),
        "aic_year_only": float(result_year.aic),
        "delta_aic_year_only_minus_full": lrt["delta_aic_year_only_minus_full"],
        "ll_full": lrt["ll_full"],
        "ll_year_only": lrt["ll_year_only"],
        "lrt_stat": lrt["lr_stat"],
        "lrt_df": lrt["df_diff"],
        "lrt_p_value": lrt["p_value"],
        "distance_remains_after_year_adj": int(remains),
        "deviance": float(result.deviance),
        "pseudo_r2_mcfadden": pseudo_r2,
        "signed_distance_min_m": float(df["signed_distance_m"].min()),
        "signed_distance_max_m": float(df["signed_distance_m"].max()),
        "signed_distance_p01_m": float(df["signed_distance_m"].quantile(0.01)),
        "signed_distance_p99_m": float(df["signed_distance_m"].quantile(0.99)),
        "unit": "panorama",
        "model": "logit(p) = a + s(signed_distance) + year_FE",
        "nested_null": "logit(p) = a + year_FE",
        "conclusion": conclusion,
    }
    summary_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_summary.csv"
    pd.DataFrame([summary]).to_csv(summary_path, index=False)

    lrt_path = OUTPUT_DIR / "Nairobi_signed_distance_gam_year_lrt.csv"
    pd.DataFrame([lrt | {"conclusion": conclusion, "distance_remains_after_year_adj": int(remains)}]).to_csv(
        lrt_path, index=False
    )

    thesis = pd.DataFrame(
        [
            ("Role", "Primary year-adjusted temporal robustness model", ""),
            ("Panoramas in GAM", f"{summary['n_panoids']:,}", ""),
            ("Waste-positive panoramas", f"{summary['n_waste_positive']:,}", ""),
            ("Year FE levels", summary["year_levels"], ""),
            ("Rare-year pool threshold", f"n < {MIN_YEAR_N}", "panoids"),
            ("Model", "logit(p)=a+s(signed_distance)+year_FE", ""),
            ("Nested comparison", "year-only vs year + s(distance)", ""),
            ("LRT statistic", f"{lrt['lr_stat']:.2f}", f"df={lrt['df_diff']:.1f}"),
            ("LRT p-value", f"{lrt['p_value']:.3e}", ""),
            ("AIC (year-only)", f"{lrt['aic_year_only']:.1f}", ""),
            ("AIC (year + distance)", f"{lrt['aic_full']:.1f}", ""),
            ("ΔAIC (year-only − full)", f"{lrt['delta_aic_year_only_minus_full']:.1f}", ""),
            (
                "McFadden pseudo-R² (full)",
                f"{pseudo_r2:.4f}" if np.isfinite(pseudo_r2) else "",
                "",
            ),
            (
                "Distance remains after year adjustment?",
                "Yes" if remains else "Weaker / check",
                "",
            ),
            ("Interpretation", conclusion, ""),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / "signed_distance_gam.csv"
    thesis.to_csv(thesis_path, index=False)

    print(f"\nWrote {frame_path}")
    print(f"Wrote {curve_path}")
    print(f"Wrote {year_path}")
    print(f"Wrote {smooth_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {lrt_path}")
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

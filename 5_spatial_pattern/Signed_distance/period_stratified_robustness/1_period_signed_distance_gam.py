#!/usr/bin/env python3
"""Period-stratified signed-distance logistic GAM (temporal robustness).

Splits GSVI panoramas into two nearly balanced capture periods:

  Period A: 2015–2019
  Period B: 2021–2022

Within each period fit (panorama unit):

  logit{P(Waste=1)} = α + s(signed_distance)

No within-period year FE — stratification is the temporal control.
Export predicted curves with bootstrap 95% CIs on a common distance grid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.gam.api import BSplines, GLMGam

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

# Always write under the external data root (not the code tree).
OUTPUT_DIR = PATTERN_DIR / "Signed_distance" / "period_stratified_robustness"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

PERIODS = {
    "2015_2019": {
        "label": "2015–2019",
        "years": {2015, 2016, 2017, 2018, 2019},
    },
    "2021_2022": {
        "label": "2021–2022",
        "years": {2021, 2022},
    },
}

SPLINE_DF = 8
SPLINE_DEGREE = 3
PRED_GRID_N = 200
CI_ALPHA = 0.05
BOOT_B = 80
BOOT_SEED = 42


def prepare_period_frame() -> pd.DataFrame:
    """Panorama-level analysis frame with year, period, signed distance."""
    points = enrich_sviwaste_frame()
    slums = load_slums()
    points = label_inside_settlement(points, slums)
    points["signed_distance_m"] = signed_distance_to_slums(points, slums)

    keep = [
        "panoid",
        "waste_positive",
        "inside_settlement",
        "year",
        "n_positive_views",
        "signed_distance_m",
    ]
    df = points[keep].copy()
    if hasattr(points, "geometry"):
        df["x"] = points.geometry.x.to_numpy()
        df["y"] = points.geometry.y.to_numpy()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year", "signed_distance_m", "waste_positive"]).copy()
    df["year"] = df["year"].astype(int)
    df["waste_positive"] = df["waste_positive"].astype(int)

    def _period(y: int) -> str | None:
        for key, meta in PERIODS.items():
            if y in meta["years"]:
                return key
        return None

    df["period"] = df["year"].map(_period)
    return df.loc[df["period"].notna()].reset_index(drop=True)


def fit_period_gam(df: pd.DataFrame):
    """Binomial GAM: intercept + smooth(signed_distance)."""
    y = df["waste_positive"].to_numpy(dtype=float)
    x_smooth = df[["signed_distance_m"]].astype(float)
    smoother = BSplines(x_smooth, df=[SPLINE_DF], degree=[SPLINE_DEGREE])
    exog = pd.DataFrame({"const": np.ones(len(df), dtype=float)})

    model = GLMGam(
        y,
        exog=exog,
        smoother=smoother,
        family=sm.families.Binomial(),
    )
    return model.fit()


def _predict(result, grid: np.ndarray) -> np.ndarray:
    n = len(grid)
    exog = np.ones((n, 1), dtype=float)
    return np.asarray(
        result.predict(exog=exog, exog_smooth=grid.reshape(-1, 1)),
        dtype=float,
    )


def _global_distance_grid(df: pd.DataFrame) -> np.ndarray:
    d_min = float(df["signed_distance_m"].quantile(0.01))
    d_max = float(df["signed_distance_m"].quantile(0.99))
    return np.linspace(d_min, d_max, PRED_GRID_N)


def prediction_curve_bootstrap(
    df: pd.DataFrame,
    result,
    grid: np.ndarray,
    period_key: str,
) -> pd.DataFrame:
    """Point curve from full-sample fit; percentile CI from clustered bootstrap."""
    mean = _predict(result, grid)
    n = len(df)
    rng = np.random.default_rng(BOOT_SEED + (abs(hash(period_key)) % 10_000))
    draws: list[np.ndarray] = []

    for _ in range(BOOT_B):
        idx = rng.integers(0, n, size=n)
        boot = df.iloc[idx]
        # Skip degenerate draws (all 0 or all 1 outcomes)
        if boot["waste_positive"].nunique() < 2:
            continue
        try:
            boot_fit = fit_period_gam(boot)
            draws.append(_predict(boot_fit, grid))
        except Exception:
            continue

    lo = np.full(len(grid), np.nan)
    hi = np.full(len(grid), np.nan)
    ci_method = "none"
    if draws:
        arr = np.vstack(draws)
        q_lo = 100.0 * (CI_ALPHA / 2.0)
        q_hi = 100.0 * (1.0 - CI_ALPHA / 2.0)
        lo = np.nanpercentile(arr, q_lo, axis=0)
        hi = np.nanpercentile(arr, q_hi, axis=0)
        ci_method = f"bootstrap_B{len(draws)}"
        print(f"  [{period_key}] bootstrap CI from {len(draws)}/{BOOT_B} draws")
    else:
        print(f"  [{period_key}] bootstrap failed; CIs left as NA")

    return pd.DataFrame(
        {
            "period": period_key,
            "period_label": PERIODS[period_key]["label"],
            "signed_distance_m": grid,
            "prob_waste_positive": mean,
            "prob_ci_low": lo,
            "prob_ci_high": hi,
            "ci_method": ci_method,
            "ci_alpha": CI_ALPHA,
        }
    )


def period_summary(df: pd.DataFrame, result, period_key: str) -> dict:
    llnull = getattr(result, "llnull", None)
    pseudo_r2 = (
        float(1.0 - (result.llf / llnull))
        if llnull not in (None, 0) and np.isfinite(llnull)
        else np.nan
    )
    years = sorted(df["year"].unique().tolist())
    return {
        "period": period_key,
        "period_label": PERIODS[period_key]["label"],
        "years": "|".join(str(y) for y in years),
        "n_panoids": int(len(df)),
        "n_waste_positive": int(df["waste_positive"].sum()),
        "pct_waste_positive": float(100.0 * df["waste_positive"].mean()),
        "n_inside_settlement": int(df["inside_settlement"].sum()),
        "pct_inside_settlement": float(100.0 * df["inside_settlement"].mean()),
        "signed_distance_min_m": float(df["signed_distance_m"].min()),
        "signed_distance_max_m": float(df["signed_distance_m"].max()),
        "aic": float(result.aic),
        "deviance": float(result.deviance),
        "pseudo_r2_mcfadden": pseudo_r2,
        "spline_df": SPLINE_DF,
        "bootstrap_B": BOOT_B,
        "model": "logit(p) = a + s(signed_distance)",
        "unit": "panorama",
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {OUTPUT_DIR}")

    print("Period-stratified signed-distance GAM...")
    full = prepare_period_frame()
    print(
        f"  Periods kept: n={len(full):,} panoramas | "
        f"waste+={int(full['waste_positive'].sum()):,}"
    )
    for key, meta in PERIODS.items():
        n = int((full["period"] == key).sum())
        pos = int(((full["period"] == key) & (full["waste_positive"] == 1)).sum())
        print(f"  {meta['label']}: n={n:,} | waste+={pos:,}")

    frame_path = OUTPUT_DIR / "Nairobi_period_signed_distance_frame.csv"
    full.to_csv(frame_path, index=False)
    print(f"Wrote {frame_path}")

    grid = _global_distance_grid(full)
    curve_rows: list[pd.DataFrame] = []
    summaries: list[dict] = []

    for key in PERIODS:
        sub = full.loc[full["period"] == key].copy()
        if len(sub) < 50 or int(sub["waste_positive"].sum()) < 5:
            print(f"  Skipping {key}: too few observations")
            continue
        print(f"  Fitting GAM — {PERIODS[key]['label']} (n={len(sub):,})...")
        result = fit_period_gam(sub)
        print(result.summary())
        curve_rows.append(prediction_curve_bootstrap(sub, result, grid, key))
        summaries.append(period_summary(sub, result, key))

    if not curve_rows:
        raise SystemExit("No period models fitted.")

    curve = pd.concat(curve_rows, ignore_index=True)
    curve_path = OUTPUT_DIR / "Nairobi_period_signed_distance_gam_curve.csv"
    curve.to_csv(curve_path, index=False)
    print(f"Wrote {curve_path}")

    summary_df = pd.DataFrame(summaries)
    summary_path = OUTPUT_DIR / "Nairobi_period_signed_distance_gam_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}")

    counts = []
    for key, meta in PERIODS.items():
        sub = full.loc[full["period"] == key]
        counts.append(
            {
                "period": meta["label"],
                "years": ",".join(str(y) for y in sorted(meta["years"])),
                "n_gsvi_panoids": int(len(sub)),
                "n_waste_positive": int(sub["waste_positive"].sum()),
                "pct_waste_positive": round(100.0 * sub["waste_positive"].mean(), 3)
                if len(sub)
                else np.nan,
            }
        )
    counts_path = OUTPUT_DIR / "Nairobi_period_capture_counts.csv"
    pd.DataFrame(counts).to_csv(counts_path, index=False)
    print(f"Wrote {counts_path}")

    thesis_rows = []
    for row in summaries:
        thesis_rows.extend(
            [
                (f"{row['period_label']}: panoramas", f"{row['n_panoids']:,}", ""),
                (
                    f"{row['period_label']}: waste-positive",
                    f"{row['n_waste_positive']:,}",
                    "",
                ),
                (
                    f"{row['period_label']}: McFadden pseudo-R²",
                    f"{row['pseudo_r2_mcfadden']:.4f}"
                    if np.isfinite(row["pseudo_r2_mcfadden"])
                    else "",
                    "",
                ),
            ]
        )
    thesis_rows.append(
        ("Model (each period)", "logit(p)=a+s(signed_distance)", "")
    )
    thesis_rows.append(
        (
            "Interpretation",
            "Period-stratified P(waste+|signed distance); "
            "robustness of settlement-distance gradient",
            "",
        )
    )
    thesis_path = TABLE_DIR / "period_signed_distance_gam.csv"
    pd.DataFrame(thesis_rows, columns=["Variable", "Value", "Unit"]).to_csv(
        thesis_path, index=False
    )
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

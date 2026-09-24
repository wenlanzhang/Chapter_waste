#!/usr/bin/env python3
"""Step 6.4c — the signed-distance GAM, with and without self-collected imagery.

Step 5c fits, on all 76,605 GSVI panoramas:

  logit P(waste_i = 1) = a + s(signed_distance_i) + gamma_{year_i}

This script refits the identical specification on the combined frame (79,584
locations, 2,845 positive) and reports the two side by side. Self-collected
imagery carries a capture year (ZWL 2023, Faith 2015-2016), so the year fixed
effect survives; the combined frame simply gains 2015, 2016 and 2023 levels.

The GSVI column is a deliberate re-derivation rather than a copy: if it does not
reproduce Step 5c exactly, the comparison is not like for like.

Alongside the fitted curves the script computes the same relationship without a
model — the observed rate by distance band, on both arms — so the curves can be
read against something that assumes nothing.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/Signed_distance/):
  1_Nairobi_sc_gam_curve.csv             year-standardised curves, both arms
  1_Nairobi_sc_rate_by_band.csv          observed rate by distance band, both arms
  thesis_table/table_6_4_gam_comparison.csv
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.gam.api import BSplines, GLMGam

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.gam import PRED_GRID_N, SPLINE_DEGREE, SPLINE_DF, assign_year_fe  # noqa: E402
from sc_frames import ARM_LABELS, PATTERN_DIR, load_frames  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "Signed_distance"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

CURVE_CSV = OUTPUT_DIR / "1_Nairobi_sc_gam_curve.csv"
BAND_CSV = OUTPUT_DIR / "1_Nairobi_sc_rate_by_band.csv"
GAM_TABLE = TABLE_DIR / "table_6_4_gam_comparison.csv"

# Same bands as Step 5c's proximity descriptives, so the two are comparable.
BAND_EDGES = [0, 250, 500, 1000, 2000, 5000]


# ---------------------------------------------------------------------------
# Model-free: observed rate by distance band
# ---------------------------------------------------------------------------
def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = successes / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) / n) + z2 / (4.0 * n * n)) / den
    return max(0.0, centre - margin), min(1.0, centre + margin)


def band_label(lo: float, hi: float) -> str:
    if not np.isfinite(lo):
        return "Inside settlement"
    if not np.isfinite(hi):
        return f">{lo:,.0f} m"
    return f"{lo:,.0f}–{hi:,.0f} m"


def rate_by_band(df: pd.DataFrame, key: str) -> pd.DataFrame:
    edges = [-np.inf, *BAND_EDGES, np.inf]
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sub = df[(df["signed_distance_m"] > lo) & (df["signed_distance_m"] <= hi)]
        if sub.empty:
            continue
        k, n = int(sub["waste_positive"].sum()), len(sub)
        ci_low, ci_high = wilson_ci(k, n)
        rows.append(
            {
                "arm": key,
                "band": band_label(lo, hi),
                "band_low_m": lo,
                "n_locations": n,
                "n_waste_positive": k,
                "rate_pct": round(100 * k / n, 2),
                "rate_ci95_low_pct": round(100 * ci_low, 2),
                "rate_ci95_high_pct": round(100 * ci_high, 2),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The GAM
# ---------------------------------------------------------------------------
def model_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["obs_key", "waste_positive", "inside_settlement", "year",
              "signed_distance_m", "is_self_collected"]].copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out = out.dropna(subset=["year", "signed_distance_m", "waste_positive"])
    out["year"] = out["year"].astype(int)
    out["waste_positive"] = out["waste_positive"].astype(int)
    return assign_year_fe(out).reset_index(drop=True)


def _year_exog(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    dummies = pd.get_dummies(df["year_fe"], drop_first=True, prefix="year")
    exog = sm.add_constant(dummies.astype(float), has_constant="add")
    return exog, dummies.columns.tolist()


def fit_year_only(df: pd.DataFrame):
    exog, cols = _year_exog(df)
    return sm.GLM(df["waste_positive"].to_numpy(dtype=float), exog,
                  family=sm.families.Binomial()).fit(), cols


def fit_year_and_distance(df: pd.DataFrame):
    smoother = BSplines(df[["signed_distance_m"]].astype(float),
                        df=[SPLINE_DF], degree=[SPLINE_DEGREE])
    exog, cols = _year_exog(df)
    return GLMGam(df["waste_positive"].to_numpy(dtype=float), exog=exog,
                  smoother=smoother, family=sm.families.Binomial()).fit(), cols


def year_standardised_curve(df: pd.DataFrame, result, year_cols: list[str]) -> pd.DataFrame:
    """Average predicted P(waste | distance, year) over the observed year mix."""
    weights = df["year_fe"].astype(str).value_counts(normalize=True)
    grid = np.linspace(df["signed_distance_m"].quantile(0.01),
                       df["signed_distance_m"].quantile(0.99), PRED_GRID_N)
    pred = np.zeros(len(grid), dtype=float)
    for level, w in weights.items():
        exog = pd.DataFrame({"const": np.ones(len(grid))})
        for col in year_cols:
            exog[col] = 1.0 if col.replace("year_", "", 1) == str(level) else 0.0
        pred += float(w) * np.asarray(
            result.predict(exog=exog.to_numpy(dtype=float), exog_smooth=grid.reshape(-1, 1)),
            dtype=float,
        )
    return pd.DataFrame({"signed_distance_m": grid, "prob_waste_positive": pred})


def fit_arm(df: pd.DataFrame, key: str) -> dict:
    print(f"\n[{key}] fitting year-only and year + s(distance)...")
    m0, _ = fit_year_only(df)
    m1, year_cols = fit_year_and_distance(df)

    y = df["waste_positive"].to_numpy(dtype=float)
    p_bar = y.mean()
    null_ll = float(np.sum(y * np.log(p_bar) + (1 - y) * np.log(1 - p_bar)))

    lr_stat = 2.0 * (m1.llf - m0.llf)
    df_diff = max(1, int(round(m1.df_model - m0.df_model)))
    p_lrt = float(stats.chi2.sf(lr_stat, df_diff))

    curve = year_standardised_curve(df, m1, year_cols)
    curve.insert(0, "arm", key)

    print(f"  LRT chi2 = {lr_stat:,.1f} (df {df_diff}), p = {p_lrt:.3g} | "
          f"pseudo-R2 = {1 - m1.llf / null_ll:.3f}")
    return {
        "curve": curve,
        "n": len(df),
        "n_positive": int(y.sum()),
        "lr_stat": lr_stat,
        "df_diff": df_diff,
        "p_lrt": p_lrt,
        "pseudo_r2_m0": float(1 - m0.llf / null_ll),
        "pseudo_r2_m1": float(1 - m1.llf / null_ll),
        "aic_m0": float(m0.aic),
        "aic_m1": float(m1.aic),
        "year_levels": sorted(df["year_fe"].astype(str).unique()),
    }


def build_gam_table(fits: dict[str, dict], bands: pd.DataFrame) -> pd.DataFrame:
    g, s = fits["gsvi"], fits["gsvi_selfcollected"]

    def band_rate(key: str, band: str) -> str:
        row = bands[(bands["arm"] == key) & (bands["band"] == band)]
        return "—" if row.empty else f"{row['rate_pct'].iloc[0]:.1f}%"

    rows = [
        ("Observation locations", f"{g['n']:,}", f"{s['n']:,}"),
        ("Waste-positive", f"{g['n_positive']:,}", f"{s['n_positive']:,}"),
        ("Year FE levels", ", ".join(g["year_levels"]), ", ".join(s["year_levels"])),
        ("LRT vs year-only, χ² (df)", f"{g['lr_stat']:,.1f} ({g['df_diff']})",
         f"{s['lr_stat']:,.1f} ({s['df_diff']})"),
        ("LRT p-value", f"{g['p_lrt']:.3g}", f"{s['p_lrt']:.3g}"),
        ("Pseudo-R², year only", f"{g['pseudo_r2_m0']:.3f}", f"{s['pseudo_r2_m0']:.3f}"),
        ("Pseudo-R², year + s(distance)", f"{g['pseudo_r2_m1']:.3f}", f"{s['pseudo_r2_m1']:.3f}"),
        ("AIC, year only", f"{g['aic_m0']:,.0f}", f"{s['aic_m0']:,.0f}"),
        ("AIC, year + s(distance)", f"{g['aic_m1']:,.0f}", f"{s['aic_m1']:,.0f}"),
    ]
    # Model-free anchors: the two ends of the observed gradient.
    for band in ("Inside settlement", ">5,000 m"):
        rows.append((f"Observed rate, {band.lower()}",
                     band_rate("gsvi", band), band_rate("gsvi_selfcollected", band)))

    out = pd.DataFrame(rows, columns=["Measure", "GSVI", "GSVI + SC"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(GAM_TABLE, index=False)
    print(f"\n6.4c — signed-distance GAM:\n{out.to_string(index=False)}")
    print(f"Wrote {GAM_TABLE}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    # The 80k-row analysis frame is rebuilt from Step 2c on every run, so it is
    # not written out; only the fitted curves and band rates are.
    frames = {key: model_frame(df) for key, df in load_frames().items()}

    bands = pd.concat([rate_by_band(df, key) for key, df in frames.items()], ignore_index=True)
    bands.to_csv(BAND_CSV, index=False)
    print("\nObserved waste-positive rate by distance band:")
    for key in frames:
        sub = bands[bands["arm"] == key]
        print(f"  [{ARM_LABELS[key]}] " + " | ".join(
            f"{r.band} {r.rate_pct:.1f}%" for r in sub.itertuples()))
    print(f"Wrote {BAND_CSV}")

    fits = {key: fit_arm(df, key) for key, df in frames.items()}
    pd.concat([f["curve"] for f in fits.values()], ignore_index=True).to_csv(CURVE_CSV, index=False)
    print(f"Wrote {CURVE_CSV}")

    build_gam_table(fits, bands)


if __name__ == "__main__":
    main()

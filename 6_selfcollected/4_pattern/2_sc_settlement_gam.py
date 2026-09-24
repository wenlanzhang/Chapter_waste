#!/usr/bin/env python3
"""Step 6.4b/c — settlement association and the signed-distance GAM, with SC added.

Steps 5b and 5c are the two statements the chapter makes about where waste is:

  5b  a 2x2 contingency — waste-positive rate inside vs outside mapped
      urban-poor settlements, with prevalence ratio, odds ratio and chi-square
  5c  logit P(waste) = a + s(signed distance to settlement) + year FE

Both are refitted here on the combined observation frame (79,584 locations,
2,845 waste-positive) and reported beside the GSVI results. Self-collected
imagery carries a capture year (ZWL 2023, Faith 2015-2016), so the year fixed
effect survives; the combined frame simply gains a 2023 level.

Both blocks share the expensive frame preparation (settlement labelling and
signed distances over ~80k points), so they run in one script and write
separate tables.

The question is not whether the gradient exists — it is whether adding imagery
collected deliberately near settlements makes the settlement association look
stronger than GSVI alone reported. If the rates barely move, the association is
not an artefact of where the platform happened to drive.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/):
  2_Nairobi_sc_gam_frame.csv                     the combined analysis frame
  2_Nairobi_sc_gam_curve.csv                     fitted curves, both arms
  2_sc_settlement_contingency.csv                the 2x2, both arms
  thesis_table/table_6_4_settlement_comparison.csv
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
from scipy.stats import chi2_contingency
from statsmodels.gam.api import BSplines, GLMGam

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir  # noqa: E402
from lib.gam import PRED_GRID_N, SPLINE_DEGREE, SPLINE_DF, assign_year_fe  # noqa: E402
from lib.panoids import (  # noqa: E402
    enrich_combined_frame,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

OUTPUT_DIR = selfcollected_dir() / "4_pattern"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

FRAME_CSV = OUTPUT_DIR / "2_Nairobi_sc_gam_frame.csv"
CURVE_CSV = OUTPUT_DIR / "2_Nairobi_sc_gam_curve.csv"
CONTINGENCY_CSV = OUTPUT_DIR / "2_sc_settlement_contingency.csv"
SETTLEMENT_TABLE = TABLE_DIR / "table_6_4_settlement_comparison.csv"
GAM_TABLE = TABLE_DIR / "table_6_4_gam_comparison.csv"

ARM_LABELS = {"gsvi": "GSVI", "gsvi_selfcollected": "GSVI + SC"}


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------
def build_frames() -> dict[str, pd.DataFrame]:
    """One analysis frame per arm, both labelled against the same settlements."""
    slums = load_slums()

    def finish(points, key_col: str) -> pd.DataFrame:
        points = label_inside_settlement(points, slums)
        points["signed_distance_m"] = signed_distance_to_slums(points, slums)
        df = pd.DataFrame(
            {
                "obs_key": points[key_col].astype(str).to_numpy(),
                "waste_positive": pd.to_numeric(points["waste_positive"], errors="coerce"),
                "inside_settlement": points["inside_settlement"].to_numpy(),
                "year": pd.to_numeric(points["year"], errors="coerce"),
                "signed_distance_m": points["signed_distance_m"].to_numpy(),
                "is_self_collected": points["is_self_collected"].to_numpy()
                if "is_self_collected" in points.columns
                else 0,
            }
        )
        df = df.dropna(subset=["year", "signed_distance_m", "waste_positive"])
        df["year"] = df["year"].astype(int)
        df["waste_positive"] = df["waste_positive"].astype(int)
        return assign_year_fe(df).reset_index(drop=True)

    print("Preparing GSVI frame...")
    gsvi = finish(enrich_sviwaste_frame(), "panoid")
    print("Preparing GSVI + self-collected frame...")
    combined = finish(enrich_combined_frame(), "obs_key")
    for key, df in (("gsvi", gsvi), ("gsvi_selfcollected", combined)):
        print(f"  [{key}] {len(df):,} locations | {int(df['waste_positive'].sum()):,} waste-positive "
              f"({100 * df['waste_positive'].mean():.2f}%)")
    return {"gsvi": gsvi, "gsvi_selfcollected": combined}


# ---------------------------------------------------------------------------
# 6.4b — settlement association
# ---------------------------------------------------------------------------
def odds_ratio_with_ci(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    if min(a, b, c, d) <= 0:
        return np.nan, np.nan, np.nan
    odds = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return float(odds), float(math.exp(math.log(odds) - 1.96 * se)), float(math.exp(math.log(odds) + 1.96 * se))


def settlement_stats(df: pd.DataFrame) -> dict:
    waste = df["waste_positive"].to_numpy() == 1
    inside = df["inside_settlement"].to_numpy() == 1
    a = int((waste & inside).sum())
    b = int((~waste & inside).sum())
    c = int((waste & ~inside).sum())
    d = int((~waste & ~inside).sum())
    chi2, p_chi2, _, _ = chi2_contingency(np.array([[a, b], [c, d]], dtype=float), correction=False)
    n = a + b + c + d
    p_in = a / (a + b) if a + b else np.nan
    p_out = c / (c + d) if c + d else np.nan
    odds, or_lo, or_hi = odds_ratio_with_ci(a, b, c, d)
    return {
        "a": a, "b": b, "c": c, "d": d, "n": n,
        "n_inside": a + b, "n_outside": c + d,
        "rate_inside_pct": 100 * p_in, "rate_outside_pct": 100 * p_out,
        "prevalence_ratio": p_in / p_out if p_out else np.nan,
        "odds_ratio": odds, "or_lo": or_lo, "or_hi": or_hi,
        "chi2": float(chi2), "p_chi2": float(p_chi2),
        "cramers_v": float(np.sqrt(chi2 / n)) if n else np.nan,
        "pct_positives_inside": 100 * a / (a + c) if a + c else np.nan,
    }


def table_settlement(stats_by_arm: dict[str, dict]) -> pd.DataFrame:
    g, s = stats_by_arm["gsvi"], stats_by_arm["gsvi_selfcollected"]
    rows = [
        ("Locations in the frame", f"{g['n']:,}", f"{s['n']:,}"),
        ("Waste-positive locations", f"{g['a'] + g['c']:,}", f"{s['a'] + s['c']:,}"),
        ("Locations inside a settlement", f"{g['n_inside']:,}", f"{s['n_inside']:,}"),
        ("Waste-positive rate inside", f"{g['rate_inside_pct']:.1f}%", f"{s['rate_inside_pct']:.1f}%"),
        ("Waste-positive rate outside", f"{g['rate_outside_pct']:.1f}%", f"{s['rate_outside_pct']:.1f}%"),
        ("Prevalence ratio (inside / outside)", f"{g['prevalence_ratio']:.2f}", f"{s['prevalence_ratio']:.2f}"),
        ("Odds ratio (95% CI)",
         f"{g['odds_ratio']:.2f} ({g['or_lo']:.2f}–{g['or_hi']:.2f})",
         f"{s['odds_ratio']:.2f} ({s['or_lo']:.2f}–{s['or_hi']:.2f})"),
        ("Pearson χ²", f"{g['chi2']:,.1f}", f"{s['chi2']:,.1f}"),
        ("Cramér's V", f"{g['cramers_v']:.3f}", f"{s['cramers_v']:.3f}"),
        ("Waste-positive locations inside a settlement",
         f"{g['pct_positives_inside']:.1f}%", f"{s['pct_positives_inside']:.1f}%"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "GSVI", "GSVI + SC"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(SETTLEMENT_TABLE, index=False)
    print(f"\n6.4b — settlement association:\n{out.to_string(index=False)}")
    print(f"Wrote {SETTLEMENT_TABLE}")

    contingency = pd.DataFrame(
        [
            {"Arm": ARM_LABELS[k], "Zone": zone, "Waste-positive": w, "Non-positive": nw}
            for k, st in stats_by_arm.items()
            for zone, w, nw in (("Inside settlement", st["a"], st["b"]),
                                ("Outside settlement", st["c"], st["d"]))
        ]
    )
    contingency.to_csv(CONTINGENCY_CSV, index=False)
    print(f"Wrote {CONTINGENCY_CSV}")
    return out


# ---------------------------------------------------------------------------
# 6.4c — signed-distance GAM
# ---------------------------------------------------------------------------
def _year_exog(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    dummies = pd.get_dummies(df["year_fe"], drop_first=True, prefix="year")
    return sm.add_constant(dummies.astype(float), has_constant="add"), dummies.columns.tolist()


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


def pseudo_r2(result, null_ll: float) -> float:
    return float(1.0 - result.llf / null_ll)


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

    # Year-standardised prediction curve: average over the observed year mix.
    weights = df["year_fe"].astype(str).value_counts(normalize=True)
    grid = np.linspace(df["signed_distance_m"].quantile(0.01),
                       df["signed_distance_m"].quantile(0.99), PRED_GRID_N)
    pred = np.zeros(len(grid))
    for level, w in weights.items():
        exog = pd.DataFrame({"const": np.ones(len(grid))})
        for col in year_cols:
            exog[col] = 1.0 if col.replace("year_", "", 1) == str(level) else 0.0
        pred += float(w) * np.asarray(
            m1.predict(exog=exog.to_numpy(dtype=float), exog_smooth=grid.reshape(-1, 1)), dtype=float
        )

    print(f"  LRT chi2 = {lr_stat:,.1f} (df {df_diff}), p = {p_lrt:.3g} | "
          f"pseudo-R2 = {pseudo_r2(m1, null_ll):.3f}")
    return {
        "curve": pd.DataFrame({"arm": key, "signed_distance_m": grid, "prob_waste_positive": pred}),
        "n": len(df),
        "n_positive": int(y.sum()),
        "lr_stat": lr_stat,
        "df_diff": df_diff,
        "p_lrt": p_lrt,
        "pseudo_r2_m0": pseudo_r2(m0, null_ll),
        "pseudo_r2_m1": pseudo_r2(m1, null_ll),
        "aic_m0": float(m0.aic),
        "aic_m1": float(m1.aic),
        "year_levels": sorted(df["year_fe"].astype(str).unique()),
    }


def table_gam(fits: dict[str, dict]) -> pd.DataFrame:
    g, s = fits["gsvi"], fits["gsvi_selfcollected"]
    rows = [
        ("Locations", f"{g['n']:,}", f"{s['n']:,}"),
        ("Waste-positive", f"{g['n_positive']:,}", f"{s['n_positive']:,}"),
        ("Year FE levels", ", ".join(g["year_levels"]), ", ".join(s["year_levels"])),
        ("LRT vs year-only, χ² (df)", f"{g['lr_stat']:,.1f} ({g['df_diff']})", f"{s['lr_stat']:,.1f} ({s['df_diff']})"),
        ("LRT p-value", f"{g['p_lrt']:.3g}", f"{s['p_lrt']:.3g}"),
        ("Pseudo-R², year only", f"{g['pseudo_r2_m0']:.3f}", f"{s['pseudo_r2_m0']:.3f}"),
        ("Pseudo-R², year + s(distance)", f"{g['pseudo_r2_m1']:.3f}", f"{s['pseudo_r2_m1']:.3f}"),
        ("AIC, year only", f"{g['aic_m0']:,.0f}", f"{s['aic_m0']:,.0f}"),
        ("AIC, year + s(distance)", f"{g['aic_m1']:,.0f}", f"{s['aic_m1']:,.0f}"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "GSVI", "GSVI + SC"])
    out.to_csv(GAM_TABLE, index=False)
    print(f"\n6.4c — signed-distance GAM:\n{out.to_string(index=False)}")
    print(f"Wrote {GAM_TABLE}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    frames = build_frames()
    frames["gsvi_selfcollected"].to_csv(FRAME_CSV, index=False)
    print(f"Wrote {FRAME_CSV}")

    table_settlement({k: settlement_stats(df) for k, df in frames.items()})

    fits = {k: fit_arm(df, k) for k, df in frames.items()}
    pd.concat([f["curve"] for f in fits.values()], ignore_index=True).to_csv(CURVE_CSV, index=False)
    print(f"Wrote {CURVE_CSV}")
    table_gam(fits)


if __name__ == "__main__":
    main()

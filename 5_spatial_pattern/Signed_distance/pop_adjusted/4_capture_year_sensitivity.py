#!/usr/bin/env python3
"""Capture-year treatment and imagery-period sensitivity.

The population-adjusted GAM controls capture year with year fixed effects.
A year with < 200 panoramas or no waste-positive panorama cannot carry its own
effect, so `lib.gam.assign_year_fe` joins each such year to its nearest usable
year: 2015 (5 panoramas) to 2017 and 2019 (73) to 2018. This script checks
whether results depend on that grouping, and whether one static population
layer represents imagery captured years apart.

Specifications, each fitted with the same nested GAMs (M0, MP, MD, MDP):

  original           main specification: 2015 joined to 2017, 2019 to 2018
  exclude_2015_2019  the 78 panoramas from 2015 and 2019 dropped
  early_2017_2018    2017–2018 imagery only (year FE within period)
  late_2021_2022     2021–2022 imagery only (year FE within period)

The period split checks whether the population and distance relationships hold
in imagery captured either side of the population layer's reference year.

For each: n, positives, ΔAIC and LRT for MP vs MDP (does distance add to
population?) and M0 vs MP (does population add to year?), McFadden pseudo-R²,
the inside/outside settlement prevalence ratio, and the pop- and
year-standardised MDP distance curve. Intervals for the ratio and the curve use
the spatial block bootstrap (2 km blocks, the scale at which the residual
correlation reaches zero; see 3_spatial_block_bootstrap.py).

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

from lib.gam import BOOT_SEED, PRED_GRID_N, assign_year_fe  # noqa: E402
from lib.script_loader import load_script  # noqa: E402


pag = load_script(SCRIPT_DIR / "1_pop_adjusted_gam.py")
bb = load_script(SCRIPT_DIR / "3_spatial_block_bootstrap.py")

BLOCK_M = 2000.0
N_BOOT = 500  # as 3_spatial_block_bootstrap.py
SPECS = {
    "original": ("Main: 2015 joined to 2017, 2019 to 2018", None),
    "exclude_2015_2019": ("2015 and 2019 panoramas excluded", lambda y: ~y.isin([2015, 2019])),
    "early_2017_2018": ("Early imagery only, 2017–2018", lambda y: y.isin([2017, 2018])),
    "late_2021_2022": ("Late imagery only, 2021–2022", lambda y: y.isin([2021, 2022])),
}


def fit_all(df: pd.DataFrame) -> dict:
    d = assign_year_fe(df.drop(columns=["year_fe"], errors="ignore"), verbose=False)
    m0, _ = pag.fit_m0(d)
    mp, _ = pag.fit_mp(d)
    md, _ = pag.fit_md(d)
    mdp, cols = pag.fit_mdp(d)
    lrt_pd = pag.likelihood_ratio_test(mdp, mp, "MP_vs_MDP")
    lrt_0p = pag.likelihood_ratio_test(mp, m0, "M0_vs_MP")
    lrt_dd = pag.likelihood_ratio_test(mdp, md, "MD_vs_MDP")
    return {
        "frame": d,
        "year_fe_levels": "|".join(sorted(d["year_fe"].astype(str).unique())),
        "delta_aic_MP_minus_MDP": lrt_pd["delta_aic_nested_minus_full"],
        "lrt_MP_vs_MDP": lrt_pd["lr_stat"],
        "lrt_MP_vs_MDP_p": lrt_pd["p_value"],
        "delta_aic_M0_minus_MP": lrt_0p["delta_aic_nested_minus_full"],
        "lrt_M0_vs_MP_p": lrt_0p["p_value"],
        "delta_aic_MD_minus_MDP": lrt_dd["delta_aic_nested_minus_full"],
        "lrt_MD_vs_MDP_p": lrt_dd["p_value"],
        "pseudo_r2_MDP": pag._model_metrics(mdp, "MDP", len(d))["pseudo_r2_mcfadden"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-subdir", default=pag.MANUSCRIPT_SUBDIR,
                    help="run folder under pop_adjusted/ (default: worldpop_2020, the manuscript sample)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    base = pag.POP_ADJ_ROOT / args.data_subdir
    out_dir, table_dir = base / "capture_year", base / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    full = pd.read_csv(base / "Nairobi_pop_adjusted_gam_frame.csv", dtype={"year_fe": str, "panoid": str})
    full["year"] = pd.to_numeric(full["year"], errors="coerce").astype(int)
    print(f"Frame {base.name}: n={len(full):,}; years {full['year'].value_counts().sort_index().to_dict()}")

    # one distance grid for every specification, so curves are comparable
    grid = np.linspace(
        float(full["signed_distance_m"].quantile(0.01)),
        float(full["signed_distance_m"].quantile(0.99)),
        PRED_GRID_N,
    )

    rows, curves = [], []
    for key, (label, keep) in SPECS.items():
        df = full if keep is None else full.loc[keep(full["year"])].reset_index(drop=True)
        print(f"{label}: n={len(df):,}, waste+={int(df['waste_positive'].sum()):,}")
        fit = fit_all(df)
        curve, cstats = bb.curve_stats(df, grid, BOOT_SEED)
        ratios = bb.ratio_measures(df)

        # 2 km spatial block bootstrap for the ratio and the curve
        # Same replicate stream as 3_spatial_block_bootstrap.py, so the main
        # specification reproduces that table's 2 km intervals exactly.
        rng = np.random.default_rng(pag.block_bootstrap_seed(BLOCK_M))
        xy = df[["x", "y"]].to_numpy(dtype=float)
        draws, pr, contrast = [], [], []
        for r in range(args.n_boot):
            boot = df.iloc[bb.block_sample(xy, BLOCK_M, rng)].reset_index(drop=True)
            if boot["waste_positive"].nunique() < 2:
                continue
            try:
                c, s = bb.curve_stats(boot, grid, BOOT_SEED + r)
            except Exception:
                continue
            draws.append(c)
            pr.append(bb.ratio_measures(boot)["prevalence_ratio"])
            contrast.append(s["curve_ratio_0m_vs_2000m"])
        draws = np.vstack(draws)
        print(f"  block bootstrap: {len(draws)}/{args.n_boot} draws")

        q = lambda a: (float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5)))
        pr_lo, pr_hi = q(pr)
        c_lo, c_hi = q(contrast)
        rows.append({
            "spec": key, "label": label,
            "n_panoramas": len(df), "n_positive": int(df["waste_positive"].sum()),
            "prevalence_pct": 100 * df["waste_positive"].mean(),
            **{k: v for k, v in fit.items() if k != "frame"},
            **ratios, "prevalence_ratio_lo": pr_lo, "prevalence_ratio_hi": pr_hi,
            **cstats, "curve_ratio_lo": c_lo, "curve_ratio_hi": c_hi,
            "n_boot": len(draws), "block_m": BLOCK_M,
        })
        curves.append(pd.DataFrame({
            "spec": key, "label": label, "signed_distance_m": grid, "prob": curve,
            "prob_lo": np.percentile(draws, 2.5, axis=0),
            "prob_hi": np.percentile(draws, 97.5, axis=0),
        }))

    res = pd.DataFrame(rows)
    cur = pd.concat(curves, ignore_index=True)

    # how far each curve sits from the published specification
    ref = cur[cur.spec == "original"]["prob"].to_numpy()
    for key in SPECS:
        c = cur[cur.spec == key]["prob"].to_numpy()
        res.loc[res.spec == key, "curve_corr_vs_original"] = float(np.corrcoef(c, ref)[0, 1])
        res.loc[res.spec == key, "curve_max_abs_diff_pp_vs_original"] = float(100 * np.max(np.abs(c - ref)))

    res.to_csv(out_dir / "Nairobi_capture_year_summary.csv", index=False)
    cur.to_csv(out_dir / "Nairobi_capture_year_curves.csv", index=False)

    thesis = pd.DataFrame({
        "Specification": res["label"],
        "Panoramas": res["n_panoramas"].map("{:,}".format),
        "Waste-positive": res["n_positive"].map("{:,}".format),
        "Year FE levels": res["year_fe_levels"],
        "ΔAIC M0 − MP (population)": res["delta_aic_M0_minus_MP"].map("{:,.0f}".format),
        "ΔAIC MP − MDP (distance)": res["delta_aic_MP_minus_MDP"].map("{:,.0f}".format),
        "LRT p (MP vs MDP)": res["lrt_MP_vs_MDP_p"].map("{:.1e}".format),
        "Pseudo-R² (MDP)": res["pseudo_r2_MDP"].map("{:.3f}".format),
        "Prevalence ratio (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(res.prevalence_ratio, res.prevalence_ratio_lo, res.prevalence_ratio_hi)],
        "Adjusted P(waste) edge → 2 km (%)": [
            f"{a:.2f} → {b:.2f}" for a, b in zip(res.curve_p_at_0m_pct, res.curve_p_at_2000m_pct)],
        "Edge ÷ 2 km (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(res.curve_ratio_0m_vs_2000m, res.curve_ratio_lo, res.curve_ratio_hi)],
        "Curve corr. with main": res["curve_corr_vs_original"].map("{:.3f}".format),
    })
    path = table_dir / "capture_year_sensitivity.csv"
    thesis.to_csv(path, index=False)
    print(f"Thesis table: {path}\nWrote outputs to {out_dir}")


if __name__ == "__main__":
    main()

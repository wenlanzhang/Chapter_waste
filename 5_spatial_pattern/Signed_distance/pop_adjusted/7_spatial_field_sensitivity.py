#!/usr/bin/env python3
"""Does the distance gradient survive a residual spatial field?

The spatial block bootstrap (3_spatial_block_bootstrap.py) keeps MDP as it is
and widens its intervals. This script changes the model instead: MDPS adds a
thin-plate spatial field on (x, y) to MDP, so that smooth residual spatial
variation is absorbed by the model and no longer left in the residuals.

  MPS : logit(p) = α + s(log1p(pop_density)) + field(x, y) + year
  MDPS: logit(p) = α + s(signed_distance) + s(log1p(pop_density)) + field(x, y) + year

Reported:
  - LRT and ΔAIC for MPS vs MDPS: does distance still add once population,
    year and the spatial field are all in the model?
  - the MDPS distance curve, standardised by setting every panorama's distance
    to each grid value in turn while it keeps its own population, capture year
    and location (averaged over N_STD panoramas evenly spaced in population rank)
  - the settlement-edge / 2 km contrast under MDP and under MDPS, with 2 km
    spatial block bootstrap intervals from the same replicates

Why the curves are compared relative to 2 km and not as levels: distance to a
settlement is itself a smooth function of location, so the field and the
distance term share part of the same signal. The field can take up the overall
level in a region, which leaves the *level* of the MDPS curve poorly
identified while its *shape* is not. The relative curve P(d) / P(2 km) is the
quantity the two models can be compared on.

Runs on the manuscript sample (worldpop_2020/) by default; --data-subdir picks another run.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in SCRIPT_DIR.parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.gam import assign_year_fe  # noqa: E402
from lib.script_loader import load_script  # noqa: E402


pag = load_script(SCRIPT_DIR / "1_pop_adjusted_gam.py")

BLOCK_M = pag.BLOCK_BOOT_M
N_BOOT = 500  # as 3_spatial_block_bootstrap.py
N_STD = 2000  # panoramas the MDPS curve is averaged over
REF_M = 2000.0  # curves are compared relative to this distance
EDGE_M = 0.0
COMPARE_MAX_M = 5000.0  # the range the figures show; the spline tail beyond is sparse


def field_design(df: pd.DataFrame, knots: np.ndarray) -> pd.DataFrame:
    """Parametric design of the field models: constant, year dummies, spatial basis."""
    exog, _ = pag._year_exog(df)
    return pd.concat([exog, pag.spatial_field(df, knots)], axis=1)


def fit_mps(df: pd.DataFrame, knots: np.ndarray):
    """MDPS without the distance term (same field, same penalty)."""
    result, _ = pag.fit_gam(df, [pag.POP], alpha=0.5, extra_exog=pag.spatial_field(df, knots))
    return result


def mdps_distance_curve(
    df: pd.DataFrame, result, knots: np.ndarray, grid: np.ndarray, n_std: int = N_STD
) -> np.ndarray:
    """MDPS P(waste+) over `grid`, each panorama keeping its own pop, year and location."""
    exog = field_design(df, knots)
    pop = df["log1p_pop_density"].to_numpy(dtype=float)
    n = min(n_std, len(df))
    idx = np.argsort(pop, kind="stable")[((np.arange(n) + 0.5) / n * len(df)).astype(int)]
    ex, pop_s = exog.to_numpy(dtype=float)[idx], pop[idx]
    out = np.empty(len(grid), dtype=float)
    for j, d in enumerate(grid):
        xs = np.column_stack([np.full(n, d), pop_s])
        out[j] = float(np.asarray(result.predict(exog=ex, exog_smooth=xs), dtype=float).mean())
    return out


def both_curves(df: pd.DataFrame, knots: np.ndarray, grid: np.ndarray) -> dict[str, np.ndarray]:
    """MDP and MDPS distance curves on one (re)sample, year FE reassigned."""
    d, res, cols = pag.refit_mdp(df)
    res_s, _, _ = pag.fit_mdps(d, knots=knots)
    return {
        "MDP": pag.mdp_distance_curve(d, res, cols, grid),
        "MDPS": mdps_distance_curve(d, res_s, knots, grid),
    }


def contrast(curve: np.ndarray, grid: np.ndarray) -> dict:
    p0, p2 = np.interp([EDGE_M, REF_M], grid, curve)
    return {"p_edge_pct": 100 * p0, "p_2km_pct": 100 * p2, "edge_vs_2km": p0 / p2}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-subdir", default=pag.MANUSCRIPT_SUBDIR,
                    help="run folder under pop_adjusted/ (default: worldpop_2020, the manuscript sample)")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    base = pag.POP_ADJ_ROOT / args.data_subdir
    out_dir, table_dir = base / "spatial_field", base / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(base / "Nairobi_pop_adjusted_gam_frame.csv", dtype={"year_fe": str, "panoid": str})
    df = assign_year_fe(df.drop(columns=["year_fe"], errors="ignore"), verbose=False)
    print(f"Frame {base.name}: n={len(df):,}, waste+={int(df['waste_positive'].sum()):,}")
    grid = pag.distance_grid(df)

    # ------------------------------------------------------------- full sample
    print("Full-sample fits (MP, MDP, MPS, MDPS)...")
    res_mp, _ = pag.fit_mp(df)
    res_mdp, cols_mdp = pag.fit_mdp(df)
    res_mdps, _, knots = pag.fit_mdps(df)
    res_mps = fit_mps(df, knots)
    tests = pd.DataFrame([
        pag.likelihood_ratio_test(res_mdp, res_mp, "MP_vs_MDP"),
        pag.likelihood_ratio_test(res_mdps, res_mps, "MPS_vs_MDPS"),
    ])
    tests.to_csv(out_dir / "Nairobi_spatial_field_lrt.csv", index=False)
    print(tests[["comparison", "lr_stat", "df_diff", "p_value", "delta_aic_nested_minus_full"]].to_string(index=False))

    full = {
        "MDP": pag.mdp_distance_curve(df, res_mdp, cols_mdp, grid),
        "MDPS": mdps_distance_curve(df, res_mdps, knots, grid),
    }
    shown = grid <= COMPARE_MAX_M
    rel = {m: c / np.interp(REF_M, grid, c) for m, c in full.items()}
    corr_shown = float(np.corrcoef(np.log(rel["MDP"][shown]), np.log(rel["MDPS"][shown]))[0, 1])
    corr_all = float(np.corrcoef(np.log(rel["MDP"]), np.log(rel["MDPS"]))[0, 1])
    print(f"  log relative curve, MDP vs MDPS: r = {corr_shown:.3f} to {COMPARE_MAX_M:,.0f} m, "
          f"{corr_all:.3f} over the full grid")

    # ------------------------------------------------------------- block bootstrap
    xy = df[["x", "y"]].to_numpy(dtype=float)
    rng = np.random.default_rng(pag.block_bootstrap_seed(BLOCK_M))  # the stream 3_ uses
    draws: dict[str, list[np.ndarray]] = {"MDP": [], "MDPS": []}
    t0 = time.time()
    for r in range(args.n_boot):
        boot = df.iloc[pag.block_sample(xy, BLOCK_M, rng)].reset_index(drop=True)
        if boot["waste_positive"].nunique() < 2:
            continue
        try:
            c = both_curves(boot, knots, grid)
        except Exception as exc:
            print(f"  rep {r}: failed ({exc})")
            continue
        for m in draws:
            draws[m].append(c[m])
        if (r + 1) % 50 == 0:
            print(f"  {r + 1}/{args.n_boot} replicates ({time.time() - t0:.0f}s)")
    mats = {m: np.vstack(v) for m, v in draws.items()}
    n_ok = len(mats["MDP"])

    # ------------------------------------------------------------- outputs
    rows, curve_rows = [], []
    ratio_draws = {}
    for m in ("MDP", "MDPS"):
        ref = np.array([np.interp(REF_M, grid, c) for c in mats[m]])
        edge = np.array([np.interp(EDGE_M, grid, c) for c in mats[m]])
        ratio_draws[m] = edge / ref
        rel_draws = mats[m] / ref[:, None]
        test = tests.iloc[0 if m == "MDP" else 1]
        rows.append({
            "model": m,
            **contrast(full[m], grid),
            "edge_vs_2km_lo": float(np.percentile(ratio_draws[m], 2.5)),
            "edge_vs_2km_hi": float(np.percentile(ratio_draws[m], 97.5)),
            "share_draws_ratio_le_1": float(np.mean(ratio_draws[m] <= 1.0)),
            "distance_test": test["comparison"],
            "lr_stat": test["lr_stat"], "df_diff": test["df_diff"], "p_value": test["p_value"],
            "delta_aic_distance": test["delta_aic_nested_minus_full"],
            "n_boot": n_ok, "block_m": BLOCK_M,
            "rel_curve_corr_mdp_vs_mdps_to_5km": corr_shown,
            "rel_curve_corr_mdp_vs_mdps_full_grid": corr_all,
        })
        curve_rows.append(pd.DataFrame({
            "model": m, "signed_distance_m": grid, "prob": full[m], "rel_to_2km": rel[m],
            "rel_lo": np.percentile(rel_draws, 2.5, axis=0),
            "rel_hi": np.percentile(rel_draws, 97.5, axis=0),
        }))
    summ = pd.DataFrame(rows)
    # how much of the MDP contrast the field removes, replicate by replicate
    atten = ratio_draws["MDPS"] / ratio_draws["MDP"]
    summ["mdps_over_mdp_contrast"] = float(summ.edge_vs_2km[1] / summ.edge_vs_2km[0])
    summ["mdps_over_mdp_contrast_lo"] = float(np.percentile(atten, 2.5))
    summ["mdps_over_mdp_contrast_hi"] = float(np.percentile(atten, 97.5))
    summ.to_csv(out_dir / "Nairobi_spatial_field_summary.csv", index=False)
    pd.concat(curve_rows, ignore_index=True).to_csv(out_dir / "Nairobi_spatial_field_curves.csv", index=False)

    label = {"MDP": "MDP: distance + population + year",
             "MDPS": "MDPS: MDP + thin-plate spatial field"}
    thesis = pd.DataFrame({
        "Model": summ.model.map(label),
        "Test of the distance term": summ.distance_test.str.replace("_", " "),
        "ΔAIC (distance adds)": summ.delta_aic_distance.map("{:,.0f}".format),
        "LRT p": summ.p_value.map("{:.1e}".format),
        "Edge ÷ 2 km (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(summ.edge_vs_2km, summ.edge_vs_2km_lo, summ.edge_vs_2km_hi)],
        "Draws with edge ÷ 2 km ≤ 1": [f"{round(s * n_ok)} / {n_ok}" for s in summ.share_draws_ratio_le_1],
    })
    path = table_dir / "spatial_field_sensitivity.csv"
    thesis.to_csv(path, index=False)
    print(thesis.to_string(index=False))
    print(f"Thesis table: {path}\nWrote outputs to {out_dir}")


if __name__ == "__main__":
    main()

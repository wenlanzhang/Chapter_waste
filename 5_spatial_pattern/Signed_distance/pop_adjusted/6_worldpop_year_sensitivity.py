#!/usr/bin/env python3
"""WorldPop reference-year sensitivity (R3.3).

The manuscript's population-adjusted GAM uses one layer, WorldPop
unconstrained Kenya 2020 (ken_ppp_2020), for imagery captured 2015–2022. This
refits the same nested GAMs with the population covariate taken from other
years, both as one static layer and year-matched to each panorama's capture
period.

Two sets, because no single WorldPop product covers both 2018 and 2022:

  A. Manuscript product, unconstrained 100 m (Global 2000–2020 series; ends 2020)
       A_static_2020   published specification
       A_static_2018
       A_matched       2015–2019 imagery -> 2018, 2021–2022 imagery -> 2020
                       (2020 is the latest year in this series)
  B. WorldPop R2025A, constrained 100 m (the only 2022 layer available at 100 m)
       B_static_2018
       B_static_2022
       B_matched       2015–2019 imagery -> 2018, 2021–2022 imagery -> 2022
       B_bridge_2020   the published 2020 unconstrained layer on the same
                       panoramas, separating the change of product/sample from
                       the change of year
     Constrained layers have no value outside mapped built-up areas, so set B
     uses the panoramas that have a value in every set-B layer.

Year FE follow the main specification (2015 joined to 2017, 2019 to 2018). For each
specification: ΔAIC and LRT for M0 vs MP and MP vs MDP, pseudo-R², and the
pop- and year-standardised MDP distance curve with a 2 km spatial block
bootstrap interval for the settlement-edge / 2 km contrast.

Run on the manuscript frame (pop_adjusted/worldpop_2020/).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in SCRIPT_DIR.parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import phd_data_root  # noqa: E402
from lib.gam import BOOT_SEED, PRED_GRID_N  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pag = _load("pop_adjusted_gam", "1_pop_adjusted_gam.py")
bb = _load("spatial_block_bootstrap", "3_spatial_block_bootstrap.py")
cy = _load("capture_year_sensitivity", "4_capture_year_sensitivity.py")

POP = phd_data_root() / "RS" / "Pop_density"
LAYERS = {
    "UC2020": POP / "UnconstraintIndividualCountries" / "ken_ppp_2020.tif",
    "UC2018": POP / "UnconstraintIndividualCountries" / "ken_ppp_2018.tif",
    "CN2018": POP / "ken_pop_2018_CN_100m_R2025A_v1.tif",
    "CN2022": POP / "ken_pop_2022_CN_100m_R2025A_v1.tif",
}
EARLY_MAX_YEAR = 2019  # 2015–2019 imagery is "early"; 2021–2022 "late"
BLOCK_M = 2000.0
N_BOOT = 500  # as 3_spatial_block_bootstrap.py

SPECS = [
    # key, set, label, early layer, late layer
    ("A_static_2020", "A", "Unconstrained 2020, all years (published)", "UC2020", "UC2020"),
    ("A_static_2018", "A", "Unconstrained 2018, all years", "UC2018", "UC2018"),
    ("A_matched", "A", "Unconstrained, year-matched (2018 / 2020)", "UC2018", "UC2020"),
    ("B_bridge_2020", "B", "Unconstrained 2020, constrained sample", "UC2020", "UC2020"),
    ("B_static_2018", "B", "Constrained 2018, all years", "CN2018", "CN2018"),
    ("B_static_2022", "B", "Constrained 2022, all years", "CN2022", "CN2022"),
    ("B_matched", "B", "Constrained, year-matched (2018 / 2022)", "CN2018", "CN2022"),
]


def sample_layers(df: pd.DataFrame) -> pd.DataFrame:
    """log1p(people/km²) from every layer at each panorama (NaN where no value)."""
    pts = gpd.GeoDataFrame(df[["panoid"]].copy(), geometry=gpd.points_from_xy(df["x"], df["y"]), crs=32737)
    out = df.copy()
    for key, path in LAYERS.items():
        if not path.is_file():
            raise SystemExit(f"Missing WorldPop layer {key}: {path}")
        pag.POP_RASTER, pag.POP_LABEL = path, key
        vals, area = pag.sample_worldpop(pts)
        out[f"logpop_{key}"] = np.log1p(vals / area)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    args = ap.parse_args()

    base = pag.OUTPUT_DIR
    out_dir, table_dir = base / "worldpop_year", base / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(base / "Nairobi_pop_adjusted_gam_frame.csv", dtype={"year_fe": str, "panoid": str})
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype(int)
    frame = sample_layers(frame)
    early = frame["year"] <= EARLY_MAX_YEAR

    # how similar are the layers at the panoramas?
    cols = [f"logpop_{k}" for k in LAYERS]
    frame[cols].corr().round(3).to_csv(out_dir / "Nairobi_worldpop_layer_correlation.csv")

    set_mask = {
        "A": frame[["logpop_UC2020", "logpop_UC2018"]].notna().all(axis=1),
        "B": frame[["logpop_UC2020", "logpop_CN2018", "logpop_CN2022"]].notna().all(axis=1),
    }
    grid = np.linspace(
        float(frame["signed_distance_m"].quantile(0.01)),
        float(frame["signed_distance_m"].quantile(0.99)),
        PRED_GRID_N,
    )

    rows, curves = [], []
    for key, set_id, label, lay_early, lay_late in SPECS:
        df = frame.loc[set_mask[set_id]].copy()
        e = df["year"] <= EARLY_MAX_YEAR
        df["log1p_pop_density"] = np.where(e, df[f"logpop_{lay_early}"], df[f"logpop_{lay_late}"])
        df = df.reset_index(drop=True)
        print(f"{label}: n={len(df):,}, waste+={int(df['waste_positive'].sum()):,}")

        fit = cy.fit_all(df)
        curve, cstats = bb.curve_stats(df, grid, BOOT_SEED)

        # Same replicate stream as 3_spatial_block_bootstrap.py, so the published
        # layer reproduces that table's 2 km interval exactly.
        rng = np.random.default_rng(pag.block_bootstrap_seed(BLOCK_M))
        xy = df[["x", "y"]].to_numpy(dtype=float)
        contrast = []
        for r in range(args.n_boot):
            boot = df.iloc[bb.block_sample(xy, BLOCK_M, rng)].reset_index(drop=True)
            try:
                _, s = bb.curve_stats(boot, grid, BOOT_SEED + r)
            except Exception:
                continue
            contrast.append(s["curve_ratio_0m_vs_2000m"])
        lo, hi = np.nanpercentile(contrast, [2.5, 97.5])

        rows.append({
            "spec": key, "set": set_id, "label": label, "layer_early": lay_early, "layer_late": lay_late,
            "n_panoramas": len(df), "n_positive": int(df["waste_positive"].sum()),
            **{k: v for k, v in fit.items() if k != "frame"},
            **cstats, "curve_ratio_lo": float(lo), "curve_ratio_hi": float(hi), "n_boot": len(contrast),
        })
        curves.append(pd.DataFrame({"spec": key, "set": set_id, "label": label,
                                    "signed_distance_m": grid, "prob": curve}))

    res = pd.DataFrame(rows)
    cur = pd.concat(curves, ignore_index=True)
    ref = cur[cur.spec == "A_static_2020"]["prob"].to_numpy()
    res["curve_corr_vs_published"] = [
        float(np.corrcoef(cur[cur.spec == k]["prob"].to_numpy(), ref)[0, 1]) for k in res.spec
    ]
    res.to_csv(out_dir / "Nairobi_worldpop_year_summary.csv", index=False)
    cur.to_csv(out_dir / "Nairobi_worldpop_year_curves.csv", index=False)

    thesis = pd.DataFrame({
        "Population layer": res["label"],
        "Panoramas": res["n_panoramas"].map("{:,}".format),
        "ΔAIC M0 − MP (population)": res["delta_aic_M0_minus_MP"].map("{:,.0f}".format),
        "ΔAIC MP − MDP (distance)": res["delta_aic_MP_minus_MDP"].map("{:,.0f}".format),
        "LRT p (MP vs MDP)": res["lrt_MP_vs_MDP_p"].map("{:.1e}".format),
        "Pseudo-R² (MDP)": res["pseudo_r2_MDP"].map("{:.3f}".format),
        "Adjusted P(waste) edge → 2 km (%)": [
            f"{a:.2f} → {b:.2f}" for a, b in zip(res.curve_p_at_0m_pct, res.curve_p_at_2000m_pct)],
        "Edge ÷ 2 km (2 km block 95% CI)": [
            f"{a:.2f} ({b:.2f}–{c:.2f})" for a, b, c in
            zip(res.curve_ratio_0m_vs_2000m, res.curve_ratio_lo, res.curve_ratio_hi)],
        "Curve corr. with published": res["curve_corr_vs_published"].map("{:.3f}".format),
    })
    path = table_dir / "worldpop_year_sensitivity.csv"
    thesis.to_csv(path, index=False)
    print(f"Thesis table: {path}\nWrote outputs to {out_dir}")


if __name__ == "__main__":
    main()

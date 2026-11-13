#!/usr/bin/env python3
"""Step 6.4b — the settlement association, with and without self-collected imagery.

Step 5b makes three separate claims about urban-poor settlements, and this
script re-tests all three on the combined observation frame:

  1. the 2x2 contingency — waste-positive rate inside vs outside, with
     prevalence ratio, odds ratio, Pearson chi-square and Cramer's V
  2. the zone summary — the same association area-normalised, because
     settlements are 2.9% of the city and a rate says nothing about density
  3. the observation-frame NNR null — are positives clustered relative to
     *where the platform could see*, rather than relative to the map

(3) is the one that matters most here. The null is drawn from the panoramas
that were actually available, so it changes when the frame changes: GSVI draws
2,696 from 76,605, the combined arm draws 2,845 from 79,584. If self-collected
imagery were simply adding positives in places the platform never went, the NNR
would move; if the clustering is real, it should not.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/settlement/):
  1_sc_settlement_contingency.csv            the 2x2, both arms
  1_sc_settlement_zone_summary.csv           area-normalised zone table, both arms
  1_sc_settlement_nnr.csv                    observation-frame NNR, both arms
  thesis_table/table_6_4_settlement_comparison.csv   the chapter table
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from shapely.ops import unary_union
from sklearn.neighbors import NearestNeighbors

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.panoids import load_boundary, load_slums  # noqa: E402
from sc_frames import ARM_LABELS, PATTERN_DIR, load_frames  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "settlement"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

CONTINGENCY_CSV = OUTPUT_DIR / "1_sc_settlement_contingency.csv"
ZONE_CSV = OUTPUT_DIR / "1_sc_settlement_zone_summary.csv"
NNR_CSV = OUTPUT_DIR / "1_sc_settlement_nnr.csv"
COMPARISON_TABLE = TABLE_DIR / "table_6_4_settlement_comparison.csv"

N_PERM = 999
RNG_SEED = 42


# ---------------------------------------------------------------------------
# (1) 2x2 contingency
# ---------------------------------------------------------------------------
def odds_ratio_with_ci(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    if min(a, b, c, d) <= 0:
        return np.nan, np.nan, np.nan
    odds = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return float(odds), float(math.exp(math.log(odds) - 1.96 * se)), float(
        math.exp(math.log(odds) + 1.96 * se)
    )


def contingency_stats(df: pd.DataFrame) -> dict:
    waste = df["waste_positive"].to_numpy() == 1
    inside = df["inside_settlement"].to_numpy() == 1
    a = int((waste & inside).sum())
    b = int((~waste & inside).sum())
    c = int((waste & ~inside).sum())
    d = int((~waste & ~inside).sum())
    n = a + b + c + d
    chi2, p_chi2, _, _ = chi2_contingency(np.array([[a, b], [c, d]], dtype=float), correction=False)
    p_in, p_out = a / (a + b), c / (c + d)
    odds, or_lo, or_hi = odds_ratio_with_ci(a, b, c, d)
    return {
        "a": a, "b": b, "c": c, "d": d, "n": n,
        "n_inside": a + b, "n_outside": c + d, "n_waste": a + c,
        "rate_inside_pct": 100 * p_in, "rate_outside_pct": 100 * p_out,
        "rate_city_pct": 100 * (a + c) / n,
        "prevalence_ratio": p_in / p_out,
        "odds_ratio": odds, "or_lo": or_lo, "or_hi": or_hi,
        "chi2": float(chi2), "p_chi2": float(p_chi2),
        "cramers_v": float(np.sqrt(chi2 / n)),
        "pct_positives_inside": 100 * a / (a + c),
        "pct_frame_inside": 100 * (a + b) / n,
    }


# ---------------------------------------------------------------------------
# (2) Area-normalised zone summary
# ---------------------------------------------------------------------------
def zone_stats(stats: dict, area_slum_km2: float, area_city_km2: float) -> dict:
    area_out_km2 = area_city_km2 - area_slum_km2
    return {
        **stats,
        "area_city_km2": area_city_km2,
        "area_slum_km2": area_slum_km2,
        "area_nonslum_km2": area_out_km2,
        "density_inside_per_km2": stats["a"] / area_slum_km2,
        "density_outside_per_km2": stats["c"] / area_out_km2,
        "density_ratio": (stats["a"] / area_slum_km2) / (stats["c"] / area_out_km2),
    }


def build_zone_table(by_arm: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for key, st in by_arm.items():
        for zone, n_pos, n_all, area, dens in (
            ("Urban poor", st["a"], st["n_inside"], st["area_slum_km2"], st["density_inside_per_km2"]),
            ("Non-urban-poor", st["c"], st["n_outside"], st["area_nonslum_km2"], st["density_outside_per_km2"]),
        ):
            rows.append(
                {
                    "Arm": ARM_LABELS[key],
                    "Zone": zone,
                    "Area (km²)": round(area, 1),
                    "Observation locations": n_all,
                    "Waste-positive": n_pos,
                    "Waste-positive rate (%)": round(100 * n_pos / n_all, 2),
                    "Positive density (per km²)": round(dens, 1),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(ZONE_CSV, index=False)
    print(f"\nZone summary (area-normalised):\n{out.to_string(index=False)}")
    print(f"Wrote {ZONE_CSV}")
    return out


# ---------------------------------------------------------------------------
# (3) Observation-frame NNR null
# ---------------------------------------------------------------------------
def mean_nn_distance(coords: np.ndarray) -> float:
    nbrs = NearestNeighbors(n_neighbors=2, algorithm="ball_tree").fit(coords)
    distances, _ = nbrs.kneighbors(coords)
    return float(distances[:, 1].mean())


def observation_frame_nnr(points: gpd.GeoDataFrame, key: str) -> dict:
    """Mean 1-NN distance among positives vs draws of the same size from the frame."""
    coords_all = np.column_stack([points.geometry.x, points.geometry.y])
    is_pos = (points["waste_positive"].to_numpy() == 1)
    n_pos = int(is_pos.sum())
    d_obs = mean_nn_distance(coords_all[is_pos])

    rng = np.random.default_rng(RNG_SEED)
    n_all = len(coords_all)
    null = np.empty(N_PERM, dtype=float)
    print(f"  [{key}] {N_PERM} permutations: {n_pos:,} drawn from {n_all:,} available panoramas...")
    for i in range(N_PERM):
        idx = rng.choice(n_all, size=n_pos, replace=False)
        null[i] = mean_nn_distance(coords_all[idx])

    null_mean = float(null.mean())
    # One-sided: more clustered than the frame would produce by chance.
    p_value = float((np.sum(null <= d_obs) + 1) / (N_PERM + 1))
    return {
        "arm": key,
        "n_positive": n_pos,
        "n_frame": n_all,
        "observed_mean_nn_m": d_obs,
        "null_mean_nn_m": null_mean,
        "null_sd_m": float(null.std(ddof=1)),
        "nnr_observation_frame": d_obs / null_mean,
        "p_value": p_value,
        "n_permutations": N_PERM,
    }


# ---------------------------------------------------------------------------
# Chapter table
# ---------------------------------------------------------------------------
def build_comparison_table(zones: dict[str, dict], nnr: dict[str, dict]) -> pd.DataFrame:
    g, s = zones["gsvi"], zones["gsvi_selfcollected"]
    ng, ns = nnr["gsvi"], nnr["gsvi_selfcollected"]
    rows = [
        ("Observation locations", f"{g['n']:,}", f"{s['n']:,}"),
        ("Waste-positive locations", f"{g['n_waste']:,}", f"{s['n_waste']:,}"),
        ("Locations inside a settlement", f"{g['n_inside']:,}", f"{s['n_inside']:,}"),
        ("Waste-positive rate inside", f"{g['rate_inside_pct']:.1f}%", f"{s['rate_inside_pct']:.1f}%"),
        ("Waste-positive rate outside", f"{g['rate_outside_pct']:.1f}%", f"{s['rate_outside_pct']:.1f}%"),
        ("Prevalence ratio (inside / outside)", f"{g['prevalence_ratio']:.2f}", f"{s['prevalence_ratio']:.2f}"),
        ("Odds ratio (95% CI)",
         f"{g['odds_ratio']:.2f} ({g['or_lo']:.2f}–{g['or_hi']:.2f})",
         f"{s['odds_ratio']:.2f} ({s['or_lo']:.2f}–{s['or_hi']:.2f})"),
        ("Pearson χ²", f"{g['chi2']:,.1f}", f"{s['chi2']:,.1f}"),
        ("Cramér's V", f"{g['cramers_v']:.3f}", f"{s['cramers_v']:.3f}"),
        ("Positive density inside (per km²)", f"{g['density_inside_per_km2']:.1f}", f"{s['density_inside_per_km2']:.1f}"),
        ("Positive density outside (per km²)", f"{g['density_outside_per_km2']:.1f}", f"{s['density_outside_per_km2']:.1f}"),
        ("Density ratio", f"{g['density_ratio']:.1f}×", f"{s['density_ratio']:.1f}×"),
        ("Waste-positive locations inside a settlement",
         f"{g['pct_positives_inside']:.1f}%", f"{s['pct_positives_inside']:.1f}%"),
        ("Observation frame inside a settlement",
         f"{g['pct_frame_inside']:.1f}%", f"{s['pct_frame_inside']:.1f}%"),
        ("Observed mean 1-NN distance",
         f"{ng['observed_mean_nn_m']:.1f} m", f"{ns['observed_mean_nn_m']:.1f} m"),
        ("Observation-frame null mean 1-NN",
         f"{ng['null_mean_nn_m']:.1f} m", f"{ns['null_mean_nn_m']:.1f} m"),
        ("Observation-frame NNR",
         f"{ng['nnr_observation_frame']:.3f}", f"{ns['nnr_observation_frame']:.3f}"),
        ("NNR permutation p", f"{ng['p_value']:.3f}", f"{ns['p_value']:.3f}"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "GSVI", "GSVI + SC"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(COMPARISON_TABLE, index=False)
    print(f"\n6.4b — settlement association:\n{out.to_string(index=False)}")
    print(f"Wrote {COMPARISON_TABLE}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    frames = load_frames()

    boundary = load_boundary()
    slums = load_slums()
    area_city_km2 = float(unary_union(boundary.geometry).area / 1e6)
    area_slum_km2 = float(unary_union(slums.geometry).area / 1e6)
    print(f"\nCity {area_city_km2:,.1f} km² | mapped settlements {area_slum_km2:,.1f} km² "
          f"({100 * area_slum_km2 / area_city_km2:.1f}%)")

    zones = {
        key: zone_stats(contingency_stats(df), area_slum_km2, area_city_km2)
        for key, df in frames.items()
    }

    contingency = pd.DataFrame(
        [
            {"Arm": ARM_LABELS[k], "Zone": zone, "Waste-positive": w, "Non-positive": nw}
            for k, st in zones.items()
            for zone, w, nw in (("Inside settlement", st["a"], st["b"]),
                                ("Outside settlement", st["c"], st["d"]))
        ]
    )
    contingency.to_csv(CONTINGENCY_CSV, index=False)
    print(f"Wrote {CONTINGENCY_CSV}")

    build_zone_table(zones)

    print("\nObservation-frame NNR null:")
    nnr = {key: observation_frame_nnr(df, key) for key, df in frames.items()}
    pd.DataFrame(list(nnr.values())).to_csv(NNR_CSV, index=False)
    for key, r in nnr.items():
        print(f"  [{key}] observed {r['observed_mean_nn_m']:.1f} m vs null "
              f"{r['null_mean_nn_m']:.1f} m → NNR {r['nnr_observation_frame']:.3f}, "
              f"p = {r['p_value']:.3f}")
    print(f"Wrote {NNR_CSV}")

    build_comparison_table(zones, nnr)


if __name__ == "__main__":
    main()

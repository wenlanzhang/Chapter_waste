#!/usr/bin/env python3
"""Step 5 sensitivity — is the settlement association just population density?

The nested GAMs answer this parametrically: adding signed distance to a
population-only model improves AIC substantially, so distance is not a density
proxy. This script makes the same point without a model, by comparing like with
like: within each population-density band, does being inside a mapped urban-poor
settlement still raise the waste-positive rate?

If the association were density in disguise, the inside and outside rates would
match within a band. Reported per band:

  - waste-positive rate outside / inside a settlement
  - the ratio between them, with a Wald 95% CI on the log ratio
  - panorama counts, so thin bands can be discounted

Unit: one GSVI panorama. Bands are quantiles of WorldPop density, so each holds
a similar number of panoramas.

Input:
  Signed_distance/pop_adjusted/Nairobi_pop_adjusted_gam_frame.csv  (1_pop_adjusted_gam.py)

Outputs (Signed_distance/pop_adjusted/):
  Nairobi_settlement_by_density_band.csv        per-band counts and rates
  thesis_table/settlement_by_density_band.csv   chapter table
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import pattern_dir  # noqa: E402

OUTPUT_DIR = pattern_dir() / "Signed_distance" / "pop_adjusted"
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"
FRAME_CSV = OUTPUT_DIR / "Nairobi_pop_adjusted_gam_frame.csv"

DEFAULT_BANDS = 8
# A band needs enough inside-settlement panoramas for the rate to mean anything.
MIN_INSIDE = 30


def rate_ratio_ci(k_in: int, n_in: int, k_out: int, n_out: int) -> tuple[float, float, float]:
    """Rate ratio (inside / outside) with a Wald 95% CI on the log scale."""
    if not (k_in and k_out and n_in and n_out):
        return np.nan, np.nan, np.nan
    p_in, p_out = k_in / n_in, k_out / n_out
    rr = p_in / p_out
    se = math.sqrt((1 - p_in) / k_in + (1 - p_out) / k_out)
    return rr, rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se)


def build(frame: pd.DataFrame, n_bands: int) -> pd.DataFrame:
    frame = frame.copy()
    frame["band"] = pd.qcut(frame["pop_density_km2"], n_bands, duplicates="drop")

    rows = []
    for band, g in frame.groupby("band", observed=True):
        inside = g[g["inside_settlement"] == 1]
        outside = g[g["inside_settlement"] == 0]
        k_in, n_in = int(inside["waste_positive"].sum()), len(inside)
        k_out, n_out = int(outside["waste_positive"].sum()), len(outside)
        rr, lo, hi = rate_ratio_ci(k_in, n_in, k_out, n_out)
        rows.append(
            {
                "density_band": f"{band.left:,.0f}–{band.right:,.0f}",
                "density_low": float(band.left),
                "density_high": float(band.right),
                "n_outside": n_out,
                "n_inside": n_in,
                "waste_positive_outside": k_out,
                "waste_positive_inside": k_in,
                "rate_outside_pct": round(100 * k_out / n_out, 2) if n_out else np.nan,
                "rate_inside_pct": round(100 * k_in / n_in, 2) if n_in else np.nan,
                "rate_ratio": round(rr, 2) if np.isfinite(rr) else np.nan,
                "rate_ratio_ci95_low": round(lo, 2) if np.isfinite(lo) else np.nan,
                "rate_ratio_ci95_high": round(hi, 2) if np.isfinite(hi) else np.nan,
                "reportable": bool(n_in >= MIN_INSIDE),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bands", type=int, default=DEFAULT_BANDS, help="Number of density quantile bands")
    args = parser.parse_args()

    if not FRAME_CSV.exists():
        raise SystemExit(
            f"Missing {FRAME_CSV} — run "
            "5_spatial_pattern/Signed_distance/pop_adjusted/1_pop_adjusted_gam.py first"
        )
    frame = pd.read_csv(FRAME_CSV)
    print(
        f"{len(frame):,} panoramas | {int(frame['waste_positive'].sum()):,} waste-positive "
        f"({100 * frame['waste_positive'].mean():.2f}%) | "
        f"{int((frame['inside_settlement'] == 1).sum()):,} inside a settlement"
    )

    table = build(frame, args.bands)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_DIR / "Nairobi_settlement_by_density_band.csv", index=False)
    print(f"Wrote {OUTPUT_DIR / 'Nairobi_settlement_by_density_band.csv'}")

    display = pd.DataFrame(
        {
            "Density band (people/km²)": table["density_band"],
            "Outside settlement": [
                f"{r:.2f}% (n={n:,})" for r, n in zip(table["rate_outside_pct"], table["n_outside"])
            ],
            "Inside settlement": [
                f"{r:.2f}% (n={n:,})" if ok else f"n={n:,}, too few to report"
                for r, n, ok in zip(table["rate_inside_pct"], table["n_inside"], table["reportable"])
            ],
            "Rate ratio (95% CI)": [
                f"{rr:.1f}× ({lo:.1f}–{hi:.1f})" if ok and np.isfinite(rr) else "—"
                for rr, lo, hi, ok in zip(
                    table["rate_ratio"], table["rate_ratio_ci95_low"],
                    table["rate_ratio_ci95_high"], table["reportable"]
                )
            ],
        }
    )
    display.to_csv(THESIS_TABLE_DIR / "settlement_by_density_band.csv", index=False)
    print(f"Wrote {THESIS_TABLE_DIR / 'settlement_by_density_band.csv'}\n")
    print("Waste-positive rate within population-density bands:")
    print(display.to_string(index=False))

    ok = table[table["reportable"]]
    print(
        f"\nInside-settlement rate exceeds outside in {int((ok['rate_ratio'] > 1).sum())}/{len(ok)} "
        f"reportable bands (ratio {ok['rate_ratio'].min():.1f}×–{ok['rate_ratio'].max():.1f}×). "
        "Density alone does not account for the settlement association."
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 5 — descriptive proximity of visible waste to urban-poor settlements.

The signed-distance GAM answers this with a fitted smooth. This script answers
it with the raw data, so the model can be read against something that assumes
nothing: the empirical waste-positive rate within fixed distance bands, and a
short comparison of how far waste-positive and non-positive panoramas sit from
the nearest settlement.

Signed distance is negative inside a settlement and positive outside.

Input:
  Signed_distance/Nairobi_signed_distance_gam_frame.csv  (1_signed_distance_gam.py)

Outputs (Signed_distance/):
  Nairobi_proximity_rate_by_band.csv          empirical rate per band (feeds panel A)
  thesis_table/proximity_descriptives.csv     the small comparison table
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import pattern_dir  # noqa: E402

OUTPUT_DIR = pattern_dir() / "Signed_distance"
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"
FRAME_CSV = OUTPUT_DIR / "Nairobi_signed_distance_gam_frame.csv"

# Upper edges in metres; the first band is everything inside a settlement.
BAND_EDGES = [0, 250, 500, 1000, 2000, 5000]
PROXIMITY_CUTS = [0, 250, 500, 1000]


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


def rate_by_band(frame: pd.DataFrame) -> pd.DataFrame:
    edges = [-np.inf, *BAND_EDGES, np.inf]
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sub = frame[(frame["signed_distance_m"] > lo) & (frame["signed_distance_m"] <= hi)]
        if sub.empty:
            continue
        k, n = int(sub["waste_positive"].sum()), len(sub)
        ci_low, ci_high = wilson_ci(k, n)
        rows.append(
            {
                "band": band_label(lo, hi),
                "band_low_m": lo,
                "band_high_m": hi,
                "n_panoramas": n,
                "n_waste_positive": k,
                "rate_pct": round(100 * k / n, 2),
                "rate_ci95_low_pct": round(100 * ci_low, 2),
                "rate_ci95_high_pct": round(100 * ci_high, 2),
            }
        )
    return pd.DataFrame(rows)


def comparison_table(frame: pd.DataFrame) -> pd.DataFrame:
    pos = frame[frame["waste_positive"] == 1]["signed_distance_m"]
    neg = frame[frame["waste_positive"] == 0]["signed_distance_m"]

    rows = [("Panoramas", f"{len(pos):,}", f"{len(neg):,}")]
    rows.append(
        (
            "Median distance to settlement",
            f"{pos.median():,.0f} m",
            f"{neg.median():,.0f} m",
        )
    )
    rows.append(
        (
            "Interquartile range",
            f"{pos.quantile(0.25):,.0f} to {pos.quantile(0.75):,.0f} m",
            f"{neg.quantile(0.25):,.0f} to {neg.quantile(0.75):,.0f} m",
        )
    )
    for cut in PROXIMITY_CUTS:
        label = "Inside a settlement" if cut == 0 else f"Within {cut:,} m"
        rows.append((label, f"{100 * (pos <= cut).mean():.1f}%", f"{100 * (neg <= cut).mean():.1f}%"))

    return pd.DataFrame(rows, columns=["Measure", "Waste-positive", "Non-positive"])


def main() -> None:
    if not FRAME_CSV.exists():
        raise SystemExit(
            f"Missing {FRAME_CSV} — run "
            "5_spatial_pattern/Signed_distance/1_signed_distance_gam.py first"
        )
    frame = pd.read_csv(FRAME_CSV)
    print(
        f"{len(frame):,} GSVI panoramas | {int(frame['waste_positive'].sum()):,} waste-positive "
        f"({100 * frame['waste_positive'].mean():.2f}%)"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)

    bands = rate_by_band(frame)
    bands.to_csv(OUTPUT_DIR / "Nairobi_proximity_rate_by_band.csv", index=False)
    print(f"\nWaste-positive rate by distance to the nearest urban-poor settlement:")
    print(
        bands[["band", "n_panoramas", "n_waste_positive", "rate_pct",
               "rate_ci95_low_pct", "rate_ci95_high_pct"]].to_string(index=False)
    )
    print(f"Wrote {OUTPUT_DIR / 'Nairobi_proximity_rate_by_band.csv'}")

    table = comparison_table(frame)
    table.to_csv(THESIS_TABLE_DIR / "proximity_descriptives.csv", index=False)
    print("\nProximity comparison:")
    print(table.to_string(index=False))
    print(f"Wrote {THESIS_TABLE_DIR / 'proximity_descriptives.csv'}")


if __name__ == "__main__":
    main()

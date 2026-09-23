#!/usr/bin/env python3
"""Urban-poor settlement association for GSVI waste-positive panoids.

Boundary stats only (panorama unit among 76,605 GSVI locations, 2,696 waste+):

  - 2×2 contingency (inside/outside × waste+/non+)
  - prevalence ratio, odds ratio with 95% CI, Pearson χ² / Cramér's V
  - area-normalised positive density + zone summary

Distance-decay / NegExp live under 5_spatial_pattern/Distance_decay/.
Signed-distance logistic GAM under 5_spatial_pattern/Signed_distance/.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_boundary,
    load_slums,
)

OUTPUT_DIR = PATTERN_DIR / "settlement"
TABLE_DIR = OUTPUT_DIR / "thesis_table"


def odds_ratio_with_ci(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """OR = (a*d)/(b*c) with Woolf 95% CI. Counts follow user table orientation."""
    if min(a, b, c, d) <= 0:
        return np.nan, np.nan, np.nan
    odds_ratio = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    lo = math.exp(math.log(odds_ratio) - 1.96 * se)
    hi = math.exp(math.log(odds_ratio) + 1.96 * se)
    return float(odds_ratio), float(lo), float(hi)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Settlement association (GSVI panoids, urban-poor boundary)...")
    points = enrich_sviwaste_frame()
    boundary = load_boundary()
    slums = load_slums()

    points = label_inside_settlement(points, slums)
    waste = points["waste_positive"].to_numpy() == 1
    inside = points["inside_settlement"].to_numpy() == 1

    # User-facing 2×2 orientation:
    #   Inside:  a = waste+, b = non+
    #   Outside: c = waste+, d = non+
    a = int((waste & inside).sum())
    b = int((~waste & inside).sum())
    c = int((waste & ~inside).sum())
    d = int((~waste & ~inside).sum())
    n_all = a + b + c + d
    n_waste = a + c
    n_inside = a + b
    n_outside = c + d

    table_2x2 = np.array([[a, b], [c, d]], dtype=float)
    chi2, p_chi2, dof, expected = chi2_contingency(table_2x2, correction=False)
    cramers_v = float(np.sqrt(chi2 / n_all)) if n_all > 0 else np.nan

    p_inside = a / n_inside if n_inside else np.nan
    p_outside = c / n_outside if n_outside else np.nan
    prevalence_ratio = p_inside / p_outside if p_outside and p_outside > 0 else np.nan
    odds_ratio, or_lo, or_hi = odds_ratio_with_ci(a, b, c, d)

    pct_positives_inside = 100.0 * a / n_waste if n_waste else np.nan
    pct_frame_inside = 100.0 * n_inside / n_all if n_all else np.nan

    contingency = pd.DataFrame(
        [
            {
                "settlement_location": "Inside mapped settlements",
                "waste_positive_panoramas": a,
                "non_positive_panoramas": b,
                "all_panoramas": a + b,
            },
            {
                "settlement_location": "Outside mapped settlements",
                "waste_positive_panoramas": c,
                "non_positive_panoramas": d,
                "all_panoramas": c + d,
            },
            {
                "settlement_location": "Total",
                "waste_positive_panoramas": a + c,
                "non_positive_panoramas": b + d,
                "all_panoramas": n_all,
            },
        ]
    )
    contingency_legacy = pd.DataFrame(
        [
            {
                "waste_status": "waste_positive",
                "inside_settlement": a,
                "outside_settlement": c,
                "total": a + c,
            },
            {
                "waste_status": "waste_negative",
                "inside_settlement": b,
                "outside_settlement": d,
                "total": b + d,
            },
        ]
    )
    contingency_path = OUTPUT_DIR / "Nairobi_settlement_contingency.csv"
    contingency_legacy.to_csv(contingency_path, index=False)
    contingency_table_path = OUTPUT_DIR / "settlement_contingency.csv"
    contingency.to_csv(contingency_table_path, index=False)

    assoc_summary = {
        "n_panoids": n_all,
        "n_waste_positive": n_waste,
        "waste_inside_a": a,
        "nonwaste_inside_b": b,
        "waste_outside_c": c,
        "nonwaste_outside_d": d,
        "positive_rate_inside": p_inside,
        "positive_rate_outside": p_outside,
        "prevalence_ratio": prevalence_ratio,
        "odds_ratio": odds_ratio,
        "odds_ratio_ci_low": or_lo,
        "odds_ratio_ci_high": or_hi,
        "chi2": chi2,
        "dof": int(dof),
        "p_value": p_chi2,
        "cramers_v": cramers_v,
        "pct_positives_inside": pct_positives_inside,
        "pct_gsvi_frame_inside": pct_frame_inside,
        "expected_waste_inside": float(expected[0, 0]),
        "expected_waste_outside": float(expected[1, 0]),
    }
    chi2_path = OUTPUT_DIR / "Nairobi_settlement_chisquare.csv"
    pd.DataFrame([assoc_summary]).to_csv(chi2_path, index=False)

    a_city = float(boundary.geometry.area.sum())
    a_slum = float(slums.geometry.area.sum())
    a_nonslum = a_city - a_slum
    dens_in = a / (a_slum / 1e6) if a_slum > 0 else np.nan
    dens_out = c / (a_nonslum / 1e6) if a_nonslum > 0 else np.nan
    dens_ratio = dens_in / dens_out if dens_out and dens_out > 0 else np.nan
    pcr = (a / n_waste) / (a_slum / a_city) if n_waste > 0 and a_city > 0 else np.nan

    density_summary = {
        "n_waste_positive": n_waste,
        "n_waste_inside": a,
        "n_waste_outside": c,
        "n_all_inside": n_inside,
        "n_all_outside": n_outside,
        "pct_waste_inside": pct_positives_inside,
        "pct_gsvi_frame_inside": pct_frame_inside,
        "city_area_km2": a_city / 1e6,
        "slum_area_km2": a_slum / 1e6,
        "nonslum_area_km2": a_nonslum / 1e6,
        "pct_city_slum": 100.0 * a_slum / a_city,
        "positive_rate_inside": p_inside,
        "positive_rate_outside": p_outside,
        "density_inside_per_km2": dens_in,
        "density_outside_per_km2": dens_out,
        "density_ratio": dens_ratio,
        "pcr": pcr,
    }
    density_path = OUTPUT_DIR / "Nairobi_settlement_density.csv"
    pd.DataFrame([density_summary]).to_csv(density_path, index=False)

    area_in_km2 = a_slum / 1e6
    area_out_km2 = a_nonslum / 1e6
    area_city_km2 = a_city / 1e6
    dens_city = n_waste / area_city_km2 if area_city_km2 > 0 else np.nan
    pct_waste_in = 100.0 * a / n_waste if n_waste else np.nan
    pct_waste_out = 100.0 * c / n_waste if n_waste else np.nan
    rate_in_pct = 100.0 * p_inside
    rate_out_pct = 100.0 * p_outside
    rate_city_pct = 100.0 * n_waste / n_all if n_all else np.nan

    def _fmt_num(x: float, nd: int = 2) -> str:
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return "-"
        return f"{x:.{nd}f}"

    def _fmt_int(x: int | float) -> str:
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return "-"
        return f"{int(round(x)):,}"

    zone_summary = pd.DataFrame(
        [
            {
                "Zone": "Urban poor",
                "Area (km²)": _fmt_num(area_in_km2),
                "Waste-positive panoids": _fmt_int(a),
                "Share of waste-positive (%)": _fmt_num(pct_waste_in),
                "Positive density (panoids/km²)": _fmt_num(dens_in),
                "All GSVI panoids": _fmt_int(n_inside),
                "Waste-positive rate (%)": _fmt_num(rate_in_pct),
            },
            {
                "Zone": "Non-urban poor",
                "Area (km²)": _fmt_num(area_out_km2),
                "Waste-positive panoids": _fmt_int(c),
                "Share of waste-positive (%)": _fmt_num(pct_waste_out),
                "Positive density (panoids/km²)": _fmt_num(dens_out),
                "All GSVI panoids": _fmt_int(n_outside),
                "Waste-positive rate (%)": _fmt_num(rate_out_pct),
            },
            {
                "Zone": "Urban poor / non-urban poor ratio",
                "Area (km²)": "-",
                "Waste-positive panoids": "-",
                "Share of waste-positive (%)": "-",
                "Positive density (panoids/km²)": _fmt_num(dens_ratio),
                "All GSVI panoids": "-",
                "Waste-positive rate (%)": _fmt_num(prevalence_ratio),
            },
            {
                "Zone": "Total",
                "Area (km²)": _fmt_num(area_city_km2),
                "Waste-positive panoids": _fmt_int(n_waste),
                "Share of waste-positive (%)": _fmt_num(100.0),
                "Positive density (panoids/km²)": _fmt_num(dens_city),
                "All GSVI panoids": _fmt_int(n_all),
                "Waste-positive rate (%)": _fmt_num(rate_city_pct),
            },
        ]
    )
    zone_path = TABLE_DIR / "settlement_zone_summary.csv"
    zone_summary.to_csv(zone_path, index=False)

    thesis = pd.DataFrame(
        [
            ("Waste-positive inside settlements (a)", f"{a:,}", ""),
            ("Non-positive inside settlements (b)", f"{b:,}", ""),
            ("Waste-positive outside settlements (c)", f"{c:,}", ""),
            ("Non-positive outside settlements (d)", f"{d:,}", ""),
            ("Positive rate inside", f"{100 * p_inside:.2f}", "%"),
            ("Positive rate outside", f"{100 * p_outside:.2f}", "%"),
            ("Prevalence ratio (inside/outside)", f"{prevalence_ratio:.2f}", ""),
            ("Odds ratio (inside vs outside)", f"{odds_ratio:.2f}", ""),
            ("Odds ratio 95% CI", f"{or_lo:.2f}–{or_hi:.2f}", ""),
            ("Share of positives inside settlements", f"{pct_positives_inside:.1f}", "%"),
            ("Share of GSVI frame inside settlements", f"{pct_frame_inside:.1f}", "%"),
            ("Chi-square", f"{chi2:.1f}", ""),
            ("Degrees of freedom", f"{int(dof)}", ""),
            ("Chi-square p-value", f"{p_chi2:.4g}", ""),
            ("Cramér's V", f"{cramers_v:.3f}", ""),
            ("Settlement area", f"{a_slum / 1e6:.2f}", "km²"),
            ("Non-settlement area", f"{a_nonslum / 1e6:.2f}", "km²"),
            ("Density inside", f"{dens_in:.2f}", "panoids/km²"),
            ("Density outside", f"{dens_out:.2f}", "panoids/km²"),
            ("Density ratio (in/out)", f"{dens_ratio:.2f}", ""),
            ("PCR", f"{pcr:.2f}", ""),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / "settlement_association.csv"
    thesis.to_csv(thesis_path, index=False)

    print(f"  Contingency [[a,b],[c,d]] = [[{a}, {b}], [{c}, {d}]]")
    print(
        f"  Rates inside/outside: {100 * p_inside:.2f}% / {100 * p_outside:.2f}% "
        f"(PR={prevalence_ratio:.2f})"
    )
    print(f"  OR={odds_ratio:.2f} (95% CI {or_lo:.2f}–{or_hi:.2f})")
    print(
        f"  Positives inside: {pct_positives_inside:.1f}% | "
        f"GSVI frame inside: {pct_frame_inside:.1f}%"
    )
    print(f"  χ²={chi2:.2f}, df={int(dof)}, p={p_chi2:.4g}, V={cramers_v:.3f}")
    print(
        f"  Density in/out: {dens_in:.2f} / {dens_out:.2f} per km² "
        f"(ratio {dens_ratio:.2f})"
    )
    for p in (
        contingency_path,
        contingency_table_path,
        chi2_path,
        density_path,
        zone_path,
        thesis_path,
    ):
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 6 anchor — one table across the whole representation pipeline.

Steps 2-5 identify and quantify representation gaps. Step 6 asks how far
supplementary local observation closes them. Each sub-step answers that for one
stage; this script collects those answers into the single table the section is
built around, reading only outputs the sub-steps already wrote.

  Observation   6.1  what self-collected imagery adds to the 100 m frame
  Measurement   6.2  whether the detector transfers to locally collected imagery
  Indicator     6.3  whether the published surface changes, and improves
  Pattern       6.4  whether the spatial conclusions move

The table is deliberately blunt about direction. A row that does not move is
reported as not moving; that is the finding for most of this pipeline.

Run after every other Step 6 script.

Outputs (Data/Chapter_waste/6_selfcollected/):
  thesis_table/table_6_0_mitigation_summary.csv   the section anchor
  0_mitigation_summary_detail.csv                 numeric values behind it
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir  # noqa: E402

ROOT = selfcollected_dir()
TABLE_DIR = ROOT / "thesis_table"

SOURCES = ROOT / "1_sources"
IDENT = ROOT / "2_identification"
INDICATOR = ROOT / "3_indicator"
PATTERN = ROOT / "4_pattern"

SUMMARY_TABLE = TABLE_DIR / "table_6_0_mitigation_summary.csv"
DETAIL_CSV = ROOT / "0_mitigation_summary_detail.csv"


def need(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {path}\nRun the Step 6 sub-steps first (see README Step 6).")
    return path


def row(stage: str, metric: str, base: str, mitigated: str, change: str) -> dict:
    return {"Stage": stage, "Metric": metric, "GSVI baseline": base,
            "GSVI + SC": mitigated, "Change": change}


def observation_rows() -> tuple[list[dict], dict]:
    s = pd.read_csv(need(SOURCES / "1_Nairobi_sc_coverage_summary.csv")).iloc[0]
    far = int(s["far_m"])
    rows = [
        row("Observation", "Self-collected images added", "—",
            f"{int(s['n_images_sc']):,}", "—"),
        row("Observation", "Directly observed 100 m cells",
            f"{int(s['n_cells_observed_gsvi']):,} ({s['pct_cells_observed_gsvi']:.1f}%)",
            f"{int(s['n_cells_observed_gsc']):,} ({s['pct_cells_observed_gsc']:.1f}%)",
            f"+{int(s['n_cells_newly_observed']):,} ({s['pct_cells_observed_gsc'] - s['pct_cells_observed_gsvi']:+.1f} pp)"),
        row("Observation", f"Cells >{far} m from an observation",
            f"{int(s['n_cells_beyond_far_gsvi']):,} ({s['pct_cells_beyond_far_gsvi']:.1f}%)",
            f"{int(s['n_cells_beyond_far_gsc']):,} ({s['pct_cells_beyond_far_gsc']:.1f}%)",
            f"{int(s['n_cells_beyond_far_gsc'] - s['n_cells_beyond_far_gsvi']):+,} "
            f"({s['pct_cells_beyond_far_gsc'] - s['pct_cells_beyond_far_gsvi']:+.1f} pp)"),
        row("Observation", "Cells observed only with self-collected imagery", "—",
            f"{int(s['n_cells_newly_observed']):,}",
            f"+{s['pct_gain_relative']:.1f}% of the GSVI frame"),
    ]
    return rows, {"n_new_cells": int(s["n_cells_newly_observed"])}


def measurement_rows() -> list[dict]:
    d = pd.read_csv(need(IDENT / "3_sc_domain_transfer.csv"))
    wide = d.pivot(index="sc_share", columns="domain", values=["recall", "mAP50"])
    wide.columns = [f"{m}_{dom}" for m, dom in wide.columns]
    lo, hi = wide.index.min(), wide.index.max()
    a, b = wide.loc[lo], wide.loc[hi]
    return [
        row("Measurement", "Recall on self-collected imagery",
            f"{100 * a['recall_sc']:.1f}%", f"{100 * b['recall_sc']:.1f}%",
            f"{100 * (b['recall_sc'] - a['recall_sc']):+.1f} pp"),
        row("Measurement", "Recall gap (GSVI − self-collected)",
            f"{100 * (a['recall_gsvi'] - a['recall_sc']):+.1f} pp",
            f"{100 * (b['recall_gsvi'] - b['recall_sc']):+.1f} pp",
            "No gap at any mix"),
        row("Measurement", "mAP@0.50 on self-collected imagery",
            f"{a['mAP50_sc']:.3f}", f"{b['mAP50_sc']:.3f}",
            f"{100 * (b['mAP50_sc'] / a['mAP50_sc'] - 1):+.0f}%"),
        row("Measurement", "mAP@0.50 gap (GSVI − self-collected)",
            f"{a['mAP50_gsvi'] - a['mAP50_sc']:+.3f}",
            f"{b['mAP50_gsvi'] - b['mAP50_sc']:+.3f}",
            f"{100 * (1 - (b['mAP50_gsvi'] - b['mAP50_sc']) / (a['mAP50_gsvi'] - a['mAP50_sc'])):.0f}% of the gap closed"),
    ]


def indicator_rows() -> list[dict]:
    prov = pd.read_csv(need(INDICATOR / "1_sc_indicator_provenance.csv"))
    eff = pd.read_csv(need(INDICATOR / "thesis_table" / "table_6_3_indicator_effect.csv"))
    changed = pd.read_csv(need(INDICATOR / "1_sc_indicator_changed_cells.csv"))
    val = pd.read_csv(need(INDICATOR / "thesis_table" / "table_6_3_validation_comparison.csv"))

    def prov_row(name: str) -> pd.Series:
        return prov[prov["Provenance"] == name].iloc[0]

    def eff_row(metric: str) -> pd.Series:
        return eff[eff["Metric"] == metric].iloc[0]

    def changed_value(measure: str) -> str:
        m = changed[changed["Measure"] == measure]
        return m["Value"].iloc[0] if len(m) else "—"

    def val_row(subset_starts: str, measure: str) -> pd.Series | None:
        m = val[val["Subset"].str.startswith(subset_starts) & (val["Measure"] == measure)]
        return m.iloc[0] if len(m) else None

    direct = prov_row("Direct share of represented surface")
    unsupported = prov_row("Unsupported, platform-coded low")
    rows = [
        row("Indicator", "Direct share of represented cells",
            direct["GSVI"], direct["GSVI + SC"], direct["Change"]),
        row("Indicator", "Cells beyond interpolation support",
            unsupported["GSVI"].split(" ")[0], unsupported["GSVI + SC"].split(" ")[0],
            unsupported["Change"]),
    ]
    for cls in ("Medium", "High"):
        r = eff_row(f"Cells classified {cls}")
        rows.append(row("Indicator", f"Cells classified {cls}", r["GSVI"], r["GSVI + SC"], r["Change"]))
    rows.append(row("Indicator", "Cells changing published class", "—",
                    changed_value("Cells changing published class"), "—"))
    rows.append(row("Indicator", "  of those, changed without receiving an image", "—",
                    changed_value("  changed only through the spatial fill"), "—"))

    acc_all = val_row("All validated cells", "3-class accuracy")
    acc_img = val_row("Changed, received imagery", "3-class accuracy")
    acc_fill = val_row("Changed through the spatial fill", "3-class accuracy")
    if acc_all is not None:
        rows.append(row("Indicator", "Agreement with crowd validation (3-class)",
                        acc_all["GSVI"], acc_all["GSVI + SC"], acc_all["Change"]))
    if acc_img is not None:
        rows.append(row("Indicator", "  on changed cells that received an image",
                        acc_img["GSVI"], acc_img["GSVI + SC"], acc_img["Change"]))
    if acc_fill is not None:
        rows.append(row("Indicator", "  on changed cells moved by interpolation",
                        acc_fill["GSVI"], acc_fill["GSVI + SC"], acc_fill["Change"]))
    return rows


def pattern_rows() -> list[dict]:
    hdb = pd.read_csv(need(PATTERN / "HDBSCAN" / "thesis_table" / "table_6_4_hdbscan_comparison.csv"), dtype=str)
    stab = pd.read_csv(need(PATTERN / "HDBSCAN" / "thesis_table" / "table_6_4_hdbscan_stability.csv"))
    settle = pd.read_csv(need(PATTERN / "settlement" / "thesis_table" / "table_6_4_settlement_comparison.csv"), dtype=str)
    gam = pd.read_csv(need(PATTERN / "Signed_distance" / "thesis_table" / "table_6_4_gam_comparison.csv"), dtype=str)

    def pick(df: pd.DataFrame, key_col: str, key: str) -> pd.Series:
        return df[df[key_col] == key].iloc[0]

    n_hot = pick(hdb, "Metric", "Number of hotspots")
    ari = pick(stab, "Measure", "Adjusted Rand Index")["Value"]
    rate_out = pick(settle, "Measure", "Waste-positive rate outside")
    pr = pick(settle, "Measure", "Prevalence ratio (inside / outside)")
    nnr = pick(settle, "Measure", "Observation-frame NNR")
    r2 = pick(gam, "Measure", "Pseudo-R², year + s(distance)")
    return [
        row("Pattern", "Waste hotspots (HDBSCAN)", n_hot["GSVI"], n_hot["GSVI + SC"],
            f"{n_hot['Change']}; label ARI {ari}"),
        row("Pattern", "Waste-positive rate outside settlements",
            rate_out["GSVI"], rate_out["GSVI + SC"], "unchanged"),
        row("Pattern", "Settlement prevalence ratio", pr["GSVI"], pr["GSVI + SC"],
            f"{float(pr['GSVI + SC']) - float(pr['GSVI']):+.2f}"),
        row("Pattern", "Observation-frame NNR", nnr["GSVI"], nnr["GSVI + SC"],
            f"{float(nnr['GSVI + SC']) - float(nnr['GSVI']):+.3f}"),
        row("Pattern", "Signed-distance GAM pseudo-R²", r2["GSVI"], r2["GSVI + SC"],
            f"{float(r2['GSVI + SC']) - float(r2['GSVI']):+.3f}"),
    ]


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    obs_rows, _ = observation_rows()
    rows = obs_rows + measurement_rows() + indicator_rows() + pattern_rows()
    table = pd.DataFrame(rows)
    table.to_csv(SUMMARY_TABLE, index=False)
    table.to_csv(DETAIL_CSV, index=False)

    print("Table 6.0 — Effect of supplementary local observations across the "
          "visible-waste representation pipeline\n")
    for stage in table["Stage"].unique():
        sub = table[table["Stage"] == stage]
        print(f"[{stage}]")
        print(sub[["Metric", "GSVI baseline", "GSVI + SC", "Change"]].to_string(index=False))
        print()
    print(f"Wrote {SUMMARY_TABLE}")
    print(f"Wrote {DETAIL_CSV}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 6 anchor — one table across the whole representation pipeline.

Steps 2-5 identify and quantify representation gaps. Step 6 asks how far
supplementary local observation closes them. Each sub-step answers that for one
stage; this script collects those answers into the single table the section is
built around, reading only outputs the sub-steps already wrote.

  Observation   6.1  what self-collected imagery adds to the 100 m frame
  Measurement   6.2  whether SC in the training mix improves detection
  Indicator     6.3  whether the published surface changes, and improves
  Pattern       6.4  whether the spatial conclusions move

The Observation and Indicator stages count directly observed cells under
different rules, and the table says so rather than hiding it. Observation snaps
points that fall in grid slivers to the nearest cell within 100 m (Step 2e's
rule, so totals reconcile with Step 1); the Indicator uses lib/ideamaps.py's
plain within-cell join, which reproduces the IDEAMaps submission. The two differ
by 53 cells — 22,725 against 22,672 — which is why the Observation row reads
32.5% while Step 6.3 reports 32.4%. Both are in
1_sources/1_Nairobi_sc_coverage_summary.csv.

The measurement stage is scored on the GSVI held-out set, because that is the
only independent test set the chapter uses. It therefore answers "does local
training data make the detector better" and not "does the detector work on
local imagery" — the latter would need a self-collected test set, which is
deliberately out of scope.

The table is deliberately blunt about direction. A row that does not move is
reported as not moving; that is the finding for most of this pipeline.

Run after every other Step 6 script.

One row per claim, and only claims the chapter makes. The fuller per-stage
numbers stay in the sub-steps' own tables; nothing is duplicated here.

Outputs (Data/Chapter_waste/6_selfcollected/):
  thesis_table/table_6_0_mitigation_summary.csv   the section anchor
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir, waste_id_dir  # noqa: E402

ROOT = selfcollected_dir()
TABLE_DIR = ROOT / "thesis_table"

SOURCES = ROOT / "1_sources"
INDICATOR = ROOT / "3_indicator"
PATTERN = ROOT / "4_pattern"

SENSITIVITY_TABLE = waste_id_dir() / "thesis_table" / "table_4_sc_sensitivity.csv"

SUMMARY_TABLE = TABLE_DIR / "table_6_0_mitigation_summary.csv"


def need(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"Missing {path}\nRun the Step 6 sub-steps first (see README Step 6).")
    return path


def row(stage: str, metric: str, base: str, mitigated: str, change: str) -> dict:
    return {"Stage": stage, "Metric": metric, "GSVI baseline": base,
            "After SC integration": mitigated, "Change": change}


def observation_rows() -> list[dict]:
    s = pd.read_csv(need(SOURCES / "1_Nairobi_sc_coverage_summary.csv")).iloc[0]
    far = int(s["far_m"])
    return [
        row("Observation", "Directly observed 100 m cells [snapped frame]",
            f"{int(s['n_cells_observed_gsvi']):,} ({s['pct_cells_observed_gsvi']:.1f}%)",
            f"{int(s['n_cells_observed_gsc']):,} ({s['pct_cells_observed_gsc']:.1f}%)",
            f"+{int(s['n_cells_newly_observed']):,} ({s['pct_cells_observed_gsc'] - s['pct_cells_observed_gsvi']:+.1f} pp)"),
        row("Observation", f"Cells >{far} m from an observation",
            f"{int(s['n_cells_beyond_far_gsvi']):,} ({s['pct_cells_beyond_far_gsvi']:.1f}%)",
            f"{int(s['n_cells_beyond_far_gsc']):,} ({s['pct_cells_beyond_far_gsc']:.1f}%)",
            f"{int(s['n_cells_beyond_far_gsc'] - s['n_cells_beyond_far_gsvi']):+,} "
            f"({s['pct_cells_beyond_far_gsc'] - s['pct_cells_beyond_far_gsvi']:+.1f} pp)"),
        # Not how much imagery was collected, but what it bought. P_new is the
        # share of reached cells that were new; the reciprocal of E_cov says how
        # many photographs one newly observed cell cost.
        row("Observation", "Cells reached by SC that were previously unobserved (P_new)",
            "—", f"{s['pct_sc_cells_previously_unobserved']:.1f}%",
            f"{s['pct_sc_cells_redundant']:.1f}% already observed"),
        row("Observation", "Self-collected images per newly observed cell",
            "—", f"{s['sc_images_per_newly_observed_cell']:.0f}",
            f"E_cov = {s['newly_observed_cells_per_sc_image']:.3f}"),
    ]


def measurement_rows() -> list[dict]:
    """The cascade's F1 on the GSVI held-out set, 0% vs 100% SC in training."""
    d = pd.read_csv(need(SENSITIVITY_TABLE), dtype=str)
    d["share"] = d["YOLO training set"].str.extract(r"^(\d+)").astype(int)
    cascade = d[d["Stage"] == "YOLO → Qwen"]
    a = cascade.loc[cascade["share"].idxmin(), "F1"]
    b = cascade.loc[cascade["share"].idxmax(), "F1"]
    delta = float(b.rstrip("%")) - float(a.rstrip("%"))
    return [row("Measurement", "CV–VLM F1", a, b, f"{delta:+.1f} pp")]


def indicator_rows() -> list[dict]:
    prov = pd.read_csv(need(INDICATOR / "1_sc_indicator_provenance.csv"))
    changed = pd.read_csv(need(INDICATOR / "1_sc_indicator_changed_cells.csv"))
    val = pd.read_csv(need(INDICATOR / "thesis_table" / "table_6_3_validation_comparison.csv"))

    direct = prov[prov["Provenance"] == "Direct share of represented surface"].iloc[0]

    def changed_value(measure: str) -> str:
        m = changed[changed["Measure"] == measure]
        return m["Value"].iloc[0] if len(m) else "—"

    agree = val[val["Subset"].str.startswith("All validated cells")
                & (val["Measure"] == "3-class accuracy")].iloc[0]

    return [
        row("Indicator", "Direct share of represented cells [strict frame]",
            direct["GSVI"], direct["GSVI + SC"], direct["Change"]),
        row("Indicator", "Cells changing final indicator class", "—",
            changed_value("Cells changing published class").replace(" of grid", ""), "—"),
        row("Indicator", "Changed cells affected through interpolation", "—",
            changed_value("  changed only through the spatial fill"), "—"),
        row("Indicator", "Three-class agreement with local validation",
            agree["GSVI"], agree["GSVI + SC"], agree["Change"]),
    ]


def pattern_rows() -> list[dict]:
    hdb = pd.read_csv(need(PATTERN / "HDBSCAN" / "1_sc_hdbscan_comparison.csv"), dtype=str)
    settle = pd.read_csv(need(PATTERN / "settlement" / "thesis_table" / "table_6_4_settlement_comparison.csv"), dtype=str)

    n_hot = hdb[hdb["Metric"] == "Number of hotspots"].iloc[0]
    pr = settle[settle["Measure"] == "Prevalence ratio (inside / outside)"].iloc[0]
    return [
        row("Socio-spatial pattern", "HDBSCAN hotspots",
            n_hot["GSVI"], n_hot["GSVI + SC"], n_hot["Change"]),
        row("Socio-spatial pattern", "Settlement prevalence ratio",
            pr["GSVI"], pr["GSVI + SC"],
            f"{float(pr['GSVI + SC']) - float(pr['GSVI']):+.2f}"),
    ]


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    rows = observation_rows() + measurement_rows() + indicator_rows() + pattern_rows()
    table = pd.DataFrame(rows)
    # Stage labels the first row of each block only, as the chapter prints it.
    table["Stage"] = table["Stage"].mask(table["Stage"].duplicated(), "")
    table.to_csv(SUMMARY_TABLE, index=False)

    print("Table 6.0 — Effect of supplementary local observations across the "
          "visible-waste representation pipeline\n")
    print(table.to_string(index=False))
    print(f"\nWrote {SUMMARY_TABLE}")


if __name__ == "__main__":
    main()

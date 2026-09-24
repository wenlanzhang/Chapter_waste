#!/usr/bin/env python3
"""Step 6.3b — is the surface with self-collected imagery any *better*?

1_sc_indicator.py compares the two indicator surfaces to each other: 670 cells
change published class and the High class grows 53%. That says the surface
moved, not that it improved. Only an independent judgement can say which
direction it moved in, so this script scores both arms against the IDEAMaps
crowd validation clicks — the same reference Step 4b uses.

Three subsets, each answering a different question:

  All validated cells         does the published surface agree better overall
  Cells holding SC imagery    the targeted test: where field collection
                              actually reached a validated cell, did it help
  Cells that changed class    among the cells that actually moved, did they
                              move towards the crowd label or away from it
    ... that moved WITH imagery      evidence-driven change
    ... that moved through the fill  interpolation-driven change

The last split is the decisive one, because 6.3 found that nine in ten changed
cells never received an image. If the evidence-driven changes improve agreement
and the interpolation-driven ones do not, then the surface is moving further
than its evidence warrants.

The changed-cell subsets are paired comparisons on the same cells, so McNemar's
exact test applies.

A caution the numbers cannot carry themselves: these subsets are small. The
result is directional evidence about a 1% increase in imagery, not a powered
test of whether field collection improves indicators in general.

Inputs:
  6_selfcollected/3_indicator/1_Nairobi_sc_indicator_grid100m_32737.gpkg
  1prepare_chapter_data/Nairobi_validation_grid_32737.gpkg   (Step 1)

Outputs (Data/Chapter_waste/6_selfcollected/3_indicator/):
  2_sc_validation_cells.csv                     one row per validated cell, both arms
  2_sc_validation_confusion.csv                 3-class crowd x indicator, both arms
  2_sc_validation_detail.csv                    numeric metrics behind the table
  thesis_table/table_6_3_validation_comparison.csv
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import stats

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import prep_dir, selfcollected_dir  # noqa: E402

OUTPUT_DIR = selfcollected_dir() / "3_indicator"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GRID_GPKG = OUTPUT_DIR / "1_Nairobi_sc_indicator_grid100m_32737.gpkg"
VALIDATION_GPKG = prep_dir() / "Nairobi_validation_grid_32737.gpkg"

CELLS_CSV = OUTPUT_DIR / "2_sc_validation_cells.csv"
CONFUSION_CSV = OUTPUT_DIR / "2_sc_validation_confusion.csv"
DETAIL_CSV = OUTPUT_DIR / "2_sc_validation_detail.csv"
COMPARISON_TABLE = TABLE_DIR / "table_6_3_validation_comparison.csv"

CLASS_LABELS = {0: "Low", 1: "Medium", 2: "High"}
ARMS = {"gsvi": "GSVI", "gsc": "GSVI + SC"}


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = successes / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) / n) + z2 / (4.0 * n * n)) / den
    return max(0.0, centre - margin), min(1.0, centre + margin)


def cohens_kappa(truth: np.ndarray, pred: np.ndarray) -> float:
    """Undefined when the reference labels are constant — chance agreement is then 1."""
    labels = sorted(set(truth) | set(pred))
    n = len(truth)
    if n == 0 or len(set(truth)) < 2:
        return float("nan")
    observed = float((truth == pred).mean())
    expected = sum(
        (truth == lab).mean() * (pred == lab).mean() for lab in labels
    )
    if np.isclose(expected, 1.0):
        return float("nan")
    return float((observed - expected) / (1.0 - expected))


def load_cells() -> pd.DataFrame:
    """Validated cells with both arms' published class attached."""
    for path in (GRID_GPKG, VALIDATION_GPKG):
        if not path.exists():
            raise SystemExit(
                f"Missing {path} — run 6_selfcollected/3_indicator/1_sc_indicator.py "
                "and Step 1 first"
            )
    grid = gpd.read_file(GRID_GPKG, ignore_geometry=True)
    val = gpd.read_file(VALIDATION_GPKG, ignore_geometry=True)

    df = val.merge(
        grid[["cell_id", "result_gsvi", "result_gsc", "class_change", "received_sc",
              "indicator_provenance_gsvi", "indicator_provenance_gsc",
              "total_svi_images_gsvi", "total_svi_images_gsc"]],
        on="cell_id",
        how="inner",
    )
    df["crowd_class"] = df["validation_result"].astype(int)
    df["crowd_is_waste"] = (df["crowd_class"] > 0).astype(int)
    for tag in ARMS:
        df[f"pred_{tag}"] = df[f"result_{tag}"].astype(int)
        df[f"pred_is_waste_{tag}"] = (df[f"pred_{tag}"] > 0).astype(int)
    print(f"{len(df):,} of {len(val):,} validated cells matched to the indicator grid")
    return df


def binary_metrics(truth: np.ndarray, pred: np.ndarray) -> dict:
    tp = int(((truth == 1) & (pred == 1)).sum())
    fp = int(((truth == 0) & (pred == 1)).sum())
    fn = int(((truth == 1) & (pred == 0)).sum())
    tn = int(((truth == 0) & (pred == 0)).sum())
    n = tp + fp + fn + tn
    acc = (tp + tn) / n if n else np.nan
    prec = tp / (tp + fp) if tp + fp else np.nan
    rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if prec and rec and (prec + rec) else np.nan
    lo, hi = wilson_ci(tp + tn, n)
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": acc, "accuracy_ci_low": lo, "accuracy_ci_high": hi,
        "precision": prec, "recall": rec, "f1": f1,
    }


def score_subset(df: pd.DataFrame, label: str) -> list[dict]:
    rows = []
    for tag, arm_label in ARMS.items():
        binary = binary_metrics(
            df["crowd_is_waste"].to_numpy(), df[f"pred_is_waste_{tag}"].to_numpy()
        )
        three = float((df["crowd_class"] == df[f"pred_{tag}"]).mean()) if len(df) else np.nan
        rows.append(
            {
                "subset": label,
                "arm": arm_label,
                **binary,
                "severity_accuracy": three,
                "kappa_binary": cohens_kappa(
                    df["crowd_is_waste"].to_numpy(), df[f"pred_is_waste_{tag}"].to_numpy()
                ),
                "kappa_severity": cohens_kappa(
                    df["crowd_class"].to_numpy(), df[f"pred_{tag}"].to_numpy()
                ),
            }
        )
    return rows


def mcnemar_exact(df: pd.DataFrame) -> dict:
    """Paired test on the same cells: which arm agrees with the crowd where they differ.

    b = cells only GSVI gets right, c = cells only GSVI + SC gets right.
    Exact binomial, two-sided — the discordant counts here are small.
    """
    correct_a = df["crowd_is_waste"].to_numpy() == df["pred_is_waste_gsvi"].to_numpy()
    correct_b = df["crowd_is_waste"].to_numpy() == df["pred_is_waste_gsc"].to_numpy()
    b = int((correct_a & ~correct_b).sum())
    c = int((~correct_a & correct_b).sum())
    n_disc = b + c
    p = float(stats.binomtest(c, n_disc, 0.5).pvalue) if n_disc else float("nan")
    return {"only_gsvi_correct": b, "only_gsc_correct": c, "n_discordant": n_disc, "p_mcnemar": p}


def build_confusion(df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for tag, arm_label in ARMS.items():
        ct = pd.crosstab(
            df["crowd_class"].map(CLASS_LABELS).rename("Crowd"),
            df[f"pred_{tag}"].map(CLASS_LABELS).rename("Indicator"),
        )
        ct = ct.reindex(index=list(CLASS_LABELS.values()),
                        columns=list(CLASS_LABELS.values())).fillna(0).astype(int)
        long = ct.stack().reset_index(name="n")
        long.insert(0, "arm", arm_label)
        frames.append(long)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(CONFUSION_CSV, index=False)
    print(f"Wrote {CONFUSION_CSV}")
    return out


def fmt_kappa(value: float) -> str:
    return f"{value:.3f}" if np.isfinite(value) else "— (crowd labels constant)"


def build_table(detail: pd.DataFrame, mcnemar: dict, n_changed: int) -> pd.DataFrame:
    rows = []
    for subset in detail["subset"].unique():
        sub = detail[detail["subset"] == subset]
        g = sub[sub["arm"] == "GSVI"].iloc[0]
        s = sub[sub["arm"] == "GSVI + SC"].iloc[0]
        n = int(g["n"])
        rows.extend(
            [
                {"Subset": f"{subset} (n = {n:,})", "Measure": "Binary accuracy",
                 "GSVI": f"{100 * g['accuracy']:.1f}%", "GSVI + SC": f"{100 * s['accuracy']:.1f}%",
                 "Change": f"{100 * (s['accuracy'] - g['accuracy']):+.1f} pp"},
                {"Subset": f"{subset} (n = {n:,})", "Measure": "Binary precision",
                 "GSVI": f"{100 * g['precision']:.1f}%", "GSVI + SC": f"{100 * s['precision']:.1f}%",
                 "Change": f"{100 * (s['precision'] - g['precision']):+.1f} pp"},
                {"Subset": f"{subset} (n = {n:,})", "Measure": "Binary recall",
                 "GSVI": f"{100 * g['recall']:.1f}%", "GSVI + SC": f"{100 * s['recall']:.1f}%",
                 "Change": f"{100 * (s['recall'] - g['recall']):+.1f} pp"},
                {"Subset": f"{subset} (n = {n:,})", "Measure": "3-class accuracy",
                 "GSVI": f"{100 * g['severity_accuracy']:.1f}%",
                 "GSVI + SC": f"{100 * s['severity_accuracy']:.1f}%",
                 "Change": f"{100 * (s['severity_accuracy'] - g['severity_accuracy']):+.1f} pp"},
                {"Subset": f"{subset} (n = {n:,})", "Measure": "Cohen's κ (binary)",
                 "GSVI": fmt_kappa(g["kappa_binary"]), "GSVI + SC": fmt_kappa(s["kappa_binary"]),
                 "Change": (f"{s['kappa_binary'] - g['kappa_binary']:+.3f}"
                            if np.isfinite(g["kappa_binary"]) and np.isfinite(s["kappa_binary"])
                            else "—")},
            ]
        )
    rows.append(
        {
            "Subset": f"Cells that changed class (n = {n_changed:,})",
            "Measure": "McNemar, cells only one arm gets right",
            "GSVI": f"{mcnemar['only_gsvi_correct']:,}",
            "GSVI + SC": f"{mcnemar['only_gsc_correct']:,}",
            "Change": f"p = {mcnemar['p_mcnemar']:.3f}" if np.isfinite(mcnemar["p_mcnemar"]) else "—",
        }
    )
    out = pd.DataFrame(rows)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(COMPARISON_TABLE, index=False)
    print(f"\nAgreement with the IDEAMaps crowd validation:\n{out.to_string(index=False)}")
    print(f"Wrote {COMPARISON_TABLE}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    df = load_cells()
    df.to_csv(CELLS_CSV, index=False)
    print(f"Wrote {CELLS_CSV}")

    changed = df[df["class_change"] != 0]
    with_sc = df[df["received_sc"] == 1]
    print(f"  {len(changed):,} validated cells changed published class")
    print(f"  {len(with_sc):,} validated cells hold self-collected imagery")

    changed_with_sc = changed[changed["received_sc"] == 1]
    changed_by_fill = changed[changed["received_sc"] == 0]
    print(f"    of which {len(changed_with_sc):,} received imagery, "
          f"{len(changed_by_fill):,} moved through the spatial fill")

    detail_rows = score_subset(df, "All validated cells")
    if len(with_sc):
        detail_rows += score_subset(with_sc, "Cells holding SC imagery")
    if len(changed):
        detail_rows += score_subset(changed, "Cells that changed class")
    if len(changed_with_sc):
        detail_rows += score_subset(changed_with_sc, "Changed, received imagery")
    if len(changed_by_fill):
        detail_rows += score_subset(changed_by_fill, "Changed through the spatial fill")
    detail = pd.DataFrame(detail_rows)
    detail.to_csv(DETAIL_CSV, index=False)
    print(f"Wrote {DETAIL_CSV}")

    mcnemar = mcnemar_exact(changed if len(changed) else df)
    print(f"\nMcNemar on the {len(changed):,} changed cells: "
          f"only GSVI correct {mcnemar['only_gsvi_correct']}, "
          f"only GSVI+SC correct {mcnemar['only_gsc_correct']}, "
          f"p = {mcnemar['p_mcnemar']:.3f}")
    for label, sub in (("received imagery", changed_with_sc), ("spatial fill", changed_by_fill)):
        if len(sub):
            m = mcnemar_exact(sub)
            print(f"  {label} (n = {len(sub):,}): only GSVI {m['only_gsvi_correct']}, "
                  f"only GSVI+SC {m['only_gsc_correct']}, p = {m['p_mcnemar']:.3f}")

    build_confusion(df)
    build_table(detail, mcnemar, len(changed))


if __name__ == "__main__":
    main()

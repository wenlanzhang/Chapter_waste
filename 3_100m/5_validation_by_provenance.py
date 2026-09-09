#!/usr/bin/env python3
"""
Crowd validation of the IDEAMaps waste indicator, by GSVI provenance.

Compares the IDEAMaps waste indicator (submission model_result) with crowd
labels on validated 100 m cells. Main thesis table keeps two rows:
  - all crowd-validation cells
  - cells with direct GSVI observations

Metrics apply only to the crowd-validation sample (not all Nairobi cells).
Higher recall on directly observed cells is consistent with observation-stage
loss, but does not by itself prove that imagery availability caused the
difference (subsets may also differ geographically or in waste prevalence).

Requires 4_indicator_provenance.py outputs (cell-level provenance CSV).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from output_paths import INPUT_DIR, OUTPUT_DIR

VALIDATION_GRID_GPKG = INPUT_DIR / "Nairobi_validation_grid_32737.gpkg"
PROVENANCE_CELLS_CSV = OUTPUT_DIR / "grid" / "Nairobi_indicator_provenance_cells.csv"
THESIS_DIR = OUTPUT_DIR / "thesis_table"
SUMMARY_CSV = OUTPUT_DIR / "validation" / "Nairobi_validation_by_provenance.csv"
TABLE_PATH = THESIS_DIR / "table_validation_by_provenance.csv"

DIRECT = "Direct observation"
INTERPOLATED = "Interpolated support"


def binary_metrics(df: pd.DataFrame) -> dict:
    """Binary waste metrics: crowd is_waste vs IDEAMaps indicator model_is_waste."""
    truth = df["is_waste"].astype(int)
    pred = df["model_is_waste"].astype(int)
    n = len(df)
    tp = int(((truth == 1) & (pred == 1)).sum())
    fp = int(((truth == 0) & (pred == 1)).sum())
    tn = int(((truth == 0) & (pred == 0)).sum())
    fn = int(((truth == 1) & (pred == 0)).sum())
    accuracy = (tp + tn) / n if n else float("nan")
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else float("nan")
    )
    return {
        "n_cells": n,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def format_thesis_row(label: str, metrics: dict) -> dict:
    return {
        "Validation sample": label,
        "Cells, n": f"{metrics['n_cells']:,}",
        "Accuracy (%)": f"{100.0 * metrics['accuracy']:.1f}",
        "Precision (%)": f"{100.0 * metrics['precision']:.1f}",
        "Recall (%)": f"{100.0 * metrics['recall']:.1f}",
        "F1": f"{metrics['f1']:.3f}",
    }


def main() -> None:
    if not PROVENANCE_CELLS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {PROVENANCE_CELLS_CSV}\n"
            "Run first: python 3_100m/4_indicator_provenance.py"
        )

    THESIS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "validation").mkdir(parents=True, exist_ok=True)

    print("Crowd validation of IDEAMaps waste indicator by GSVI provenance...")
    provenance = pd.read_csv(PROVENANCE_CELLS_CSV)
    validation = gpd.read_file(VALIDATION_GRID_GPKG).drop(columns="geometry")

    merged = validation.merge(
        provenance[["cell_id", "indicator_provenance", "total_svi_images", "result"]],
        on="cell_id",
        how="left",
        validate="one_to_one",
    )
    if merged["indicator_provenance"].isna().any():
        n_miss = int(merged["indicator_provenance"].isna().sum())
        raise RuntimeError(
            f"{n_miss} validation cells lack provenance labels; re-run "
            "4_indicator_provenance.py on the same grid."
        )

    # Full numeric summary (includes evidence-supported for archive / appendix)
    all_samples = [
        ("All crowd-validation cells", merged),
        (
            "Evidence-supported cells (direct + interpolated)",
            merged.loc[
                merged["indicator_provenance"].isin([DIRECT, INTERPOLATED])
            ].copy(),
        ),
        (
            "Cells with direct GSVI observations",
            merged.loc[merged["indicator_provenance"] == DIRECT].copy(),
        ),
    ]

    numeric_rows = []
    for label, subset in all_samples:
        metrics = binary_metrics(subset)
        numeric_rows.append({"Validation sample": label, **metrics})
    summary = pd.DataFrame(numeric_rows)
    summary.to_csv(SUMMARY_CSV, index=False)

    # Main thesis table: two rows only (evidence-supported == all in this sample)
    thesis_samples = [
        ("All crowd-validation cells", merged),
        (
            "Cells with direct GSVI observations",
            merged.loc[merged["indicator_provenance"] == DIRECT].copy(),
        ),
    ]
    thesis = pd.DataFrame(
        [format_thesis_row(label, binary_metrics(subset)) for label, subset in thesis_samples]
    )
    thesis.to_csv(TABLE_PATH, index=False)

    print(thesis.to_string(index=False))
    print(f"\nWrote {SUMMARY_CSV}")
    print(f"Wrote {TABLE_PATH}")
    print(
        "Note: metrics are on the crowd-validation sample only "
        "(not all Nairobi grid cells)."
    )


if __name__ == "__main__":
    main()

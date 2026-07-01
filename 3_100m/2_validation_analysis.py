"""
IDEAMaps validation analysis — model vs crowd labels on 100 m grid cells.

Reads Step 1 validation grid (max severity when multiple validators per cell)
and writes confusion matrices + accuracy metrics for R plotting.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

VALIDATION_GRID_GPKG = INPUT_DIR / "Nairobi_validation_grid_32737.gpkg"
VALIDATION_GRID_CSV = OUTPUT_DIR / "Nairobi_validation_grid.csv"

SEVERITY_LEVELS = [0, 1, 2]
SEVERITY_LABELS = {
    0: "No waste (0)",
    1: "Medium (1)",
    2: "High (2)",
}
BINARY_LABELS = {0: "No waste", 1: "Waste present"}


def build_confusion_matrix(
    df: pd.DataFrame,
    truth_col: str,
    pred_col: str,
    levels: list[int],
    truth_name: str,
    pred_name: str,
) -> pd.DataFrame:
    ct = pd.crosstab(df[truth_col], df[pred_col], dropna=False)
    ct = ct.reindex(index=levels, columns=levels, fill_value=0).astype(int)
    ct.index.name = truth_name
    ct.columns.name = pred_name

    long_rows = []
    n_total = int(ct.values.sum())
    for truth in levels:
        row_total = int(ct.loc[truth].sum())
        for pred in levels:
            n = int(ct.loc[truth, pred])
            long_rows.append(
                {
                    "truth": truth,
                    "pred": pred,
                    "n": n,
                    "pct_of_total": round(100.0 * n / n_total, 2) if n_total else 0.0,
                    "pct_of_truth_row": round(100.0 * n / row_total, 2) if row_total else 0.0,
                }
            )
    return pd.DataFrame(long_rows)


def classification_metrics(df: pd.DataFrame, truth_col: str, pred_col: str) -> dict:
    truth = df[truth_col]
    pred = df[pred_col]
    n = len(df)
    accuracy = float((truth == pred).mean()) if n else float("nan")

    # One-vs-rest recall for waste presence when binary columns exist
    if truth_col.endswith("_is_waste") or truth_col == "is_waste":
        tp = int(((truth == 1) & (pred == 1)).sum())
        fn = int(((truth == 1) & (pred == 0)).sum())
        fp = int(((truth == 0) & (pred == 1)).sum())
        tn = int(((truth == 0) & (pred == 0)).sum())
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall > 0
            else float("nan")
        )
        return {
            "n_cells": n,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
        }

    return {"n_cells": n, "accuracy": round(accuracy, 4)}


def build_summary_table(
    severity_metrics: dict,
    binary_metrics: dict,
    grid: gpd.GeoDataFrame,
) -> pd.DataFrame:
    multi = int((grid["n_validations"] > 1).sum())
    return pd.DataFrame(
        [
            {"Metric": "Validated grid cells", "Value": f"{len(grid):,}"},
            {"Metric": "Cells with 2+ validation clicks", "Value": f"{multi:,}"},
            {
                "Metric": "Aggregation rule",
                "Value": "Max severity (0/1/2) per cell",
            },
            {
                "Metric": "3-class accuracy",
                "Value": f"{severity_metrics['accuracy']:.1%}",
            },
            {
                "Metric": "Binary accuracy (waste present)",
                "Value": f"{binary_metrics['accuracy']:.1%}",
            },
            {
                "Metric": "Binary precision",
                "Value": f"{binary_metrics['precision']:.1%}",
            },
            {"Metric": "Binary recall", "Value": f"{binary_metrics['recall']:.1%}"},
            {"Metric": "Binary F1", "Value": f"{binary_metrics['f1']:.3f}"},
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    grid = gpd.read_file(VALIDATION_GRID_GPKG)
    attrs = grid.drop(columns="geometry").copy()
    attrs.to_csv(VALIDATION_GRID_CSV, index=False)

    severity_cm = build_confusion_matrix(
        attrs,
        truth_col="validation_result",
        pred_col="model_result",
        levels=SEVERITY_LEVELS,
        truth_name="validation_result",
        pred_name="model_result",
    )
    binary_cm = build_confusion_matrix(
        attrs,
        truth_col="is_waste",
        pred_col="model_is_waste",
        levels=[0, 1],
        truth_name="is_waste",
        pred_name="model_is_waste",
    )

    severity_metrics = classification_metrics(
        attrs, "validation_result", "model_result"
    )
    binary_metrics = classification_metrics(attrs, "is_waste", "model_is_waste")
    summary = build_summary_table(severity_metrics, binary_metrics, grid)

    severity_cm_path = TABLE_DIR / "Nairobi_validation_confusion_severity.csv"
    binary_cm_path = TABLE_DIR / "Nairobi_validation_confusion_binary.csv"
    metrics_path = TABLE_DIR / "Nairobi_validation_metrics.csv"
    summary_path = TABLE_DIR / "Nairobi_validation_summary.csv"

    severity_cm.to_csv(severity_cm_path, index=False)
    binary_cm.to_csv(binary_cm_path, index=False)
    pd.DataFrame([severity_metrics, binary_metrics]).to_csv(metrics_path, index=False)
    summary.to_csv(summary_path, index=False)

    print(f"Wrote {VALIDATION_GRID_CSV}")
    print(f"Wrote {severity_cm_path}")
    print(f"Wrote {binary_cm_path}")
    print(f"Wrote {metrics_path}")
    print(f"Wrote {summary_path}")
    print()
    print("Validation summary:")
    print(summary.to_string(index=False))
    print()
    print("3-class confusion (validation → model, counts):")
    wide = severity_cm.pivot(index="truth", columns="pred", values="n").fillna(0).astype(int)
    print(wide.to_string())
    print()
    print("Binary confusion (validation → model, counts):")
    wide_bin = binary_cm.pivot(index="truth", columns="pred", values="n").fillna(0).astype(int)
    print(wide_bin.to_string())


if __name__ == "__main__":
    main()

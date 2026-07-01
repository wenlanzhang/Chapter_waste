"""
Mitigation validation — crowd labels vs GSVI vs GSVI + self-collected.

Both arms recomputed on the Nairobi-clipped 100 m grid (Step 1) with identical
pipeline settings and fixed IDEAMaps submission Jenks break points. Only the
input SVI/waste layers differ (Google-only vs Google + Faith + ZWL).

model_result from the validation CSV is retained for reference only.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from ideamaps_grid_pipeline import (
    FIXED_BREAKS_METHOD_LABEL,
    METHOD_LABEL,
    attach_cell_keys,
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GRID_GPKG = INPUT_DIR / "Nairobi_grid_100m_32737.gpkg"
VALIDATION_GRID_GPKG = INPUT_DIR / "Nairobi_validation_grid_32737.gpkg"

GSVI_PREDICTOR = "GSVI (Nairobi grid)"
GSC_PREDICTOR = "G+Self (Nairobi grid)"

ARMS = {
    "gsvi": {
        "label": "GSVI only (Google)",
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg",
    },
    "gsvi_selfcollected": {
        "label": "GSVI + self-collected (Faith/ + ZWL/)",
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    },
}

SELF_SOURCES = ("Faith", "ZWL")
SEVERITY_CLASSES = (0, 1, 2)


def binary_prf(truth: pd.Series, pred: pd.Series) -> tuple[float, float, float]:
    tp = int(((truth == 1) & (pred == 1)).sum())
    fp = int(((truth == 0) & (pred == 1)).sum())
    fn = int(((truth == 1) & (pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else np.nan
    recall = tp / (tp + fn) if (tp + fn) else np.nan
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else np.nan
    )
    return precision, recall, f1


def multiclass_macro_prf(
    truth: pd.Series, pred: pd.Series, classes: tuple[int, ...] = SEVERITY_CLASSES
) -> tuple[float, float, float]:
    """Macro-averaged precision, recall, F1 over severity classes (one-vs-rest)."""
    precs, recs, f1s = [], [], []
    for c in classes:
        tp = int(((truth == c) & (pred == c)).sum())
        fp = int(((truth != c) & (pred == c)).sum())
        fn = int(((truth == c) & (pred != c)).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        precs.append(prec)
        recs.append(rec)
        f1s.append(f1)
    return float(np.mean(precs)), float(np.mean(recs)), float(np.mean(f1s))


def self_collected_overlap(grid: gpd.GeoDataFrame, validation: gpd.GeoDataFrame) -> pd.DataFrame:
    svi_all = gpd.read_file(ARMS["gsvi_selfcollected"]["svi_gpkg"])
    waste_all = gpd.read_file(ARMS["gsvi_selfcollected"]["waste_gpkg"])

    def cells_with(points: gpd.GeoDataFrame, sources: tuple[str, ...] | None) -> set[int]:
        pts = points if sources is None else points[points["source"].isin(sources)]
        joined = gpd.sjoin(
            pts, grid[["cell_id", "geometry"]], how="inner", predicate="within"
        )
        return set(joined["cell_id"].astype(int))

    all_self_svi = cells_with(svi_all, SELF_SOURCES)
    faith_svi = cells_with(svi_all, ("Faith",))
    zwl_svi = cells_with(svi_all, ("ZWL",))
    both_svi = faith_svi & zwl_svi
    self_waste = cells_with(waste_all, SELF_SOURCES)

    val_ids = set(validation["cell_id"].astype(int))
    n_val = len(val_ids)

    overlap_self_svi = val_ids & all_self_svi
    overlap_self_waste = val_ids & self_waste
    no_self = val_ids - all_self_svi

    rows = [
        ("Validated grid cells (crowd)", n_val, 100.0),
        ("With self-collected SVI images", len(overlap_self_svi), 100 * len(overlap_self_svi) / n_val),
        ("With self-collected waste detections", len(overlap_self_waste), 100 * len(overlap_self_waste) / n_val),
        ("Without self-collected SVI", len(no_self), 100 * len(no_self) / n_val),
        ("Faith SVI in validated cells", len(val_ids & faith_svi), 100 * len(val_ids & faith_svi) / n_val),
        ("ZWL SVI in validated cells", len(val_ids & zwl_svi), 100 * len(val_ids & zwl_svi) / n_val),
        ("Both Faith and ZWL SVI", len(val_ids & both_svi), 100 * len(val_ids & both_svi) / n_val),
        ("Nairobi grid cells with self-collected SVI", len(all_self_svi), np.nan),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Count", "Pct_of_validated"])


def metrics_row(
    df: pd.DataFrame,
    pred_sev_col: str,
    pred_bin_col: str,
    *,
    subset: str,
    predictor: str,
) -> dict:
    n = len(df)
    truth_sev = df["validation_result"]
    pred_sev = df[pred_sev_col]
    sev_acc = float((pred_sev == truth_sev).mean()) if n else np.nan
    sev_prec, sev_rec, sev_f1 = (
        multiclass_macro_prf(truth_sev, pred_sev) if n else (np.nan, np.nan, np.nan)
    )

    bin_acc = float((df[pred_bin_col] == df["is_waste"]).mean()) if n else np.nan
    precision, recall, f1 = (
        binary_prf(df["is_waste"], df[pred_bin_col]) if n else (np.nan, np.nan, np.nan)
    )
    tp = int(((df["is_waste"] == 1) & (df[pred_bin_col] == 1)).sum())
    fp = int(((df["is_waste"] == 0) & (df[pred_bin_col] == 1)).sum())
    fn = int(((df["is_waste"] == 1) & (df[pred_bin_col] == 0)).sum())
    tn = int(((df["is_waste"] == 0) & (df[pred_bin_col] == 0)).sum())
    return {
        "subset": subset,
        "predictor": predictor,
        "n_cells": n,
        "severity_accuracy": round(sev_acc, 4),
        "severity_precision": round(sev_prec, 4) if np.isfinite(sev_prec) else np.nan,
        "severity_recall": round(sev_rec, 4) if np.isfinite(sev_rec) else np.nan,
        "severity_f1": round(sev_f1, 4) if np.isfinite(sev_f1) else np.nan,
        "binary_accuracy": round(bin_acc, 4),
        "binary_precision": round(precision, 4) if np.isfinite(precision) else np.nan,
        "binary_recall": round(recall, 4) if np.isfinite(recall) else np.nan,
        "binary_f1": round(f1, 4) if np.isfinite(f1) else np.nan,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def build_comparison_table(df: pd.DataFrame) -> pd.DataFrame:
    subsets = [
        ("All validated cells", df),
        ("Self-collected SVI overlap", df[df["has_self_svi"]]),
        ("Prediction changed (G vs G+Self)", df[df["pred_changed"]]),
        ("Self overlap AND prediction changed", df[df["has_self_svi"] & df["pred_changed"]]),
    ]
    predictors = [
        (GSVI_PREDICTOR, "gsvi_result", "gsvi_pred_is_waste"),
        (GSC_PREDICTOR, "gsc_result", "gsc_pred_is_waste"),
    ]
    rows = []
    for subset_name, sub in subsets:
        for pred_name, sev_col, bin_col in predictors:
            rows.append(metrics_row(sub, sev_col, bin_col, subset=subset_name, predictor=pred_name))
    return pd.DataFrame(rows)


def build_method_table(gsvi_breaks: np.ndarray) -> pd.DataFrame:
    break_str = ", ".join(f"{b:.6f}" for b in gsvi_breaks)
    classification = FIXED_BREAKS_METHOD_LABEL
    return pd.DataFrame(
        [
            {"Item": "Grid extent", "Value": "Nairobi constituency clip (Step 1 Nairobi_grid_100m_32737.gpkg)"},
            {"Item": "Ratio pipeline", "Value": METHOD_LABEL.split(" + ")[0] + " + linear spatial fill"},
            {"Item": "GSVI inputs", "Value": "Step 1 Google SVI image + waste gpkgs"},
            {"Item": "G+Self inputs", "Value": "Step 1 gsvi_selfcollected SVI image + waste gpkgs"},
            {"Item": "Classification (both arms)", "Value": classification},
            {"Item": "Jenks upper bounds (proportion)", "Value": break_str},
            {
                "Item": "Fair comparison rule",
                "Value": "Same grid, pipeline, and Jenks thresholds; only SVI/waste counts differ",
            },
            {"Item": "Result scale", "Value": "0 = low, 1 = medium, 2 = high"},
            {"Item": "model_result column", "Value": "Retained in cell table for reference (IDEAMaps submission); not used as GSVI arm"},
        ]
    )


def build_summary_note(overlap: pd.DataFrame, comparison: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    n_self = int(overlap.loc[overlap["Metric"] == "With self-collected SVI images", "Count"].iloc[0])
    n_changed = int(df["pred_changed"].sum())
    n_val = len(df)
    n_model_match = int((df["gsvi_result"] == df["model_result"]).sum())

    all_gsvi = comparison[
        (comparison["subset"] == "All validated cells") & (comparison["predictor"] == GSVI_PREDICTOR)
    ].iloc[0]
    all_gsc = comparison[
        (comparison["subset"] == "All validated cells") & (comparison["predictor"] == GSC_PREDICTOR)
    ].iloc[0]
    self_gsvi = comparison[
        (comparison["subset"] == "Self-collected SVI overlap") & (comparison["predictor"] == GSVI_PREDICTOR)
    ].iloc[0]
    self_gsc = comparison[
        (comparison["subset"] == "Self-collected SVI overlap") & (comparison["predictor"] == GSC_PREDICTOR)
    ].iloc[0]

    delta_all = all_gsc["severity_accuracy"] - all_gsvi["severity_accuracy"]
    delta_self = self_gsc["severity_accuracy"] - self_gsvi["severity_accuracy"]

    return pd.DataFrame(
        [
            {"Topic": "Method", "Note": "Both arms on Nairobi grid with IDEAMaps submission Jenks breaks"},
            {"Topic": "Validated cells", "Note": f"{n_val:,} grid cells (max severity aggregation)"},
            {
                "Topic": "Self-collected overlap",
                "Note": f"{n_self:,} validated cells ({100 * n_self / n_val:.1f}%) with Faith/ZWL SVI",
            },
            {
                "Topic": "Cells where G+Self differs from GSVI",
                "Note": f"{n_changed:,} cells ({100 * n_changed / n_val:.1f}%)",
            },
            {
                "Topic": "Nairobi GSVI vs IDEAMaps model_result",
                "Note": f"{n_model_match:,}/{n_val:,} cells match ({100 * n_model_match / n_val:.1f}%)",
            },
            {
                "Topic": "All cells: 3-class accuracy",
                "Note": f"GSVI {all_gsvi['severity_accuracy']:.1%} → G+Self {all_gsc['severity_accuracy']:.1%} ({delta_all:+.1%})",
            },
            {
                "Topic": "Self-overlap: 3-class accuracy",
                "Note": f"GSVI {self_gsvi['severity_accuracy']:.1%} → G+Self {self_gsc['severity_accuracy']:.1%} ({delta_self:+.1%})",
            },
            {
                "Topic": "Data sufficiency",
                "Note": (
                    f"Only {n_changed} cells change class; n={n_self} self-overlap cells. "
                    "Directional evidence only — underpowered for formal tests."
                ),
            },
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    grid = gpd.read_file(GRID_GPKG)
    validation = attach_cell_keys(gpd.read_file(VALIDATION_GRID_GPKG))
    gsvi_breaks = load_gsvi_submission_jenks_breaks()

    overlap = self_collected_overlap(grid, validation)
    overlap_path = TABLE_DIR / "Nairobi_validation_selfcollected_overlap.csv"
    overlap.to_csv(overlap_path, index=False)

    gsvi_nairobi = attach_cell_keys(
        run_ideamaps_grid_pipeline(
            grid,
            ARMS["gsvi"]["svi_gpkg"],
            ARMS["gsvi"]["waste_gpkg"],
            jenks_breaks=gsvi_breaks,
        )
    )
    gsc_nairobi = attach_cell_keys(
        run_ideamaps_grid_pipeline(
            grid,
            ARMS["gsvi_selfcollected"]["svi_gpkg"],
            ARMS["gsvi_selfcollected"]["waste_gpkg"],
            jenks_breaks=gsvi_breaks,
        )
    )

    svi_self = gpd.read_file(ARMS["gsvi_selfcollected"]["svi_gpkg"])
    svi_self = svi_self[svi_self["source"].isin(SELF_SOURCES)]
    self_joined = gpd.sjoin(
        svi_self, grid[["cell_id", "geometry"]], how="inner", predicate="within"
    )
    self_svi_cells = set(self_joined["cell_id"].astype(int))

    waste_self = gpd.read_file(ARMS["gsvi_selfcollected"]["waste_gpkg"])
    waste_self = waste_self[waste_self["source"].isin(SELF_SOURCES)]
    waste_joined = gpd.sjoin(
        waste_self, grid[["cell_id", "geometry"]], how="inner", predicate="within"
    )
    self_waste_cells = set(waste_joined["cell_id"].astype(int))

    val_attrs = validation.drop(columns="geometry").copy()
    df = val_attrs.merge(
        gsvi_nairobi[["cell_id", "lat_r", "lon_r", "result", "waste_points", "total_svi_images"]].rename(
            columns={
                "result": "gsvi_result",
                "waste_points": "gsvi_waste_points",
                "total_svi_images": "gsvi_svi_images",
            }
        ),
        on=["cell_id", "lat_r", "lon_r"],
    ).merge(
        gsc_nairobi[["cell_id", "lat_r", "lon_r", "result", "waste_points", "total_svi_images"]].rename(
            columns={
                "result": "gsc_result",
                "waste_points": "gsc_waste_points",
                "total_svi_images": "gsc_svi_images",
            }
        ),
        on=["cell_id", "lat_r", "lon_r"],
    )

    df["has_self_svi"] = df["cell_id"].isin(self_svi_cells)
    df["has_self_waste"] = df["cell_id"].isin(self_waste_cells)
    df["gsvi_pred_is_waste"] = (df["gsvi_result"] > 0).astype(np.uint8)
    df["gsc_pred_is_waste"] = (df["gsc_result"] > 0).astype(np.uint8)
    df["pred_changed"] = df["gsvi_result"] != df["gsc_result"]
    df["gsvi_correct"] = df["gsvi_result"] == df["validation_result"]
    df["gsc_correct"] = df["gsc_result"] == df["validation_result"]
    df["mitigation_improved"] = (~df["gsvi_correct"]) & df["gsc_correct"]
    df["mitigation_worsened"] = df["gsvi_correct"] & (~df["gsc_correct"])

    comparison = build_comparison_table(df)
    summary = build_summary_note(overlap, comparison, df)
    method_table = build_method_table(gsvi_breaks)

    cells_path = TABLE_DIR / "Nairobi_validation_mitigation_cells.csv"
    comparison_path = TABLE_DIR / "Nairobi_validation_mitigation_comparison.csv"
    summary_path = TABLE_DIR / "Nairobi_validation_mitigation_summary.csv"
    method_path = TABLE_DIR / "Nairobi_validation_mitigation_method.csv"

    df.to_csv(cells_path, index=False)
    comparison.to_csv(comparison_path, index=False)
    summary.to_csv(summary_path, index=False)
    method_table.to_csv(method_path, index=False)

    print(f"Wrote {overlap_path}")
    print(f"Wrote {method_path}")
    print(f"Wrote {cells_path}")
    print(f"Wrote {comparison_path}")
    print(f"Wrote {summary_path}")
    print()
    print("Method:")
    print(method_table.to_string(index=False))
    print()
    print("Mitigation comparison (accuracy):")
    print(
        comparison[
            ["subset", "predictor", "n_cells", "severity_accuracy", "binary_accuracy"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()

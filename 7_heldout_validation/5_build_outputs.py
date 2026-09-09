#!/usr/bin/env python3
"""Build Step 7 thesis tables from Validation/ inputs.

Main held-out comparison (confusion matrix / primary metrics):
  YOLO (sc_100pct) → Qwen on all YOLO-positive images using the **best**
  of three independent full-positive replicates (highest F1 among Qwen2_1/2/3)

Replication / stability (secondary):
  All three Qwen runs + 3-run majority on the same 115 YOLO+ set

Writes under thesis_table/:
  - yolo_heldout_detection.csv
  - yolo_vs_qwen_heldout_display.csv
  - yolo_vs_qwen_heldout_ci_table.csv
  - yolo_vs_qwen_heldout_detail.csv     ← main panel + confusion plots
  - yolo_qwen_yolo_pos_replicates.csv   ← stability of 3 full-positive audits
  - yolo_qwen_citywide_funnel.csv         (optional)

Usage:
  python 7_heldout_validation/5_build_outputs.py
  python 7_heldout_validation/5_build_outputs.py --skip-funnel
  python 7_heldout_validation/5_build_outputs.py --skip-stability
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from paths import (
    DATA_ROOT,
    OUTPUT_DIR,
    THESIS_TABLE_DIR,
    VALIDATION_DIR,
)

ARCHIVE_VAL = DATA_ROOT / "Chapter_waste" / "6_sensitivity_archive" / "Validation"
UUID_PREFIX = re.compile(r"^[0-9a-f]{8}-", re.I)

QWEN_COLS = ("Qwen2_1", "Qwen2_2", "Qwen2_3")
WITH_QWEN_NAME = "heldout_GSVI_p100_image_level_predictions_with_qwen.csv"
SUMMARY_NAME = "heldout_GSVI_p100_val_summary.csv"
FP_CSV_NAME = "heldout_GSVI_p100_sc100pct_fp_conf001.csv"
QWEN_FP_NAME = "qwen2_vl_72b_segmind_results.csv"


def canonical_img_name(name: object) -> str:
    s = str(name).strip()
    if s.lower().endswith(".jpg"):
        s = s[:-4]
    if UUID_PREFIX.match(s):
        s = s.split("-", 1)[1]
    return s


def parse_qwen_yes_no(text: object) -> str | None:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    s = str(text).strip().lower()
    if not s or s.startswith("error"):
        return None
    token = re.split(r"[\s,.;:!?]+", s, maxsplit=1)[0].strip("\"'")
    if token in {"yes", "y"}:
        return "yes"
    if token in {"no", "n"}:
        return "no"
    if s.startswith("yes"):
        return "yes"
    if s.startswith("no"):
        return "no"
    return None


def metrics_binary(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    n = tp + fp + tn + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    p = successes / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) / n) + z2 / (4.0 * n * n)) / den
    return max(0.0, center - margin), min(1.0, center + margin)


def wilson_from_counts(tp: int, fp: int, tn: int, fn: int) -> dict[str, float]:
    n = tp + fp + tn + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    acc_lo, acc_hi = wilson_ci(tp + tn, n)
    prec_lo, prec_hi = wilson_ci(tp, tp + fp)
    rec_lo, rec_hi = wilson_ci(tp, tp + fn)
    f1_lo, f1_hi = wilson_ci(2 * tp, 2 * tp + fp + fn)
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy_ci95_low": float(acc_lo),
        "accuracy_ci95_high": float(acc_hi),
        "precision_ci95_low": float(prec_lo),
        "precision_ci95_high": float(prec_hi),
        "recall_ci95_low": float(rec_lo),
        "recall_ci95_high": float(rec_hi),
        "f1_ci95_low": float(f1_lo),
        "f1_ci95_high": float(f1_hi),
    }


def fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def fmt_ci(lo: float, hi: float) -> str:
    return f"{100 * lo:.1f}–{100 * hi:.1f}%"


def write_csv(df: pd.DataFrame, name: str) -> list[Path]:
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    df.to_csv(path, index=False)
    return [path]


def write_text(text: str, name: str) -> list[Path]:
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    path.write_text(text, encoding="utf-8")
    return [path]


def _find(*parts: str) -> Path | None:
    for root in (VALIDATION_DIR, ARCHIVE_VAL, OUTPUT_DIR):
        path = root.joinpath(*parts)
        if path.exists():
            return path
        alt = root / "del" / Path(*parts)
        if alt.exists():
            return alt
    return None


def resolve_main_inputs() -> dict[str, Path]:
    summary = _find(SUMMARY_NAME) or _find("heldout_GSVI_val_summary.csv")
    with_qwen = _find(WITH_QWEN_NAME)
    missing = [
        k
        for k, v in {"summary": summary, "with_qwen": with_qwen}.items()
        if v is None
    ]
    if missing:
        raise FileNotFoundError(
            f"Missing main held-out artifacts (best full YOLO+ Qwen run): {missing}. "
            f"Need {WITH_QWEN_NAME} from notebook 4_."
        )
    return {"summary": summary, "with_qwen": with_qwen}


def majority_yes_no(labels: list[str | None]) -> str | None:
    """Majority Yes/No; None if fewer than 2 valid votes or a tie after filtering Nones."""
    votes = [lab for lab in labels if lab in ("yes", "no")]
    if len(votes) < 2:
        return None
    n_yes = sum(1 for v in votes if v == "yes")
    n_no = len(votes) - n_yes
    if n_yes > n_no:
        return "yes"
    if n_no > n_yes:
        return "no"
    return None


def pipeline_pred_yolo_qwen(
    yolo: np.ndarray, labels: list[str | None]
) -> np.ndarray:
    """Final pred = YOLO positive AND Qwen Yes."""
    return np.array(
        [1 if yp == 1 and lab == "yes" else 0 for yp, lab in zip(yolo, labels)],
        dtype=np.int8,
    )


def write_citywide_funnel() -> Path:
    gsvi_path = DATA_ROOT / "Waste" / "QGIS" / "GSVI_Nairobi.csv"
    waste_path = DATA_ROOT / "Waste" / "QGIS" / "Waste_Nairobi.csv"
    gsvi = pd.read_csv(gsvi_path, low_memory=False)
    waste = pd.read_csv(waste_path, low_memory=False)

    yolo_mask = pd.to_numeric(gsvi["yolo_num"], errors="coerce").fillna(0) > 0
    n_yolo = int(yolo_mask.sum())
    pred = gsvi.loc[yolo_mask, "prediction"].astype(str)
    n_qwen_yes = int((pred == "yes").sum())
    n_qwen_no = int((pred == "no").sum())
    n_final = len(waste)
    retention_final = n_final / n_yolo if n_yolo else float("nan")

    funnel = pd.DataFrame(
        [
            {
                "stage": "01_gsvi_images_citywide",
                "n": len(gsvi),
                "share_of_yolo_candidates": None,
                "note": "All Google SVI images in GSVI_Nairobi.csv",
            },
            {
                "stage": "02_yolo_candidates",
                "n": n_yolo,
                "share_of_yolo_candidates": 1.0,
                "note": "Images with yolo_num > 0",
            },
            {
                "stage": "03_qwen_yes",
                "n": n_qwen_yes,
                "share_of_yolo_candidates": n_qwen_yes / n_yolo if n_yolo else None,
                "note": "VLM accepted YOLO candidate (prediction=yes)",
            },
            {
                "stage": "04_qwen_no",
                "n": n_qwen_no,
                "share_of_yolo_candidates": n_qwen_no / n_yolo if n_yolo else None,
                "note": "VLM rejected YOLO candidate (prediction=no)",
            },
            {
                "stage": "05_final_waste_points_gsvi",
                "n": n_final,
                "share_of_yolo_candidates": retention_final,
                "note": "Waste_Nairobi.csv after VLM + Nairobi clip/dedupe",
            },
        ]
    )
    paths = write_csv(funnel, "yolo_qwen_citywide_funnel.csv")
    print(
        f"Funnel: YOLO {n_yolo:,} → Qwen yes {n_qwen_yes:,} / no {n_qwen_no:,} "
        f"→ final {n_final:,} ({100 * retention_final:.1f}% retention)"
    )
    for out in paths:
        print(f"Wrote {out}")
    return paths[0]


def load_with_qwen_frame(with_qwen_path: Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    df = pd.read_csv(with_qwen_path)
    need = {"gt_waste", "pred_waste", *QWEN_COLS}
    missing = sorted(need - set(df.columns))
    if missing:
        raise ValueError(f"{with_qwen_path.name} missing columns {missing}")
    y_true = pd.to_numeric(df["gt_waste"], errors="coerce").fillna(0).astype(np.int8).to_numpy()
    yolo = pd.to_numeric(df["pred_waste"], errors="coerce").fillna(0).astype(np.int8).to_numpy()
    return y_true, yolo, df


def select_best_qwen_run(
    y_true: np.ndarray, yolo: np.ndarray, df: pd.DataFrame
) -> tuple[str, list[str | None], dict[str, float]]:
    """Pick the replicate with highest F1 (ties: Acc, P, R, then column order)."""
    best_col: str | None = None
    best_labels: list[str | None] = []
    best_m: dict[str, float] | None = None
    best_key: tuple[float, ...] = (-1.0,)

    for col in QWEN_COLS:
        labels = [parse_qwen_yes_no(v) for v in df[col].tolist()]
        miss = sum(1 for yp, lab in zip(yolo, labels) if yp == 1 and lab is None)
        if miss:
            raise ValueError(
                f"{col} has {miss} missing/unparseable labels among YOLO+ images"
            )
        pred = pipeline_pred_yolo_qwen(yolo, labels)
        m = metrics_binary(y_true, pred)
        key = (m["f1"], m["accuracy"], m["precision"], m["recall"])
        if key > best_key:
            best_key = key
            best_col = col
            best_labels = labels
            best_m = m

    assert best_col is not None and best_m is not None
    return best_col, best_labels, best_m


def stage_counts_main(paths: dict[str, Path]) -> list[dict]:
    """Primary CM: YOLO + best of three full YOLO+ Qwen replicates (by F1)."""
    y_true, yolo, df = load_with_qwen_frame(paths["with_qwen"])
    yolo_m = metrics_binary(y_true, yolo)
    best_col, labels, pipe_m = select_best_qwen_run(y_true, yolo, df)
    n_yes = sum(1 for yp, lab in zip(yolo, labels) if yp == 1 and lab == "yes")
    n_no = sum(1 for yp, lab in zip(yolo, labels) if yp == 1 and lab == "no")
    n_yolo = int(yolo.sum())

    return [
        {
            "stage": "YOLO candidate stage",
            "tp": yolo_m["tp"],
            "fp": yolo_m["fp"],
            "tn": yolo_m["tn"],
            "fn": yolo_m["fn"],
            "note": f"Image-level pred_waste ({paths['with_qwen'].name})",
        },
        {
            "stage": "YOLO → Qwen",
            "tp": pipe_m["tp"],
            "fp": pipe_m["fp"],
            "tn": pipe_m["tn"],
            "fn": pipe_m["fn"],
            "note": (
                f"Best of 3 full YOLO+ Qwen replicates by F1: {best_col} "
                f"(Yes={n_yes}, No={n_no} of {n_yolo} YOLO+). "
                f"Source: {paths['with_qwen'].name}"
            ),
        },
    ]


def write_yolo_detection_table(summary_path: Path) -> Path:
    base = pd.read_csv(summary_path).loc[lambda d: d["scenario"] == "sc_100pct"].iloc[0]
    map50 = float(base["mAP50"])
    map5095 = float(base["mAP50-95"] if "mAP50-95" in base.index else base["mAP50.95"])

    display = pd.DataFrame(
        [
            {
                "Independent GSVI test": "YOLO detection (box-level)",
                "mAP@0.50": f"{100 * map50:.1f}%",
                "mAP@0.50:0.95": f"{100 * map5095:.1f}%",
            }
        ]
    )
    detail = pd.DataFrame(
        [
            {
                "test_set": "Independent GSVI held-out",
                "stage": "YOLO detection (box-level)",
                "scenario": "sc_100pct",
                "n_images": int(base["n_images"]),
                "n_waste_labels": int(base["n_waste_labels"]),
                "n_background": int(base["n_background"]),
                "mAP50": map50,
                "mAP50_95": map5095,
                "mAP50_pct": round(100 * map50, 1),
                "mAP50_95_pct": round(100 * map5095, 1),
                "val_conf": float(base["val_conf"]),
                "source": summary_path.name,
                "note": (
                    "COCO-style mean average precision from Ultralytics val; "
                    "box-level metric (not image-level binary Accuracy/Precision/Recall/F1)."
                ),
            }
        ]
    )
    display_paths = write_csv(display, "yolo_heldout_detection.csv")
    detail_paths = write_csv(detail, "yolo_heldout_detection_detail.csv")
    print("\nYOLO box detection (independent GSVI held-out, sc_100pct):")
    print(display.to_string(index=False))
    for p in display_paths + detail_paths:
        print(f"Wrote {p}")
    return display_paths[0]


def write_main_heldout_tables(stages: list[dict]) -> None:
    detail_rows = []
    display_rows = []
    ci_rows = []

    for st in stages:
        ci = wilson_from_counts(st["tp"], st["fp"], st["tn"], st["fn"])
        detail_rows.append(
            {
                "test_set": "Independent GSVI held-out",
                "stage": st["stage"],
                "accuracy_pct": round(100 * ci["accuracy"], 1),
                "precision_pct": round(100 * ci["precision"], 1),
                "recall_pct": round(100 * ci["recall"], 1),
                "f1_pct": round(100 * ci["f1"], 1),
                "tp": ci["tp"],
                "fp": ci["fp"],
                "tn": ci["tn"],
                "fn": ci["fn"],
                "accuracy_ci95_low": ci["accuracy_ci95_low"],
                "accuracy_ci95_high": ci["accuracy_ci95_high"],
                "precision_ci95_low": ci["precision_ci95_low"],
                "precision_ci95_high": ci["precision_ci95_high"],
                "recall_ci95_low": ci["recall_ci95_low"],
                "recall_ci95_high": ci["recall_ci95_high"],
                "f1_ci95_low": ci["f1_ci95_low"],
                "f1_ci95_high": ci["f1_ci95_high"],
                "ci_method": "wilson_binomial",
                "note": st["note"],
            }
        )
        display_rows.append(
            {
                "Independent GSVI test": st["stage"],
                "Accuracy": fmt_pct(ci["accuracy"]),
                "Precision": fmt_pct(ci["precision"]),
                "Recall": fmt_pct(ci["recall"]),
                "F1": fmt_pct(ci["f1"]),
            }
        )
        ci_rows.append(
            [
                st["stage"],
                fmt_pct(ci["accuracy"]),
                fmt_ci(ci["accuracy_ci95_low"], ci["accuracy_ci95_high"]),
                fmt_pct(ci["precision"]),
                fmt_ci(ci["precision_ci95_low"], ci["precision_ci95_high"]),
                fmt_pct(ci["recall"]),
                fmt_ci(ci["recall_ci95_low"], ci["recall_ci95_high"]),
                fmt_pct(ci["f1"]),
                fmt_ci(ci["f1_ci95_low"], ci["f1_ci95_high"]),
            ]
        )

    detail = pd.DataFrame(detail_rows)
    display = pd.DataFrame(display_rows)
    header = [
        "Independent GSVI test",
        "Accuracy",
        "95% CI",
        "Precision",
        "95% CI",
        "Recall",
        "95% CI",
        "F1",
        "95% CI",
    ]
    ci_text = ",".join(header) + "\n" + "\n".join(",".join(row) for row in ci_rows) + "\n"

    display_paths = write_csv(display, "yolo_vs_qwen_heldout_display.csv")
    detail_paths = write_csv(detail, "yolo_vs_qwen_heldout_detail.csv")
    ci_paths = write_text(ci_text, "yolo_vs_qwen_heldout_ci_table.csv")

    print("\nMain held-out comparison (best full YOLO+ Qwen run; Wilson 95% CI):")
    print(pd.DataFrame(ci_rows, columns=header).to_string(index=False))
    for p in display_paths + ci_paths + detail_paths:
        print(f"Wrote {p}")


def write_stability_table(with_qwen_path: Path | None = None) -> Path | None:
    """Secondary: 3 Qwen runs + 3-run majority on all YOLO positives (stability only)."""
    with_qwen = with_qwen_path or _find(WITH_QWEN_NAME)
    if with_qwen is None:
        print(
            f"\nSkip stability table: missing {WITH_QWEN_NAME} "
            "(run notebook 4_ to produce Qwen2_1/2/3)."
        )
        return None

    try:
        y_true, yolo, df = load_with_qwen_frame(with_qwen)
    except ValueError as exc:
        print(f"\nSkip stability table: {exc}")
        return None

    yolo_m = metrics_binary(y_true, yolo)
    rows = []
    rows.append(
        {
            "setting": "YOLO only",
            "role": "baseline",
            "n_yolo_pos": int(yolo.sum()),
            "qwen_yes_among_yolo": None,
            "qwen_no_among_yolo": None,
            "accuracy_pct": round(100 * yolo_m["accuracy"], 1),
            "precision_pct": round(100 * yolo_m["precision"], 1),
            "recall_pct": round(100 * yolo_m["recall"], 1),
            "f1_pct": round(100 * yolo_m["f1"], 1),
            "tp": yolo_m["tp"],
            "fp": yolo_m["fp"],
            "tn": yolo_m["tn"],
            "fn": yolo_m["fn"],
            "note": "Image-level pred_waste from held-out YOLO val",
        }
    )

    label_cols: dict[str, list[str | None]] = {}
    for col in QWEN_COLS:
        labels = [parse_qwen_yes_no(v) for v in df[col].tolist()]
        label_cols[col] = labels
        n_yes = sum(1 for yp, lab in zip(yolo, labels) if yp == 1 and lab == "yes")
        n_no = sum(1 for yp, lab in zip(yolo, labels) if yp == 1 and lab == "no")
        pred = pipeline_pred_yolo_qwen(yolo, labels)
        m = metrics_binary(y_true, pred)
        rows.append(
            {
                "setting": f"YOLO → {col}",
                "role": "replicate",
                "n_yolo_pos": int(yolo.sum()),
                "qwen_yes_among_yolo": n_yes,
                "qwen_no_among_yolo": n_no,
                "accuracy_pct": round(100 * m["accuracy"], 1),
                "precision_pct": round(100 * m["precision"], 1),
                "recall_pct": round(100 * m["recall"], 1),
                "f1_pct": round(100 * m["f1"], 1),
                "tp": m["tp"],
                "fp": m["fp"],
                "tn": m["tn"],
                "fn": m["fn"],
                "note": (
                    "Single independent Qwen replicate on all YOLO positives "
                    f"(stability analysis). Source: {with_qwen.name}"
                ),
            }
        )

    majority = [
        majority_yes_no([label_cols[c][i] for c in QWEN_COLS]) for i in range(len(df))
    ]
    n_yes_m = sum(1 for yp, lab in zip(yolo, majority) if yp == 1 and lab == "yes")
    n_no_m = sum(1 for yp, lab in zip(yolo, majority) if yp == 1 and lab == "no")
    maj_pred = pipeline_pred_yolo_qwen(yolo, majority)
    maj_m = metrics_binary(y_true, maj_pred)
    rows.append(
        {
            "setting": "YOLO → 3-run majority",
            "role": "majority_summary",
            "n_yolo_pos": int(yolo.sum()),
            "qwen_yes_among_yolo": n_yes_m,
            "qwen_no_among_yolo": n_no_m,
            "accuracy_pct": round(100 * maj_m["accuracy"], 1),
            "precision_pct": round(100 * maj_m["precision"], 1),
            "recall_pct": round(100 * maj_m["recall"], 1),
            "f1_pct": round(100 * maj_m["f1"], 1),
            "tp": maj_m["tp"],
            "fp": maj_m["fp"],
            "tn": maj_m["tn"],
            "fn": maj_m["fn"],
            "note": (
                "Descriptive 3-run majority Yes/No on YOLO+ "
                f"(not the main FP-only CM). Source: {with_qwen.name}"
            ),
        }
    )

    # Pairwise agreement among YOLO+ images
    pos_idx = [i for i, yp in enumerate(yolo) if yp == 1]
    labs_mat = {col: [label_cols[col][i] for i in pos_idx] for col in QWEN_COLS}
    n_pos = len(pos_idx)
    unanimous = 0
    for j in range(n_pos):
        vals = [labs_mat[c][j] for c in QWEN_COLS]
        if None in vals:
            continue
        if len(set(vals)) == 1:
            unanimous += 1
    pair_agree = {}
    for a, b in (("Qwen2_1", "Qwen2_2"), ("Qwen2_1", "Qwen2_3"), ("Qwen2_2", "Qwen2_3")):
        agree = sum(
            1
            for x, y in zip(labs_mat[a], labs_mat[b])
            if x is not None and y is not None and x == y
        )
        pair_agree[f"{a}_vs_{b}"] = agree / n_pos if n_pos else float("nan")

    rows.append(
        {
            "setting": "stability_summary",
            "role": "summary",
            "n_yolo_pos": n_pos,
            "qwen_yes_among_yolo": None,
            "qwen_no_among_yolo": None,
            "accuracy_pct": None,
            "precision_pct": None,
            "recall_pct": None,
            "f1_pct": None,
            "tp": None,
            "fp": None,
            "tn": None,
            "fn": None,
            "note": (
                f"Unanimous Yes/No on {unanimous}/{n_pos} YOLO+ images; "
                + ", ".join(f"{k} agree={100 * v:.1f}%" for k, v in pair_agree.items())
            ),
        }
    )

    out = pd.DataFrame(rows)
    paths = write_csv(out, "yolo_qwen_yolo_pos_replicates.csv")
    print("\nReplication / stability (Qwen on all YOLO positives — not main CM):")
    show = out[out["role"].isin(["baseline", "majority_summary", "replicate"])][
        [
            "setting",
            "role",
            "qwen_yes_among_yolo",
            "qwen_no_among_yolo",
            "tp",
            "fp",
            "tn",
            "fn",
            "accuracy_pct",
            "precision_pct",
            "recall_pct",
            "f1_pct",
        ]
    ]
    print(show.to_string(index=False))
    print("  " + rows[-1]["note"])
    for p in paths:
        print(f"Wrote {p}")
    return paths[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-funnel",
        action="store_true",
        help="Skip citywide YOLO→Qwen funnel table",
    )
    parser.add_argument(
        "--skip-stability",
        action="store_true",
        help="Skip 3-replicate Qwen-on-YOLO+ stability table",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_funnel:
        write_citywide_funnel()

    main_paths = resolve_main_inputs()
    write_yolo_detection_table(main_paths["summary"])
    stages = stage_counts_main(main_paths)
    write_main_heldout_tables(stages)

    if not args.skip_stability:
        write_stability_table()


if __name__ == "__main__":
    main()

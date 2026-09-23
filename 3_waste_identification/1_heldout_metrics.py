#!/usr/bin/env python3
"""Step 3a — held-out waste-identification metrics (YOLO and YOLO + Qwen).

Independent 180-image GSVI held-out set, image-level binary task
(waste present vs background). The YOLO detector was retrained at five
shares of self-collected (SC) imagery in its training set — sc_0pct …
sc_100pct — and every model is validated on the same 180 images.

Headline results (sc_100pct, the full detector):

  1. YOLO only        image-level prediction from the held-out val run
  2. YOLO -> Qwen     a YOLO positive is kept only if Qwen2-VL also says Yes,
                      using the best of the independent Qwen replicates (highest F1)

Plus the repeated-inference stability of those replicates, and a sensitivity
table across the five SC shares.

Inputs (Data/Chapter_waste/3_waste_identification/):
  yolo/heldout_GSVI_val_summary.csv              per-scenario YOLO box mAP + counts
  yolo/heldout_GSVI_p100_image_level_predictions.csv  180 rows x 5 scenarios
  yolo/heldout_GSVI_p100_sc_<share>pct_fp_conf001.csv  YOLO false positives (Qwen inputs)
  qwen/qwen_labels_<scenario>.csv                optional Qwen replicate labels

Outputs (thesis_table/):
  table_1_yolo_detection.csv / _detail.csv    box-level mAP, all scenarios
  table_2_yolo_qwen_heldout.csv               display metrics, headline scenario
  table_2_yolo_qwen_heldout_ci.csv            + Wilson 95% CIs
  table_2_yolo_qwen_heldout_detail.csv        counts + numeric CIs (feeds the panel figure)
  table_3_qwen_replicates.csv                 replicates + majority (stability figure)
  table_4_sc_sensitivity.csv / _detail.csv    image-level metrics across SC shares
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import waste_id_dir  # noqa: E402

OUTPUT_DIR = waste_id_dir()
YOLO_DIR = OUTPUT_DIR / "yolo"
QWEN_DIR = OUTPUT_DIR / "qwen"
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"

SUMMARY_NAME = "heldout_GSVI_val_summary.csv"
PREDICTIONS_NAME = "heldout_GSVI_p100_image_level_predictions.csv"
QWEN_LABELS_GLOB = "qwen_labels_sc_*.csv"
FP_CSV_TEMPLATE = "heldout_GSVI_p100_{scenario}_fp_conf001.csv"
HEADLINE_SCENARIO = "sc_100pct"

UUID_PREFIX = re.compile(r"^[0-9a-f]{8}-", re.I)
SCENARIO_SHARE = re.compile(r"sc_(\d+)pct", re.I)


def canonical_img_name(name: object) -> str:
    """Drop the .jpg suffix and any Colab-added 8-hex-digit prefix."""
    s = str(name).strip()
    if s.lower().endswith(".jpg"):
        s = s[:-4]
    if UUID_PREFIX.match(s):
        s = s.split("-", 1)[1]
    return s


def scenario_share(scenario: str) -> int:
    m = SCENARIO_SHARE.search(str(scenario))
    return int(m.group(1)) if m else -1


def scenario_label(scenario: str) -> str:
    share = scenario_share(scenario)
    return f"{share}% self-collected" if share >= 0 else str(scenario)


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


def write_csv(df: pd.DataFrame, name: str) -> Path:
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    df.to_csv(path, index=False)
    print(f"Wrote {path}")
    return path


def write_text(text: str, name: str) -> Path:
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}")
    return path


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_summary() -> pd.DataFrame:
    path = YOLO_DIR / SUMMARY_NAME
    if not path.exists():
        raise FileNotFoundError(f"Missing YOLO val summary: {path}")
    df = pd.read_csv(path)
    df = df.rename(columns={"mAP50.95": "mAP50-95"})
    df["sc_share_pct"] = df["scenario"].map(scenario_share)
    return df.sort_values("sc_share_pct").reset_index(drop=True)


def load_predictions() -> pd.DataFrame:
    """Image-level YOLO predictions, one row per image x scenario."""
    path = YOLO_DIR / PREDICTIONS_NAME
    if not path.exists():
        raise FileNotFoundError(f"Missing image-level predictions: {path}")
    df = pd.read_csv(path)
    need = {"image_name", "ground_truth", "prediction", "scenario"}
    missing = sorted(need - set(df.columns))
    if missing:
        raise ValueError(f"{path.name} missing columns {missing}")
    df["img_key"] = df["image_name"].map(canonical_img_name)
    df["gt_waste"] = pd.to_numeric(df["ground_truth"], errors="coerce").fillna(0).astype(np.int8)
    df["pred_waste"] = pd.to_numeric(df["prediction"], errors="coerce").fillna(0).astype(np.int8)
    df["sc_share_pct"] = df["scenario"].map(scenario_share)
    return df


def load_qwen_labels() -> dict[str, tuple[pd.DataFrame, list[str]]]:
    """{scenario: (labels keyed by img_key, replicate column names)} for every
    qwen/qwen_labels_sc_*.csv present. Scenarios without a file get YOLO-only rows."""
    out: dict[str, tuple[pd.DataFrame, list[str]]] = {}
    if not QWEN_DIR.is_dir():
        return out
    for path in sorted(QWEN_DIR.glob(QWEN_LABELS_GLOB)):
        df = pd.read_csv(path)
        if "image_name" not in df.columns:
            print(f"  skip {path.name}: no image_name column")
            continue
        scenario = (
            str(df["scenario"].iloc[0])
            if "scenario" in df.columns and len(df)
            else path.stem.replace("qwen_labels_", "")
        )
        replicates = [c for c in df.columns if c not in {"image_name", "scenario"}]
        if not replicates:
            print(f"  skip {path.name}: no replicate columns")
            continue
        df = df.copy()
        df["img_key"] = df["image_name"].map(canonical_img_name)
        out[scenario] = (df.set_index("img_key"), replicates)
    return out


def fp_csv_path(scenario: str) -> Path:
    return YOLO_DIR / FP_CSV_TEMPLATE.format(scenario=scenario)


# ---------------------------------------------------------------------------
# YOLO -> Qwen cascade
# ---------------------------------------------------------------------------
def qwen_vote_frame(
    preds: pd.DataFrame, labels: pd.DataFrame, replicates: list[str]
) -> pd.DataFrame:
    """Attach parsed yes/no votes for each replicate to the scenario's predictions."""
    out = preds.copy()
    for col in replicates:
        mapped = out["img_key"].map(labels[col])
        out[col] = [parse_qwen_yes_no(v) for v in mapped]
    return out


def cascade_pred(yolo: np.ndarray, votes: list[str | None]) -> np.ndarray:
    """Final prediction = YOLO positive AND Qwen Yes."""
    return np.array(
        [1 if yp == 1 and v == "yes" else 0 for yp, v in zip(yolo, votes)],
        dtype=np.int8,
    )


def majority_yes_no(labels: list[str | None]) -> str | None:
    """Majority Yes/No; None if fewer than 2 valid votes or a tie."""
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


def check_vote_coverage(frame: pd.DataFrame, replicates: list[str], scenario: str) -> None:
    yolo_pos = frame["pred_waste"].to_numpy() == 1
    for col in replicates:
        miss = int(sum(1 for keep, v in zip(yolo_pos, frame[col]) if keep and v is None))
        if miss:
            raise ValueError(
                f"{scenario}: {col} has {miss} missing/unparseable labels among "
                f"{int(yolo_pos.sum())} YOLO-positive images"
            )


def best_replicate(frame: pd.DataFrame, replicates: list[str]) -> tuple[str, dict[str, float]]:
    """Replicate with the highest F1 (ties: accuracy, precision, recall, column order)."""
    y_true = frame["gt_waste"].to_numpy()
    yolo = frame["pred_waste"].to_numpy()
    best_col = replicates[0]
    best_m = metrics_binary(y_true, cascade_pred(yolo, frame[best_col].tolist()))
    best_key = (best_m["f1"], best_m["accuracy"], best_m["precision"], best_m["recall"])
    for col in replicates[1:]:
        m = metrics_binary(y_true, cascade_pred(yolo, frame[col].tolist()))
        key = (m["f1"], m["accuracy"], m["precision"], m["recall"])
        if key > best_key:
            best_col, best_m, best_key = col, m, key
    return best_col, best_m


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def write_yolo_detection_table(summary: pd.DataFrame, headline: str) -> None:
    """table_1 — box-level mAP for every SC share, headline scenario flagged."""
    display_rows = []
    detail_rows = []
    for _, row in summary.iterrows():
        map50 = float(row["mAP50"])
        map5095 = float(row["mAP50-95"])
        is_headline = row["scenario"] == headline
        display_rows.append(
            {
                "YOLO training set": scenario_label(row["scenario"])
                + (" (headline)" if is_headline else ""),
                "mAP@0.50": f"{100 * map50:.1f}%",
                "mAP@0.50:0.95": f"{100 * map5095:.1f}%",
            }
        )
        detail_rows.append(
            {
                "test_set": "Independent GSVI held-out",
                "stage": "YOLO detection (box-level)",
                "scenario": row["scenario"],
                "sc_share_pct": int(row["sc_share_pct"]),
                "headline": bool(is_headline),
                "n_images": int(row["n_images"]),
                "n_waste_labels": int(row["n_waste_labels"]),
                "n_background": int(row["n_background"]),
                "mAP50": map50,
                "mAP50_95": map5095,
                "mAP50_pct": round(100 * map50, 1),
                "mAP50_95_pct": round(100 * map5095, 1),
                "val_conf": float(row["val_conf"]),
                "source": SUMMARY_NAME,
                "note": (
                    "COCO-style mean average precision from Ultralytics val; "
                    "box-level metric (not image-level binary Accuracy/Precision/Recall/F1)."
                ),
            }
        )

    display = pd.DataFrame(display_rows)
    print("\nYOLO box detection (independent GSVI held-out, by SC share of training set):")
    print(display.to_string(index=False))
    write_csv(display, "table_1_yolo_detection.csv")
    write_csv(pd.DataFrame(detail_rows), "table_1_yolo_detection_detail.csv")


def headline_stages(
    preds: pd.DataFrame,
    qwen: dict[str, tuple[pd.DataFrame, list[str]]],
    headline: str,
) -> list[dict]:
    """YOLO and YOLO -> Qwen confusion counts for the headline scenario."""
    frame = preds[preds["scenario"] == headline].copy()
    if frame.empty:
        raise ValueError(f"No predictions for headline scenario {headline!r}")
    y_true = frame["gt_waste"].to_numpy()
    yolo = frame["pred_waste"].to_numpy()
    yolo_m = metrics_binary(y_true, yolo)

    stages = [
        {
            "stage": "YOLO candidate stage",
            **{k: yolo_m[k] for k in ("tp", "fp", "tn", "fn")},
            "note": f"Image-level prediction, {headline} ({PREDICTIONS_NAME})",
        }
    ]

    if headline not in qwen:
        print(
            f"\nNo Qwen labels for {headline}: expected "
            f"{QWEN_DIR / f'qwen_labels_{headline}.csv'} — YOLO stage only."
        )
        return stages

    labels, replicates = qwen[headline]
    voted = qwen_vote_frame(frame, labels, replicates)
    check_vote_coverage(voted, replicates, headline)
    best_col, pipe_m = best_replicate(voted, replicates)
    votes = voted[best_col].tolist()
    n_yes = sum(1 for yp, v in zip(yolo, votes) if yp == 1 and v == "yes")
    n_no = sum(1 for yp, v in zip(yolo, votes) if yp == 1 and v == "no")

    stages.append(
        {
            "stage": "YOLO → Qwen",
            **{k: pipe_m[k] for k in ("tp", "fp", "tn", "fn")},
            "note": (
                f"Best of {len(replicates)} Qwen replicates by F1: {best_col} "
                f"(Yes={n_yes}, No={n_no} of {int(yolo.sum())} YOLO+). "
                f"Source: qwen_labels_{headline}.csv"
            ),
        }
    )
    return stages


def write_main_heldout_tables(stages: list[dict]) -> None:
    """table_2 — display, Wilson-CI and detail views of the headline comparison."""
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

    print("\nMain held-out comparison (best Qwen replicate; Wilson 95% CI):")
    print(pd.DataFrame(ci_rows, columns=header).to_string(index=False))
    write_csv(pd.DataFrame(display_rows), "table_2_yolo_qwen_heldout.csv")
    write_text(ci_text, "table_2_yolo_qwen_heldout_ci.csv")
    write_csv(pd.DataFrame(detail_rows), "table_2_yolo_qwen_heldout_detail.csv")


def write_stability_table(
    preds: pd.DataFrame,
    qwen: dict[str, tuple[pd.DataFrame, list[str]]],
    headline: str,
) -> None:
    """table_3 — each Qwen replicate plus their majority vote, on all YOLO positives."""
    if headline not in qwen:
        print(f"\nSkip stability table: no Qwen labels for {headline}.")
        return

    frame = preds[preds["scenario"] == headline].copy()
    labels, replicates = qwen[headline]
    voted = qwen_vote_frame(frame, labels, replicates)
    check_vote_coverage(voted, replicates, headline)

    y_true = voted["gt_waste"].to_numpy()
    yolo = voted["pred_waste"].to_numpy()
    n_yolo = int(yolo.sum())
    source = f"qwen_labels_{headline}.csv"

    yolo_m = metrics_binary(y_true, yolo)
    rows = [
        {
            "setting": "YOLO only",
            "role": "baseline",
            "n_yolo_pos": n_yolo,
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
            "note": f"Image-level prediction from the held-out YOLO val run ({headline})",
        }
    ]

    for col in replicates:
        votes = voted[col].tolist()
        n_yes = sum(1 for yp, v in zip(yolo, votes) if yp == 1 and v == "yes")
        n_no = sum(1 for yp, v in zip(yolo, votes) if yp == 1 and v == "no")
        m = metrics_binary(y_true, cascade_pred(yolo, votes))
        rows.append(
            {
                "setting": f"YOLO → {col}",
                "role": "replicate",
                "n_yolo_pos": n_yolo,
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
                    f"(stability analysis). Source: {source}"
                ),
            }
        )

    majority = [
        majority_yes_no([voted[c].iloc[i] for c in replicates]) for i in range(len(voted))
    ]
    n_yes_m = sum(1 for yp, v in zip(yolo, majority) if yp == 1 and v == "yes")
    n_no_m = sum(1 for yp, v in zip(yolo, majority) if yp == 1 and v == "no")
    maj_m = metrics_binary(y_true, cascade_pred(yolo, majority))
    rows.append(
        {
            "setting": f"YOLO → {len(replicates)}-run majority",
            "role": "majority_summary",
            "n_yolo_pos": n_yolo,
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
                f"Descriptive {len(replicates)}-run majority Yes/No on YOLO+ "
                f"(not the headline cascade). Source: {source}"
            ),
        }
    )

    # Agreement among the replicates, over YOLO-positive images only
    pos = voted[voted["pred_waste"] == 1]
    n_pos = len(pos)
    unanimous = sum(
        1
        for _, r in pos.iterrows()
        if None not in [r[c] for c in replicates] and len(set(r[c] for c in replicates)) == 1
    )
    pair_agree = {}
    for i, a in enumerate(replicates):
        for b in replicates[i + 1 :]:
            agree = sum(
                1
                for x, y in zip(pos[a], pos[b])
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
    print("\nReplication / stability (Qwen on all YOLO positives — not the headline CM):")
    print(
        out[out["role"].isin(["baseline", "replicate", "majority_summary"])][
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
        ].to_string(index=False)
    )
    print("  " + rows[-1]["note"])
    write_csv(out, "table_3_qwen_replicates.csv")


def write_sc_sensitivity_table(
    preds: pd.DataFrame,
    summary: pd.DataFrame,
    qwen: dict[str, tuple[pd.DataFrame, list[str]]],
) -> None:
    """table_4 — image-level metrics at each SC share, YOLO and (where labelled) YOLO -> Qwen."""
    map_by_scenario = summary.set_index("scenario")
    display_rows = []
    detail_rows = []

    for scenario in summary["scenario"]:
        frame = preds[preds["scenario"] == scenario].copy()
        if frame.empty:
            continue
        y_true = frame["gt_waste"].to_numpy()
        yolo = frame["pred_waste"].to_numpy()
        n_fp_images = int(sum((y_true == 0) & (yolo == 1)))
        fp_csv = fp_csv_path(scenario)

        variants: list[tuple[str, dict[str, float], str]] = [
            (
                "YOLO only",
                metrics_binary(y_true, yolo),
                f"Image-level prediction ({PREDICTIONS_NAME})",
            )
        ]
        if scenario in qwen:
            labels, replicates = qwen[scenario]
            voted = qwen_vote_frame(frame, labels, replicates)
            check_vote_coverage(voted, replicates, scenario)
            best_col, pipe_m = best_replicate(voted, replicates)
            variants.append(
                (
                    "YOLO → Qwen",
                    pipe_m,
                    f"Best of {len(replicates)} replicates by F1: {best_col} "
                    f"(qwen_labels_{scenario}.csv)",
                )
            )
            qwen_status = f"{len(replicates)} replicate(s)"
        else:
            qwen_status = (
                f"pending — {n_fp_images} false positives in {fp_csv.name}"
                if fp_csv.exists()
                else "pending"
            )

        for stage, m, note in variants:
            ci = wilson_from_counts(m["tp"], m["fp"], m["tn"], m["fn"])
            display_rows.append(
                {
                    "YOLO training set": scenario_label(scenario),
                    "Stage": stage,
                    "Accuracy": fmt_pct(ci["accuracy"]),
                    "Precision": fmt_pct(ci["precision"]),
                    "Recall": fmt_pct(ci["recall"]),
                    "F1": fmt_pct(ci["f1"]),
                    "mAP@0.50": f"{100 * float(map_by_scenario.loc[scenario, 'mAP50']):.1f}%"
                    if stage == "YOLO only"
                    else "",
                    "Qwen": qwen_status if stage == "YOLO only" else "",
                }
            )
            detail_rows.append(
                {
                    "test_set": "Independent GSVI held-out",
                    "scenario": scenario,
                    "sc_share_pct": scenario_share(scenario),
                    "stage": stage,
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
                    "map50": float(map_by_scenario.loc[scenario, "mAP50"]),
                    "map50_95": float(map_by_scenario.loc[scenario, "mAP50-95"]),
                    "n_yolo_fp_images": n_fp_images,
                    "qwen_status": qwen_status,
                    "ci_method": "wilson_binomial",
                    "note": note,
                }
            )

    display = pd.DataFrame(display_rows)
    print("\nSensitivity to the self-collected share of the YOLO training set:")
    print(display.to_string(index=False))
    write_csv(display, "table_4_sc_sensitivity.csv")
    write_csv(pd.DataFrame(detail_rows), "table_4_sc_sensitivity_detail.csv")


def check_summary_consistency(preds: pd.DataFrame, summary: pd.DataFrame) -> None:
    """The per-image predictions must reproduce the counts in the YOLO val summary."""
    for _, row in summary.iterrows():
        frame = preds[preds["scenario"] == row["scenario"]]
        if frame.empty:
            print(f"  ! no per-image predictions for {row['scenario']}")
            continue
        m = metrics_binary(frame["gt_waste"].to_numpy(), frame["pred_waste"].to_numpy())
        mismatch = [k for k in ("tp", "fp", "tn", "fn") if m[k] != int(row[k])]
        if mismatch:
            print(
                f"  ! {row['scenario']}: {mismatch} differ from {SUMMARY_NAME} "
                f"(images {[m[k] for k in mismatch]} vs summary {[int(row[k]) for k in mismatch]})"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        default=HEADLINE_SCENARIO,
        help=f"Headline YOLO training scenario (default: {HEADLINE_SCENARIO})",
    )
    args = parser.parse_args()

    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)

    summary = load_summary()
    preds = load_predictions()
    qwen = load_qwen_labels()
    print(
        f"Read {len(summary)} scenarios from {YOLO_DIR.name}/ "
        f"({', '.join(summary['scenario'])}); Qwen labels for "
        f"{', '.join(sorted(qwen)) if qwen else 'none'}"
    )
    check_summary_consistency(preds, summary)

    write_yolo_detection_table(summary, args.scenario)
    write_main_heldout_tables(headline_stages(preds, qwen, args.scenario))
    write_stability_table(preds, qwen, args.scenario)
    write_sc_sensitivity_table(preds, summary, qwen)


if __name__ == "__main__":
    main()

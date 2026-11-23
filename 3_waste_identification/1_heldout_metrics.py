#!/usr/bin/env python3
"""Step 3a — held-out waste-identification metrics (YOLO and YOLO + Qwen).

Independent 180-image GSVI held-out set, image-level binary task
(waste present vs background). The YOLO detector was retrained at five
shares of self-collected (SC) imagery in its training set — sc_0pct …
sc_100pct — and every model is validated on the same 180 images.

Headline results (sc_100pct, the full detector):

  1. YOLO only        image-level prediction from the held-out val run
  2. YOLO -> Qwen     a YOLO positive is kept only if Qwen2-VL also says Yes;
                      each metric is computed per Qwen replicate and averaged
                      (a single-pass scenario is its one run)

95% intervals: one paired percentile bootstrap over panoramas, the units the
held-out set was drawn by (B = 10,000, fixed seed; waste and background
panoramas resampled within class, each bringing all its views). Each resample
keeps an image's ground truth, YOLO prediction and every cascade run together,
and cascade metrics are re-averaged over runs within it. The intervals describe
sampling uncertainty conditional on the observed runs; the run range is
reported separately. Paired cascade-minus-YOLO differences
come from the same replicates.

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
  table_2_yolo_qwen_heldout_ci.csv            + bootstrap 95% CIs
  table_2_yolo_qwen_heldout_detail.csv        counts + numeric CIs + run range (feeds the panel figure)
  table_2_yolo_qwen_heldout_diff.csv          paired cascade - YOLO differences with 95% CIs
  table_3_qwen_replicates.csv                 replicates + majority (stability figure)
  table_4_sc_sensitivity.csv / _detail.csv    image-level metrics across SC shares
"""

from __future__ import annotations

import argparse
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

METRICS = ("accuracy", "precision", "recall", "f1")
BOOT_B = 10_000
BOOT_SEED = 20261123
CI_METHOD = f"class_stratified_panorama_paired_percentile_bootstrap_B{BOOT_B}"

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


def metrics_from_counts(tp, fp, tn, fn) -> dict[str, np.ndarray]:
    """Accuracy / precision / recall / F1 from confusion counts (scalars or arrays).

    An undefined ratio (empty denominator) is 0. F1 is written as
    2TP / (2TP + FP + FN), which equals 2PR / (P + R) whenever that is defined.
    """
    tp, fp, tn, fn = (np.asarray(x, dtype=float) for x in (tp, fp, tn, fn))

    def ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
        return np.divide(num, den, out=np.zeros_like(num), where=den > 0)

    return {
        "accuracy": ratio(tp + tn, tp + fp + tn + fn),
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def metrics_binary(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Confusion counts and the four metrics for one set of predictions."""
    counts = {
        "tp": int(np.sum((y_true == 1) & (y_pred == 1))),
        "fp": int(np.sum((y_true == 0) & (y_pred == 1))),
        "tn": int(np.sum((y_true == 0) & (y_pred == 0))),
        "fn": int(np.sum((y_true == 1) & (y_pred == 0))),
    }
    return {**{m: float(v) for m, v in metrics_from_counts(**counts).items()}, **counts}


def stage_metrics(
    y_true: np.ndarray, preds: np.ndarray, weights: np.ndarray | None = None
) -> tuple[dict[str, np.ndarray], list[dict[str, np.ndarray]]]:
    """Metrics of one stage, computed per run and then averaged over runs.

    preds is (n_images, n_runs): one column per run (a single column for YOLO).
    weights, an (n_boot, n_images) array of how many times each image appears
    in each bootstrap replicate, gives one value per replicate; the same weights
    apply to y_true and to every run, so the runs stay paired.
    Returns (run-mean metrics, per-run metrics).
    """
    w = np.ones(len(y_true)) if weights is None else weights
    runs = []
    for j in range(preds.shape[1]):
        p = preds[:, j]
        runs.append(
            metrics_from_counts(
                (w * ((y_true == 1) & (p == 1))).sum(axis=-1),
                (w * ((y_true == 0) & (p == 1))).sum(axis=-1),
                (w * ((y_true == 0) & (p == 0))).sum(axis=-1),
                (w * ((y_true == 1) & (p == 0))).sum(axis=-1),
            )
        )
    mean = {m: np.mean([r[m] for r in runs], axis=0) for m in METRICS}
    return mean, runs


def panorama_ids(frame: pd.DataFrame) -> np.ndarray:
    """Panorama of each image: the img_key without its trailing _<heading>."""
    return frame["img_key"].str.rsplit("_", n=1).str[0].to_numpy()


def bootstrap_weights(
    y_true: np.ndarray, panoramas: np.ndarray, n_boot: int = BOOT_B, seed: int = BOOT_SEED
) -> np.ndarray:
    """(n_boot, n_images) resampling weights from a panorama-level bootstrap.

    The held-out set was drawn by panorama, and most panoramas contribute two
    views, so panoramas, not images, are the independent units. Each replicate
    draws panoramas with replacement within class (every panorama is all-waste
    or all-background), keeping the number of waste and background panoramas
    fixed; every view of a drawn panorama comes with it.
    """
    codes, _ = pd.factorize(panoramas)
    n_pan = codes.max() + 1
    pan_class = np.full(n_pan, -1)
    for c, y in zip(codes, y_true):
        if pan_class[c] not in (-1, y):
            raise ValueError("A held-out panorama mixes waste and background images")
        pan_class[c] = y
    rng = np.random.default_rng(seed)
    pan_counts = np.zeros((n_boot, n_pan))
    for cls in (1, 0):
        members = np.flatnonzero(pan_class == cls)
        draws = rng.choice(members, size=(n_boot, len(members)), replace=True)
        for b in range(n_boot):
            pan_counts[b] += np.bincount(draws[b], minlength=n_pan)
    return pan_counts[:, codes]


def percentile_ci(draws: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def evaluate_stage(
    y_true: np.ndarray, preds: np.ndarray, weights: np.ndarray
) -> tuple[dict[str, float], dict[str, np.ndarray]]:
    """Point metrics (mean of per-run values), their bootstrap 95% intervals and
    the run range, plus the bootstrap draws (for paired differences)."""
    point, runs = stage_metrics(y_true, preds)
    draws, _ = stage_metrics(y_true, preds, weights)
    out: dict[str, float] = {}
    for m in METRICS:
        out[m] = float(point[m])
        out[f"{m}_ci95_low"], out[f"{m}_ci95_high"] = percentile_ci(draws[m])
        out[f"{m}_run_min"] = float(min(r[m] for r in runs))
        out[f"{m}_run_max"] = float(max(r[m] for r in runs))
    return out, draws


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


def cascade_runs(
    frame: pd.DataFrame, replicates: list[str]
) -> tuple[np.ndarray, list[dict[str, float]]]:
    """Cascade predictions for every Qwen replicate, (n_images, n_runs), and
    each run's metrics and confusion counts.

    The reported cascade result is the arithmetic mean of the per-run metrics
    (stage_metrics); the mean confusion counts are kept only to draw the
    confusion matrix. With one replicate this is that run.
    """
    y_true = frame["gt_waste"].to_numpy()
    yolo = frame["pred_waste"].to_numpy()
    preds = np.column_stack([cascade_pred(yolo, frame[c].tolist()) for c in replicates])
    runs = [metrics_binary(y_true, preds[:, j]) for j in range(preds.shape[1])]
    return preds, runs


def mean_counts(runs: list[dict[str, float]]) -> dict[str, float]:
    return {k: float(np.mean([r[k] for r in runs])) for k in ("tp", "fp", "tn", "fn")}


def replicate_note(replicates: list[str], runs: list[dict[str, float]]) -> str:
    if len(runs) == 1:
        return f"single Qwen pass ({replicates[0]})"
    f1s = " / ".join(f"{100 * r['f1']:.1f}" for r in runs)
    return f"mean of {len(runs)} Qwen replicates (per-run F1 {f1s}%)"


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
    """YOLO and YOLO -> Qwen predictions for the headline scenario, on the same
    images in the same order (the bootstrap resamples them together)."""
    frame = preds[preds["scenario"] == headline].copy()
    if frame.empty:
        raise ValueError(f"No predictions for headline scenario {headline!r}")
    y_true = frame["gt_waste"].to_numpy()
    yolo = frame["pred_waste"].to_numpy()
    yolo_m = metrics_binary(y_true, yolo)

    stages = [
        {
            "stage": "YOLO candidate stage",
            "y_true": y_true,
            "panoramas": panorama_ids(frame),
            "preds": yolo.reshape(-1, 1),
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
    pipe_preds, runs = cascade_runs(voted, replicates)

    stages.append(
        {
            "stage": "YOLO → Qwen",
            "y_true": y_true,
            "panoramas": panorama_ids(frame),
            "preds": pipe_preds,
            **mean_counts(runs),
            "note": (
                f"{headline}: {replicate_note(replicates, runs)} "
                f"on {int(yolo.sum())} YOLO+. Source: qwen_labels_{headline}.csv"
            ),
        }
    )
    return stages


def write_main_heldout_tables(stages: list[dict]) -> None:
    """table_2 — display, CI, detail and paired-difference views of the headline
    comparison.

    95% intervals are percentile intervals from one class-stratified, paired
    panorama bootstrap (bootstrap_weights): every stage and every Qwen run is
    scored on the same resampled panoramas, and cascade metrics are averaged
    over runs within each replicate. They describe sampling uncertainty
    conditional on the observed runs, not run-to-run variation, which is
    reported separately as the run range.
    """
    detail_rows = []
    display_rows = []
    ci_rows = []
    draws_by_stage: dict[str, dict[str, np.ndarray]] = {}
    point_by_stage: dict[str, dict[str, float]] = {}

    weights = bootstrap_weights(stages[0]["y_true"], stages[0]["panoramas"])
    n_images = len(stages[0]["y_true"])
    n_pos = int(stages[0]["y_true"].sum())

    for st in stages:
        if not np.array_equal(st["y_true"], stages[0]["y_true"]):
            raise ValueError("Stages must be scored on the same images in the same order")
        ci, draws = evaluate_stage(st["y_true"], st["preds"], weights)
        draws_by_stage[st["stage"]] = draws
        point_by_stage[st["stage"]] = ci
        detail_rows.append(
            {
                "test_set": "Independent GSVI held-out",
                "stage": st["stage"],
                "n_images": n_images,
                "n_waste": n_pos,
                "n_panoramas": int(pd.unique(stages[0]["panoramas"]).size),
                "n_runs": int(st["preds"].shape[1]),
                **{f"{m}_pct": round(100 * ci[m], 1) for m in METRICS},
                **{m: ci[m] for m in METRICS},
                "tp": round(st["tp"], 2),
                "fp": round(st["fp"], 2),
                "tn": round(st["tn"], 2),
                "fn": round(st["fn"], 2),
                **{
                    f"{m}_{s}": ci[f"{m}_{s}"]
                    for m in METRICS
                    for s in ("ci95_low", "ci95_high", "run_min", "run_max")
                },
                "ci_method": CI_METHOD,
                "boot_seed": BOOT_SEED,
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
    ci_table = pd.DataFrame(ci_rows, columns=header)

    print(
        "\nMain held-out comparison (Qwen = mean of per-run metrics; class-stratified "
        f"paired panorama bootstrap 95% CI, B = {BOOT_B}):"
    )
    print(ci_table.to_string(index=False))
    write_csv(pd.DataFrame(display_rows), "table_2_yolo_qwen_heldout.csv")
    write_csv(ci_table, "table_2_yolo_qwen_heldout_ci.csv")
    write_csv(pd.DataFrame(detail_rows), "table_2_yolo_qwen_heldout_detail.csv")

    # Paired differences, cascade minus YOLO, on the same bootstrap replicates
    if len(stages) < 2:
        return
    base, comp = stages[0]["stage"], stages[1]["stage"]
    diff_rows = []
    for m in METRICS:
        d = draws_by_stage[comp][m] - draws_by_stage[base][m]
        lo, hi = percentile_ci(d)
        diff_rows.append(
            {
                "metric": m,
                "comparison": f"{comp} minus {base}",
                "baseline_pct": round(100 * point_by_stage[base][m], 1),
                "comparison_pct": round(100 * point_by_stage[comp][m], 1),
                "difference_pp": round(100 * (point_by_stage[comp][m] - point_by_stage[base][m]), 1),
                "difference_ci95_low_pp": round(100 * lo, 1),
                "difference_ci95_high_pp": round(100 * hi, 1),
                "share_boot_above_0": float(np.mean(d > 0)),
                "ci_method": CI_METHOD,
                "boot_seed": BOOT_SEED,
            }
        )
    diff = pd.DataFrame(diff_rows)
    print("\nPaired differences (percentage points, same bootstrap replicates):")
    print(
        diff[
            ["metric", "baseline_pct", "comparison_pct", "difference_pp",
             "difference_ci95_low_pp", "difference_ci95_high_pp"]
        ].to_string(index=False)
    )
    write_csv(diff, "table_2_yolo_qwen_heldout_diff.csv")


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

    def row(setting: str, role: str, votes: list[str | None] | None, note: str) -> dict:
        """One table_3 row: YOLO alone (votes None) or YOLO filtered by these votes."""
        pred = yolo if votes is None else cascade_pred(yolo, votes)
        m = metrics_binary(y_true, pred)

        def among_yolo(label: str) -> int | None:
            if votes is None:
                return None
            return sum(1 for yp, v in zip(yolo, votes) if yp == 1 and v == label)

        return {
            "setting": setting,
            "role": role,
            "n_yolo_pos": n_yolo,
            "qwen_yes_among_yolo": among_yolo("yes"),
            "qwen_no_among_yolo": among_yolo("no"),
            **{f"{k}_pct": round(100 * m[k], 1) for k in METRICS},
            **{k: m[k] for k in ("tp", "fp", "tn", "fn")},
            "note": note,
        }

    majority = [
        majority_yes_no([voted[c].iloc[i] for c in replicates]) for i in range(len(voted))
    ]
    rows = [
        row("YOLO only", "baseline", None,
            f"Image-level prediction from the held-out YOLO val run ({headline})"),
        *(
            row(f"YOLO → {col}", "replicate", voted[col].tolist(),
                "Single independent Qwen replicate on all YOLO positives "
                f"(stability analysis). Source: {source}")
            for col in replicates
        ),
        row(f"YOLO → {len(replicates)}-run majority", "majority_summary", majority,
            f"Descriptive {len(replicates)}-run majority Yes/No on YOLO+ "
            f"(not the headline cascade). Source: {source}"),
    ]

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

        weights = bootstrap_weights(y_true, panorama_ids(frame))
        variants: list[tuple[str, np.ndarray, dict[str, float], str]] = [
            (
                "YOLO only",
                yolo.reshape(-1, 1),
                metrics_binary(y_true, yolo),
                f"Image-level prediction ({PREDICTIONS_NAME})",
            )
        ]
        if scenario in qwen:
            labels, replicates = qwen[scenario]
            voted = qwen_vote_frame(frame, labels, replicates)
            check_vote_coverage(voted, replicates, scenario)
            pipe_preds, runs = cascade_runs(voted, replicates)
            variants.append(
                (
                    "YOLO → Qwen",
                    pipe_preds,
                    mean_counts(runs),
                    f"{scenario}: {replicate_note(replicates, runs)} "
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

        for stage, stage_preds, m, note in variants:
            ci, _ = evaluate_stage(y_true, stage_preds, weights)
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
                    "tp": round(m["tp"], 2),
                    "fp": round(m["fp"], 2),
                    "tn": round(m["tn"], 2),
                    "fn": round(m["fn"], 2),
                    **{
                        f"{k}_{s}": ci[f"{k}_{s}"]
                        for k in METRICS
                        for s in ("ci95_low", "ci95_high", "run_min", "run_max")
                    },
                    "map50": float(map_by_scenario.loc[scenario, "mAP50"]),
                    "map50_95": float(map_by_scenario.loc[scenario, "mAP50-95"]),
                    "n_yolo_fp_images": n_fp_images,
                    "qwen_status": qwen_status,
                    "ci_method": CI_METHOD,
                    "boot_seed": BOOT_SEED,
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

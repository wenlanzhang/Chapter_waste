#!/usr/bin/env python3
"""One-shot Step 7 regenerate: stage inputs → thesis tables → figures.

Usage:
  python 7_heldout_validation/0_run_all.py
  python 7_heldout_validation/0_run_all.py --skip-plots
  python 7_heldout_validation/0_run_all.py --skip-funnel
  python 7_heldout_validation/0_run_all.py --skip-stability
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from paths import (
    ARCHIVE_OUTPUT_DIR,
    ARCHIVE_VALIDATION_DIR,
    HELDOUT_IMAGES_CSV,
    HELDOUT_UNITS_CSV,
    OUTPUT_DIR,
    REPO_ROOT,
    THESIS_TABLE_DIR,
    TRAINING_CSV,
    TRAINING_CSV_STEP6,
    VALIDATION_DIR,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SUMMARY_NAME = "heldout_GSVI_p100_val_summary.csv"
SC_SUMMARY_NAME = "heldout_val_summary.csv"
FP_CSV_NAME = "heldout_GSVI_p100_sc100pct_fp_conf001.csv"
FP_DIR_NAME = "heldout_GSVI_p100_sc100pct_fp_conf001"
QWEN_FP_NAME = "qwen2_vl_72b_segmind_results.csv"
WITH_QWEN_NAME = "heldout_GSVI_p100_image_level_predictions_with_qwen.csv"

LEGACY_OUTPUTS = [
    "yolo_vs_qwen_heldout.csv",
    "yolo_vs_qwen_heldout_bootstrap_ci.csv",
    "yolo_qwen_citywide_funnel.csv",
    "yolo_qwen_citywide_funnel_summary.csv",
    "heldout_performance_with_ci.csv",
    "test_design.csv",
    "training_mixes.csv",
]


def _copy_if_missing(src: Path, dst: Path) -> None:
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Staged: {dst.name}")


def stage_inputs() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    flat_qwen = VALIDATION_DIR / QWEN_FP_NAME
    nested_qwen = VALIDATION_DIR / FP_DIR_NAME / QWEN_FP_NAME
    if flat_qwen.exists():
        nested_qwen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(flat_qwen, nested_qwen)
    elif nested_qwen.exists() and not flat_qwen.exists():
        shutil.copy2(nested_qwen, flat_qwen)

    _copy_if_missing(ARCHIVE_VALIDATION_DIR / SC_SUMMARY_NAME, VALIDATION_DIR / SC_SUMMARY_NAME)
    _copy_if_missing(
        ARCHIVE_OUTPUT_DIR / "Train0315_695_held_out_gsvi_p100_test.csv",
        HELDOUT_IMAGES_CSV,
    )
    _copy_if_missing(
        ARCHIVE_OUTPUT_DIR / "held_out_gsvi_p100_test_units.csv",
        HELDOUT_UNITS_CSV,
    )
    if not TRAINING_CSV.exists() and TRAINING_CSV_STEP6.exists():
        shutil.copy2(TRAINING_CSV_STEP6, TRAINING_CSV)
        print(f"Staged: {TRAINING_CSV.name}")


def preflight() -> None:
    summary_path = VALIDATION_DIR / SUMMARY_NAME
    with_qwen = VALIDATION_DIR / WITH_QWEN_NAME
    for path in (summary_path, with_qwen):
        if not path.exists():
            raise FileNotFoundError(f"Missing Validation input: {path}")

    base = pd.read_csv(summary_path).loc[lambda d: d["scenario"] == "sc_100pct"].iloc[0]
    df = pd.read_csv(with_qwen)
    need = {"gt_waste", "pred_waste", "Qwen2_1", "Qwen2_2", "Qwen2_3"}
    missing = sorted(need - set(df.columns))
    if missing:
        raise RuntimeError(f"{with_qwen.name} missing columns: {missing}")
    n_yolo = int(pd.to_numeric(df["pred_waste"], errors="coerce").fillna(0).gt(0).sum())
    print(
        f"Preflight sc_100pct (main CM = best full YOLO+ Qwen run): "
        f"summary tp={int(base['tp'])} fp={int(base['fp'])} "
        f"tn={int(base['tn'])} fn={int(base['fn'])} val_conf={base.get('val_conf')}"
    )
    print(f"  {with_qwen.name}: n={len(df)}, YOLO+={n_yolo}")
    if not HELDOUT_IMAGES_CSV.exists():
        raise FileNotFoundError(f"Missing held-out inventory: {HELDOUT_IMAGES_CSV}")


def clean_legacy_outputs() -> None:
    for name in LEGACY_OUTPUTS:
        path = OUTPUT_DIR / name
        if path.exists():
            path.unlink()
            print(f"Removed legacy output: {name}")
    legacy_ci = VALIDATION_DIR / "heldout_binary_metrics_bootstrap_ci.csv"
    if legacy_ci.exists():
        legacy_ci.unlink()
        print(f"Removed legacy output: {legacy_ci.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-plots", action="store_true")
    parser.add_argument("--skip-funnel", action="store_true")
    parser.add_argument("--skip-stability", action="store_true")
    parser.add_argument(
        "--keep-legacy",
        action="store_true",
        help="Do not delete old parent-folder CSVs",
    )
    args = parser.parse_args()

    print(f"OUTPUT_DIR = {OUTPUT_DIR}")
    stage_inputs()
    preflight()
    if not args.keep_legacy:
        clean_legacy_outputs()

    build_cmd = [sys.executable, str(SCRIPT_DIR / "5_build_outputs.py")]
    if args.skip_funnel:
        build_cmd.append("--skip-funnel")
    if args.skip_stability:
        build_cmd.append("--skip-stability")
    print("\n===== build thesis tables =====")
    subprocess.run(build_cmd, cwd=str(REPO_ROOT), check=True)

    if not args.skip_plots:
        print("\n===== plot figures =====")
        subprocess.run(
            ["Rscript", str(SCRIPT_DIR / "6_plot_outputs.R")],
            cwd=str(REPO_ROOT),
            check=True,
        )

    display = THESIS_TABLE_DIR / "yolo_vs_qwen_heldout_display.csv"
    ci = THESIS_TABLE_DIR / "yolo_vs_qwen_heldout_ci_table.csv"
    print("\nDone.")
    if display.exists():
        print(display)
        print(pd.read_csv(display).to_string(index=False))
    if ci.exists():
        print(ci)
        print(pd.read_csv(ci).to_string(index=False))
    stab = THESIS_TABLE_DIR / "yolo_qwen_yolo_pos_replicates.csv"
    if stab.exists():
        print(stab)
        print(pd.read_csv(stab).to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""Step 6.2b — does the detector transfer to locally collected imagery?

Step 6.2a asks whether self-collected imagery in the *training* set changes
performance on the GSVI held-out images. This script asks the complementary
question, which is the one the mitigation argument actually needs: how does the
same detector perform on self-collected imagery, and does adding SC training
examples close the gap between the two domains?

Two independent held-out sets, one per source, scored with the same five
detectors (0-100% self-collected in the training mix):

  GSVI held-out              180 images, 90 waste / 90 background
  Self-collected held-out    107 images, 55 waste / 52 background

The expected story was a recall gap — a detector trained on Street View missing
waste in hand-collected photographs. That is not what the data shows. Recall on
self-collected imagery is equal to or higher than on GSVI at every training mix,
so there is no recall loss to mitigate. The domain gap is in *localisation
quality*: mAP@0.50 is roughly 0.39 on GSVI against 0.16 on self-collected at 0%
SC, and adding SC training data closes a large part of that.

So the mitigation claim this supports is not "recall increased" but "supplementary
local training data reduced source-specific localisation loss", which is both
narrower and better evidenced.

Inputs (3_waste_identification/yolo/):
  heldout_GSVI_val_summary.csv            one row per scenario, GSVI test set
  heldout_selfcollected_val_summary.csv   one row per scenario, SC test set

Outputs (Data/Chapter_waste/6_selfcollected/2_identification/):
  3_sc_domain_transfer.csv                        both domains, long format
  thesis_table/table_6_2_domain_transfer.csv      the chapter table
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir, waste_id_dir  # noqa: E402

YOLO_DIR = waste_id_dir() / "yolo"
OUTPUT_DIR = selfcollected_dir() / "2_identification"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GSVI_SUMMARY = YOLO_DIR / "heldout_GSVI_val_summary.csv"
SC_SUMMARY = YOLO_DIR / "heldout_selfcollected_val_summary.csv"

LONG_CSV = OUTPUT_DIR / "3_sc_domain_transfer.csv"
TRANSFER_TABLE = TABLE_DIR / "table_6_2_domain_transfer.csv"

DOMAINS = {"gsvi": "GSVI held-out", "sc": "Self-collected held-out"}
METRICS = ["recall", "precision", "f1", "mAP50", "mAP50-95"]


def share_from_scenario(scenario: str) -> int:
    """sc_75pct -> 75."""
    return int(scenario.replace("sc_", "").replace("pct", ""))


def load() -> pd.DataFrame:
    for path in (GSVI_SUMMARY, SC_SUMMARY):
        if not path.exists():
            raise SystemExit(f"Missing {path}")
    frames = []
    for tag, path in (("gsvi", GSVI_SUMMARY), ("sc", SC_SUMMARY)):
        df = pd.read_csv(path)
        keep = ["scenario", "n_images", "n_waste_labels", *METRICS]
        df = df[[c for c in keep if c in df.columns]].copy()
        df["domain"] = tag
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["sc_share"] = out["scenario"].map(share_from_scenario)
    return out.sort_values(["domain", "sc_share"]).reset_index(drop=True)


def build_wide(long: pd.DataFrame) -> pd.DataFrame:
    """One row per training mix, both domains side by side, with the gaps."""
    wide = long.pivot(index="sc_share", columns="domain", values=METRICS)
    wide.columns = [f"{metric}_{domain}" for metric, domain in wide.columns]
    wide = wide.reset_index()
    for metric in METRICS:
        wide[f"{metric}_gap"] = wide[f"{metric}_gsvi"] - wide[f"{metric}_sc"]
    n_gsvi = int(long.loc[long["domain"] == "gsvi", "n_images"].iloc[0])
    n_sc = int(long.loc[long["domain"] == "sc", "n_images"].iloc[0])
    wide["n_images_gsvi"] = n_gsvi
    wide["n_images_sc"] = n_sc
    return wide


def build_table(wide: pd.DataFrame) -> pd.DataFrame:
    """Recall, precision and mAP on both domains, plus the domain gap."""
    rows = []
    for _, r in wide.iterrows():
        rows.append(
            {
                "SC in training": f"{int(r['sc_share'])}%",
                "Recall, GSVI": f"{100 * r['recall_gsvi']:.1f}%",
                "Recall, SC": f"{100 * r['recall_sc']:.1f}%",
                "Recall gap (pp)": f"{100 * r['recall_gap']:+.1f}",
                "Precision, GSVI": f"{100 * r['precision_gsvi']:.1f}%",
                "Precision, SC": f"{100 * r['precision_sc']:.1f}%",
                "mAP@0.50, GSVI": f"{r['mAP50_gsvi']:.3f}",
                "mAP@0.50, SC": f"{r['mAP50_sc']:.3f}",
                "mAP gap": f"{r['mAP50_gap']:+.3f}",
            }
        )
    out = pd.DataFrame(rows)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(TRANSFER_TABLE, index=False)
    print(f"\nCross-domain transfer, by self-collected share of the training set:")
    print(out.to_string(index=False))
    print(f"Wrote {TRANSFER_TABLE}")
    return out


def report(wide: pd.DataFrame) -> None:
    first = wide.iloc[0]
    last = wide.iloc[-1]
    print("\nWhat adding self-collected training data does to the domain gap:")
    print(f"  Recall gap (GSVI − SC): {100 * first['recall_gap']:+.1f} pp at 0% SC "
          f"→ {100 * last['recall_gap']:+.1f} pp at 100% SC")
    print("    The gap is negative throughout: recall on self-collected imagery is not lower.")
    print(f"  mAP@0.50 gap:           {first['mAP50_gap']:+.3f} at 0% SC "
          f"→ {last['mAP50_gap']:+.3f} at 100% SC "
          f"({100 * (1 - last['mAP50_gap'] / first['mAP50_gap']):.0f}% of the gap closed)")
    print(f"  mAP@0.50 on SC imagery: {first['mAP50_sc']:.3f} → {last['mAP50_sc']:.3f} "
          f"({100 * (last['mAP50_sc'] / first['mAP50_sc'] - 1):+.0f}%)")
    print(f"  Precision on SC:        {100 * first['precision_sc']:.1f}% "
          f"→ {100 * last['precision_sc']:.1f}%")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    long = load()
    n = long.groupby("domain")["n_images"].first()
    print(f"GSVI held-out: {n['gsvi']:,} images | Self-collected held-out: {n['sc']:,} images")
    long.to_csv(LONG_CSV, index=False)
    print(f"Wrote {LONG_CSV}")

    wide = build_wide(long)
    build_table(wide)
    report(wide)


if __name__ == "__main__":
    main()

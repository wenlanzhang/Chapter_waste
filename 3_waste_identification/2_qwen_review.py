#!/usr/bin/env python3
"""Step 3b — single-pass Qwen2-VL review of YOLO positives, all SC scenarios.

Companion to 3_qwen_replicates.ipynb, which queries Qwen three times but only
for the headline scenario and is the source of the replicate-stability result.
This script queries **once per image**, for **every** scenario found in the
YOLO predictions, so each retrained detector gets its YOLO -> Qwen cascade row.
Same model, prompt and image files as the notebook; only the replicate count
differs.

Each scenario is reviewed independently: every YOLO-positive row gets its own
API call, keyed by (scenario, image_name). An image that two detectors both
call positive is queried once for each of them. --dry-run reports the call
count before anything is spent.

Answers are written to qwen/qwen_responses_by_scenario.csv as they arrive, so a
run can be interrupted and resumed. That file is this script's own output: it
never reads Qwen results produced anywhere else.

Inputs (Data/Chapter_waste/3_waste_identification/):
  yolo/heldout_GSVI_p100_image_level_predictions.csv   which images each YOLO called positive
  sampling/heldout_GSVI_p100_test.csv                  img_dir for each held-out image

Image files are located under $PHD_DATA_ROOT/Waste/img/ via the img_dir column
of the sampling inventory, falling back to the Google panorama tree — the same
JPGs YOLO was validated on.

Outputs (Data/Chapter_waste/3_waste_identification/qwen/):
  qwen_responses_by_scenario.csv       one raw response per scenario x image (resumable)
  qwen_labels_sc_<share>pct.csv        per-scenario labels for 1_heldout_metrics.py

Scenarios whose label file is already complete are skipped unless --overwrite,
so a plain run will not clobber the notebook's multi-replicate output.

Usage:
  python 3_waste_identification/2_qwen_review.py --dry-run     # plan only, no API calls
  python 3_waste_identification/2_qwen_review.py --limit 3     # smoke test (3 rows)
  python 3_waste_identification/2_qwen_review.py               # the real run
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import waste_id_dir, waste_raw_dir  # noqa: E402

OUTPUT_DIR = waste_id_dir()
YOLO_DIR = OUTPUT_DIR / "yolo"
QWEN_DIR = OUTPUT_DIR / "qwen"
SAMPLING_DIR = OUTPUT_DIR / "sampling"

PREDICTIONS_CSV = YOLO_DIR / "heldout_GSVI_p100_image_level_predictions.csv"
INVENTORY_CSV = SAMPLING_DIR / "heldout_GSVI_p100_test.csv"
RESPONSES_CSV = QWEN_DIR / "qwen_responses_by_scenario.csv"

IMG_ROOT = waste_raw_dir() / "img"

MODEL_ID = "qwen2-vl-72b-instruct"
LABEL_COLUMN = "Qwen2_single"
SLEEP_S = 0.5
RETRY_SLEEP_S = 1.5
MAX_RETRY_ROUNDS = 20

# Verbatim from 3_qwen_replicates.ipynb — do not reword without
# re-running every scenario, including sc_100pct. The earlier, stricter
# "clearly defined piles" prompt of notebook 3_ answers No noticeably more often.
PROMPT = """
Is any discarded household refuse visible in this image (bags, packaging, bottles, paper, cloth,
food waste, or mixed trash)? Count modest or scattered waste as Yes if it is clearly discard/rubbish.
Ignore clean road/sidewalk, vegetation, bare soil, and intentional goods stacked for sale.
Answer Yes or No only.
""".strip()

UUID_PREFIX = re.compile(r"^[0-9a-f]{8}-(.+)$", re.I)
MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Image resolution (same chain as the notebook)
# ---------------------------------------------------------------------------
def core_stem(name: object) -> str:
    """Strip LabelImg-style leading 8-hex UUID prefixes from a stem/filename."""
    s = str(name)
    s = Path(s).stem if s.lower().endswith(tuple(MIME_TYPES)) else s
    while True:
        m = UUID_PREFIX.match(s)
        if not m:
            break
        s = m.group(1)
    return s


def load_inventory_paths() -> dict[str, Path]:
    """img_name -> file, using the img_dir recorded when the sample was drawn."""
    mapping: dict[str, Path] = {}
    if not INVENTORY_CSV.exists():
        return mapping
    with INVENTORY_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            path = IMG_ROOT / row["img_dir"] / f"{row['img_name']}.jpg"
            if path.exists():
                mapping[row["img_name"]] = path
    return mapping


def google_path_guesses(core: str) -> list[Path]:
    """GSVI layout: Google/{first}/{second}/{stem}.jpg, with case variants."""
    if "_" not in core:
        return []
    pan = core.rsplit("_", 1)[0]
    if len(pan) < 2:
        return []
    a, b = pan[0], pan[1]
    return [
        IMG_ROOT / "Google" / aa / bb / f"{core}.jpg"
        for aa in {a, a.lower(), a.upper()}
        for bb in {b, b.lower(), b.upper()}
    ]


def resolve_image(img_name: str, inv_paths: dict[str, Path]) -> Path | None:
    """The sampling inventory's img_dir first, then the Google panorama tree."""
    stem = Path(str(img_name)).stem
    core = core_stem(img_name)
    for key in (stem, core):
        if key in inv_paths:
            return inv_paths[key]
    for path in google_path_guesses(core):
        if path.exists():
            return path
    return None


# ---------------------------------------------------------------------------
# Qwen call
# ---------------------------------------------------------------------------
def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix not in MIME_TYPES:
        raise ValueError(f"Unsupported image type: {suffix}")
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{MIME_TYPES[suffix]};base64,{encoded}"


def qwen_yes_no(segmind, image_path: Path) -> str:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                ],
            }
        ]
    }
    reply = segmind.chat(MODEL_ID, **payload)
    text = getattr(reply, "text", None)
    if text is None:
        text = str(reply) if reply is not None else ""
    return (text or "").strip()


def is_missing(value: object) -> bool:
    """Blank / NaN / ERROR responses count as not yet answered."""
    if value is None:
        return True
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "na"}:
        return True
    return s.upper().startswith("ERROR")


# ---------------------------------------------------------------------------
# Responses, keyed by (scenario, image_name)
# ---------------------------------------------------------------------------
RESPONSE_FIELDS = [
    "scenario",
    "image_name",
    "image_path",
    "qwen_response",
    "status",
    "error",
    "model",
    "queried_at",
]

Key = tuple[str, str]


def load_responses() -> dict[Key, dict]:
    """Answers already collected, so an interrupted run resumes where it stopped."""
    if not RESPONSES_CSV.exists():
        return {}
    with RESPONSES_CSV.open(encoding="utf-8") as f:
        return {(r["scenario"], r["image_name"]): r for r in csv.DictReader(f)}


def save_responses(store: dict[Key, dict]) -> None:
    QWEN_DIR.mkdir(parents=True, exist_ok=True)
    with RESPONSES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESPONSE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for key in sorted(store):
            writer.writerow(store[key])


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
def scenario_label_path(scenario: str) -> Path:
    return QWEN_DIR / f"qwen_labels_{scenario}.csv"


def label_file_state(path: Path) -> tuple[str, int, int]:
    """('missing'|'partial'|'complete', answered, rows) for an existing label file.

    A file is only 'complete' when every row carries an answer in at least one
    replicate column. A partial file is a leftover from an interrupted or
    --limit run and must not be treated as done.
    """
    if not path.exists():
        return "missing", 0, 0
    df = pd.read_csv(path)
    replicates = [c for c in df.columns if c not in {"image_name", "scenario"}]
    if not replicates or df.empty:
        return "partial", 0, len(df)
    answered = int(sum(any(not is_missing(row[c]) for c in replicates) for _, row in df.iterrows()))
    return ("complete" if answered == len(df) else "partial"), answered, len(df)


def build_plan(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    """Rows to label, and the scenarios that will get a label file."""
    preds = pd.read_csv(PREDICTIONS_CSV)
    positives = preds[preds["prediction"] == 1].copy()

    scenarios = sorted(positives["scenario"].unique(), key=lambda s: int(re.search(r"\d+", s).group()))
    if args.scenario:
        unknown = set(args.scenario) - set(scenarios)
        if unknown:
            raise SystemExit(f"Unknown scenario(s): {sorted(unknown)}. Available: {scenarios}")
        scenarios = [s for s in scenarios if s in args.scenario]

    todo = []
    for scenario in scenarios:
        path = scenario_label_path(scenario)
        state, answered, rows = label_file_state(path)
        if state == "complete" and not args.overwrite:
            print(f"  skip {scenario}: {path.name} already complete ({rows} rows; --overwrite to replace)")
            continue
        if state == "partial":
            print(f"  redo {scenario}: {path.name} only {answered}/{rows} answered")
        todo.append(scenario)

    return positives[positives["scenario"].isin(todo)].copy(), todo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", nargs="+", help="Restrict to these scenarios (default: all)")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing qwen_labels_*.csv")
    parser.add_argument("--dry-run", action="store_true", help="Resolve images and report the plan; no API calls")
    parser.add_argument("--limit", type=int, help="Query at most N new images (smoke test)")
    parser.add_argument("--sleep", type=float, default=SLEEP_S, help=f"Pause between calls (default {SLEEP_S}s)")
    args = parser.parse_args()

    if not PREDICTIONS_CSV.exists():
        raise SystemExit(f"Missing predictions: {PREDICTIONS_CSV}")

    print(f"Prompt ({MODEL_ID}, single pass):\n  " + PROMPT.replace("\n", "\n  "))
    print()

    rows, scenarios = build_plan(args)
    if not scenarios:
        print("Nothing to do — every requested scenario already has a label file.")
        return

    # --- resolve every image that needs a response ------------------------
    inv_paths = load_inventory_paths()
    images = sorted(rows["image_name"].unique())
    resolved: dict[str, Path] = {}
    unresolved: list[str] = []
    for name in images:
        path = resolve_image(name, inv_paths)
        if path is None:
            unresolved.append(name)
        else:
            resolved[name] = path
    if unresolved:
        raise SystemExit(
            f"{len(unresolved)} image(s) not found on disk, e.g. {unresolved[:5]}. "
            f"Check PHD_DATA_ROOT ({IMG_ROOT})"
        )

    store = load_responses()
    todo_keys: list[Key] = [
        (str(r.scenario), str(r.image_name))
        for r in rows.sort_values(["scenario", "image_name"]).itertuples()
    ]
    pending = [k for k in todo_keys if is_missing(store.get(k, {}).get("qwen_response"))]
    n_done = len(todo_keys) - len(pending)
    if args.limit:
        pending = pending[: args.limit]

    print(
        f"Scenarios to label : {', '.join(scenarios)}\n"
        f"Rows to query      : {len(todo_keys)} (one call per scenario x image)\n"
        f"Distinct images    : {len(images)} (all located on disk)\n"
        f"Already answered   : {n_done}\n"
        f"API calls to make  : {len(pending)}"
    )
    if args.dry_run:
        print("\n--dry-run: stopping before any API call.")
        return

    # --- query ------------------------------------------------------------
    if pending:
        try:
            import segmind  # noqa: PLC0415
        except ImportError:
            raise SystemExit('segmind not installed. Run: pip install -U "segmind>=1.1.0"') from None
        if not os.environ.get("SEGMIND_API_KEY"):
            os.environ["SEGMIND_API_KEY"] = getpass.getpass("Enter your Segmind API key: ")

        def query(key: Key, tag: str) -> bool:
            scenario, name = key
            print(f"{tag} {scenario} {name} ...", end=" ", flush=True)
            path = resolved[name]
            record = {
                "scenario": scenario,
                "image_name": name,
                "image_path": str(path),
                "model": MODEL_ID,
                "queried_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                answer = qwen_yes_no(segmind, path)
                if is_missing(answer):
                    store[key] = {**record, "qwen_response": "", "status": "empty", "error": ""}
                    print("✗ empty response")
                    return False
                store[key] = {**record, "qwen_response": answer, "status": "success", "error": ""}
                print("✓", answer[:40].replace("\n", " "))
                return True
            except Exception as exc:  # noqa: BLE001 — recorded, retried below
                store[key] = {**record, "qwen_response": "", "status": "error", "error": str(exc)}
                print(f"✗ {exc}")
                return False
            finally:
                save_responses(store)
                time.sleep(args.sleep)

        n_ok = sum(query(k, f"[{i}/{len(pending)}]") for i, k in enumerate(pending, start=1))
        print(f"Initial pass: success={n_ok}, failed/empty={len(pending) - n_ok}")

        for round_i in range(1, MAX_RETRY_ROUNDS + 1):
            still = [k for k in pending if is_missing(store.get(k, {}).get("qwen_response"))]
            if not still:
                break
            print(f"\n--- Retry round {round_i}/{MAX_RETRY_ROUNDS}: {len(still)} row(s) ---")
            for i, key in enumerate(still, start=1):
                query(key, f"[retry{round_i} {i}/{len(still)}]")
                time.sleep(max(0.0, RETRY_SLEEP_S - args.sleep))
        still = [k for k in pending if is_missing(store.get(k, {}).get("qwen_response"))]
        if still:
            print(f"\nWARNING: {len(still)} row(s) still unanswered after {MAX_RETRY_ROUNDS} rounds: {still[:10]}")
        print(f"\nResponses: {RESPONSES_CSV}")

    # --- write one label file per scenario --------------------------------
    # Only fully answered scenarios are written. A partial file would be read back
    # as "done" on the next run and would break 1_heldout_metrics.py's cascade.
    print()
    for scenario in scenarios:
        subset = rows[rows["scenario"] == scenario].copy()
        subset[LABEL_COLUMN] = [
            store.get((scenario, str(n)), {}).get("qwen_response", "")
            for n in subset["image_name"]
        ]
        answered = int((~subset[LABEL_COLUMN].map(is_missing)).sum())
        out = subset[["image_name", "scenario", LABEL_COLUMN]].sort_values("image_name")
        path = scenario_label_path(scenario)

        if answered < len(out):
            print(f"Incomplete {scenario}: {answered}/{len(out)} answered — not written")
            # Drop a stale partial written by an earlier run of this script, so
            # nothing downstream reads it. Never touch a file we did not write.
            if path.exists() and list(pd.read_csv(path).columns) == ["image_name", "scenario", LABEL_COLUMN]:
                path.unlink()
                print(f"  removed stale {path.name}")
            continue

        QWEN_DIR.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
        print(f"Wrote {path}  ({answered}/{len(out)} answered)")

    if args.limit:
        print(
            f"\n--limit {args.limit} was set, so most scenarios are still incomplete. "
            "Re-run without --limit to finish; answers already collected are not re-queried."
        )

    print("\nNext: python 3_waste_identification/1_heldout_metrics.py")


if __name__ == "__main__":
    main()

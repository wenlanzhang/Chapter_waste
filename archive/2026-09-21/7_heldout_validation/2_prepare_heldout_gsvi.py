#!/usr/bin/env python3
"""Prepare an expanded GSVI held-out set via panoid-first sampling.

Method
------
1. Sample ~100 panoids (50 waste + 50 background), panoid-disjoint from Train0315_695
   and from the existing 20260714 GSVI held-out.
2. From each panoid, choose 1–2 class-appropriate directional views.
3. Target ~160–200 images (default 180 = 90 waste + 90 background).
4. Copy images into 7_heldout_validation/<tag>/{waste,background}/ and write CSVs.

Waste views come from Correct_SVI (on disk). Background views come from Combined_SVI
rows that are not in Correct_SVI. A share of backgrounds is hard-neg:
YOLO detected waste (yolo_num > 0) but Qwen said no (prediction == "no").
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import re
import shutil
from pathlib import Path

import pandas as pd

from paths import (
    ARCHIVE_OUTPUT_DIR,
    ARCHIVE_SENS_IMG_ROOT,
    HELDOUT_IMAGES_CSV,
    HELDOUT_IMG_ROOT,
    HELDOUT_TAG,
    HELDOUT_UNITS_CSV,
    IMG_ROOT,
    OUTPUT_DIR,
    TRAINING_CSV,
    TRAINING_CSV_STEP6,
)

GSVI_SUFFIX = re.compile(r"_(0|90|180|270)$")
HEADING_ORDER = {"0": 0, "90": 1, "180": 2, "270": 3}


def collection_from_name(img_name: str) -> str:
    return "GSVI" if GSVI_SUFFIX.search(str(img_name)) else "SC"


def archive_image_path(img_root: Path, img_name: str, img_dir: str) -> Path:
    return (img_root / str(img_dir) / f"{img_name}.jpg").resolve()


def heading_from_name(img_name: str) -> str:
    return str(img_name).rsplit("_", 1)[-1]


def max_yolo_conf(val) -> float:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0.0
    if isinstance(val, (list, tuple)):
        nums = [float(x) for x in val if x is not None]
        return max(nums) if nums else 0.0
    text = str(val).strip()
    if not text or text in {"[]", "nan", "None"}:
        return 0.0
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return 0.0
    if isinstance(parsed, (list, tuple)):
        nums = [float(x) for x in parsed if x is not None]
        return max(nums) if nums else 0.0
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return 0.0


def rank_waste_views(grp: pd.DataFrame) -> pd.DataFrame:
    out = grp.copy()
    out["_yolo_num"] = pd.to_numeric(out.get("yolo_num"), errors="coerce").fillna(0)
    out["_max_conf"] = out["yolo_conf"].map(max_yolo_conf) if "yolo_conf" in out.columns else 0.0
    out["_heading_rank"] = out["img_name"].map(heading_from_name).map(lambda h: HEADING_ORDER.get(h, 99))
    return out.sort_values(["_yolo_num", "_max_conf", "_heading_rank"], ascending=[False, False, True])


def stable_seed(text: str, base: int) -> int:
    digest = hashlib.md5(f"{base}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def assign_views_per_panoid(n_panoids: int, n_images: int) -> tuple[int, int]:
    if n_images < n_panoids:
        raise ValueError(f"Need at least 1 image/panoid: n_images={n_images}, n_panoids={n_panoids}")
    if n_images > 2 * n_panoids:
        raise ValueError(f"With max 2 views/panoid, cannot reach {n_images} from {n_panoids} panoids")
    n_double = n_images - n_panoids
    n_single = n_panoids - n_double
    return n_double, n_single


def allocate_hardneg_counts(
    n_panoids: int, n_images: int, share: float
) -> tuple[int, int, int, int]:
    if not 0.0 <= share <= 1.0:
        raise ValueError(f"share must be in [0, 1], got {share}")
    n_hard_p = int(round(n_panoids * share))
    n_hard_p = min(n_panoids, max(0, n_hard_p))
    n_easy_p = n_panoids - n_hard_p
    if n_hard_p == 0:
        return 0, 0, n_easy_p, n_images
    if n_easy_p == 0:
        return n_hard_p, n_images, 0, 0

    n_hard_i = int(round(n_images * share))
    lo_h, hi_h = n_hard_p, 2 * n_hard_p
    lo_e, hi_e = n_easy_p, 2 * n_easy_p
    n_hard_i = min(hi_h, max(lo_h, n_hard_i))
    n_easy_i = n_images - n_hard_i
    if n_easy_i < lo_e:
        n_easy_i = lo_e
        n_hard_i = n_images - n_easy_i
    elif n_easy_i > hi_e:
        n_easy_i = hi_e
        n_hard_i = n_images - n_easy_i
    if not (lo_h <= n_hard_i <= hi_h and lo_e <= n_easy_i <= hi_e):
        raise ValueError(
            f"Cannot allocate bg images with hardneg_share={share}: "
            f"hard {n_hard_p}p/{n_hard_i}i, easy {n_easy_p}p/{n_easy_i}i, total_images={n_images}"
        )
    return n_hard_p, n_hard_i, n_easy_p, n_easy_i


def rank_hardneg_views(grp: pd.DataFrame) -> pd.DataFrame:
    out = grp.copy()
    out["_yolo_num"] = pd.to_numeric(out.get("yolo_num"), errors="coerce").fillna(0)
    out["_max_conf"] = out["yolo_conf"].map(max_yolo_conf) if "yolo_conf" in out.columns else 0.0
    out["_heading_rank"] = out["img_name"].map(heading_from_name).map(lambda h: HEADING_ORDER.get(h, 99))
    return out.sort_values(["_yolo_num", "_max_conf", "_heading_rank"], ascending=[False, False, True])


def select_panoid_views(
    pool: pd.DataFrame,
    *,
    label_class: str,
    n_panoids: int,
    n_images: int,
    seed: int,
    view_rank: str = "auto",
) -> pd.DataFrame:
    n_double, n_single = assign_views_per_panoid(n_panoids, n_images)
    sizes = pool.groupby("panoid").size()
    ge2 = sorted(sizes[sizes >= 2].index.tolist())
    ge1 = sorted(sizes[sizes >= 1].index.tolist())
    if len(ge1) < n_panoids:
        raise ValueError(
            f"[{label_class}] only {len(ge1)} eligible panoids, need {n_panoids}"
        )
    if len(ge2) < n_double:
        raise ValueError(
            f"[{label_class}] only {len(ge2)} panoids with ≥2 views, need {n_double} doubles"
        )

    # Deterministic sample without replacement
    ge2_df = pd.Series(ge2).sample(frac=1, random_state=seed).tolist()
    double_panoids = ge2_df[:n_double]
    remaining = [p for p in ge1 if p not in set(double_panoids)]
    remaining = pd.Series(remaining).sample(frac=1, random_state=seed + 1).tolist()
    single_panoids = remaining[:n_single]
    if len(single_panoids) < n_single:
        raise ValueError(f"[{label_class}] could not fill single-view panoids")

    selected_rows: list[pd.DataFrame] = []
    double_set = set(double_panoids)
    for panoid in double_panoids + single_panoids:
        grp = pool[pool["panoid"] == panoid]
        mode = view_rank
        if mode == "auto":
            mode = "waste" if label_class == "waste" else "background"
        if mode == "waste":
            ranked = rank_waste_views(grp)
        elif mode == "hardneg":
            ranked = rank_hardneg_views(grp)
        else:
            ranked = grp.sample(frac=1, random_state=stable_seed(str(panoid), seed)).copy()
            ranked["_heading_rank"] = ranked["img_name"].map(heading_from_name).map(
                lambda h: HEADING_ORDER.get(h, 99)
            )
            ranked = ranked.sort_values("_heading_rank", kind="mergesort")
        n_take = 2 if panoid in double_set else 1
        take = ranked.head(n_take).copy()
        take["class"] = label_class
        take["n_views_selected"] = n_take
        take["unit_id"] = f"GSVI:{panoid}"
        selected_rows.append(take)

    out = pd.concat(selected_rows, ignore_index=True)
    assert out["panoid"].nunique() == n_panoids
    assert len(out) == n_images
    return out


def select_background_views(
    bg_pool: pd.DataFrame,
    *,
    n_panoids: int,
    n_images: int,
    seed: int,
    hardneg_share: float,
) -> pd.DataFrame:
    if "bg_kind" not in bg_pool.columns:
        raise ValueError("bg_pool must include bg_kind from build_pools()")
    hard = bg_pool[bg_pool["bg_kind"] == "hardneg"].copy()
    easy = bg_pool[bg_pool["bg_kind"] == "easy"].copy()
    n_hard_p, n_hard_i, n_easy_p, n_easy_i = allocate_hardneg_counts(
        n_panoids, n_images, hardneg_share
    )
    parts: list[pd.DataFrame] = []
    if n_hard_p:
        hard_sel = select_panoid_views(
            hard,
            label_class="background",
            n_panoids=n_hard_p,
            n_images=n_hard_i,
            seed=seed,
            view_rank="hardneg",
        )
        hard_sel["bg_kind"] = "hardneg"
        parts.append(hard_sel)
    if n_easy_p:
        if parts:
            used = set(parts[0]["panoid"].astype(str))
            easy = easy[~easy["panoid"].astype(str).isin(used)].copy()
        easy_sel = select_panoid_views(
            easy,
            label_class="background",
            n_panoids=n_easy_p,
            n_images=n_easy_i,
            seed=seed + 3,
            view_rank="background",
        )
        easy_sel["bg_kind"] = "easy"
        parts.append(easy_sel)
    out = pd.concat(parts, ignore_index=True)
    assert out["panoid"].nunique() == n_panoids
    assert len(out) == n_images
    return out


def build_pools(img_root: Path, training_csv: Path, exclude_prior_heldout: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(training_csv)
    train_names = set(train["img_name"].astype(str))
    train_panoids = set(train.loc[train["collection"] == "GSVI", "panoid"].dropna().astype(str))

    prior_panoids: set[str] = set()
    if exclude_prior_heldout:
        # Small 20260714 GSVI held-out lives in the archive
        prior_csv = ARCHIVE_OUTPUT_DIR / "Train0315_695_held_out_gsvi_test.csv"
        if prior_csv.exists():
            prior = pd.read_csv(prior_csv)
            prior_panoids = set(prior["panoid"].dropna().astype(str))

    correct = pd.read_csv(img_root / "Correct_SVI.csv", low_memory=False)
    correct["collection"] = correct["img_name"].map(collection_from_name)
    correct_names = set(correct["img_name"].astype(str))

    waste = correct[(correct["collection"] == "GSVI") & correct["panoid"].notna()].copy()
    waste["panoid"] = waste["panoid"].astype(str)
    waste = waste[~waste["img_name"].astype(str).isin(train_names)]
    waste = waste[~waste["panoid"].isin(train_panoids)]
    if prior_panoids:
        waste = waste[~waste["panoid"].isin(prior_panoids)]
    waste["source_image"] = [
        archive_image_path(img_root, n, d) for n, d in zip(waste["img_name"], waste["img_dir"])
    ]
    waste = waste[waste["source_image"].map(Path.exists)].copy()
    waste["collection"] = "GSVI"

    combined = pd.read_csv(img_root / "Combined_SVI.csv", low_memory=False)
    combined["collection"] = combined["img_name"].map(collection_from_name)
    bg = combined[
        (combined["collection"] == "GSVI")
        & combined["panoid"].notna()
        & ~combined["img_name"].astype(str).isin(correct_names)
        & ~combined["img_name"].astype(str).isin(train_names)
    ].copy()
    bg["panoid"] = bg["panoid"].astype(str)
    bg = bg[~bg["panoid"].isin(train_panoids)]
    if prior_panoids:
        bg = bg[~bg["panoid"].isin(prior_panoids)]
    # Keep background panoids disjoint from waste-candidate panoids
    waste_panoids = set(waste["panoid"])
    bg = bg[~bg["panoid"].isin(waste_panoids)].copy()
    bg["source_image"] = [
        archive_image_path(img_root, n, d) for n, d in zip(bg["img_name"], bg["img_dir"])
    ]
    # exist flag is reliable in this archive; still verify selected rows later
    if "exist" in bg.columns:
        bg = bg[bg["exist"] == True].copy()  # noqa: E712
    bg["collection"] = "GSVI"

    yolo_pos = pd.to_numeric(bg.get("yolo_num"), errors="coerce").fillna(0) > 0
    pred = (
        bg["prediction"].astype(str).str.strip().str.lower()
        if "prediction" in bg.columns
        else pd.Series("", index=bg.index)
    )
    bg = bg[~(yolo_pos & pred.eq("yes"))].copy()
    yolo_pos = pd.to_numeric(bg.get("yolo_num"), errors="coerce").fillna(0) > 0
    pred = (
        bg["prediction"].astype(str).str.strip().str.lower()
        if "prediction" in bg.columns
        else pd.Series("", index=bg.index)
    )
    bg["bg_kind"] = "easy"
    bg.loc[yolo_pos & pred.eq("no"), "bg_kind"] = "hardneg"
    bg = bg[(bg["bg_kind"] == "hardneg") | (~yolo_pos)].copy()
    return waste.reset_index(drop=True), bg.reset_index(drop=True)


def export_images(test_df: pd.DataFrame, out_dir: Path, img_root: Path) -> pd.DataFrame:
    waste_dir = out_dir / "waste"
    bg_dir = out_dir / "background"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    waste_dir.mkdir(parents=True)
    bg_dir.mkdir(parents=True)

    rows = []
    for _, row in test_df.sort_values("img_name").iterrows():
        src = Path(row["source_image"]) if pd.notna(row.get("source_image")) else archive_image_path(
            img_root, row["img_name"], row["img_dir"]
        )
        if not src.exists():
            raise FileNotFoundError(f"Missing source image: {src}")
        dest_dir = waste_dir if row["class"] == "waste" else bg_dir
        dest = dest_dir / f"{row['img_name']}.jpg"
        shutil.copy2(src, dest)
        rows.append(
            {
                "img_name": row["img_name"],
                "class": row["class"],
                "collection": row["collection"],
                "unit_id": row["unit_id"],
                "panoid": row["panoid"],
                "img_dir": row["img_dir"],
                "src_path": str(src),
                "dest_path": str(dest),
                "label_status": "manual_required" if row["class"] == "waste" else "background_no_label",
            }
        )
    return pd.DataFrame(rows)


def build_units(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for panoid, grp in selected.groupby("panoid", sort=True):
        rows.append(
            {
                "unit_id": f"GSVI:{panoid}",
                "collection": "GSVI",
                "label_class": grp["class"].iloc[0],
                "n_images": len(grp),
                "img_names": sorted(grp["img_name"].tolist()),
                "panoids": [str(panoid)],
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=HELDOUT_TAG)
    parser.add_argument("--n-panoids", type=int, default=100)
    parser.add_argument("--n-images", type=int, default=180)
    parser.add_argument("--waste-share", type=float, default=0.5)
    parser.add_argument(
        "--bg-hardneg-share",
        type=float,
        default=0.3,
        help="Share of background panoids/images from YOLO>0 & Qwen=no (default: 0.3)",
    )
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument(
        "--exclude-prior-heldout",
        dest="exclude_prior_heldout",
        action="store_true",
        default=True,
        help="Exclude panoids from archived 20260714 GSVI held-out (default: true)",
    )
    parser.add_argument(
        "--include-prior-heldout",
        dest="exclude_prior_heldout",
        action="store_false",
        help="Allow panoids from the archived 20260714 GSVI held-out",
    )
    parser.add_argument(
        "--copy-images",
        dest="copy_images",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-copy-images",
        dest="copy_images",
        action="store_false",
        help="Write CSVs only; do not copy image files",
    )
    parser.add_argument(
        "--link-archive-labels",
        action="store_true",
        default=True,
        help="If this sample matches archived p100 labels, copy waste YOLO labels (default: true)",
    )
    parser.add_argument(
        "--no-link-archive-labels",
        dest="link_archive_labels",
        action="store_false",
    )
    args = parser.parse_args()

    if args.n_panoids % 2 != 0:
        raise SystemExit("--n-panoids should be even for a 50/50 class split")
    training_csv = TRAINING_CSV if TRAINING_CSV.exists() else TRAINING_CSV_STEP6
    if not training_csv.exists():
        raise SystemExit(
            f"Missing training CSV. Run 1_build_training_inventory.py or Step 6 inventory.\n"
            f"Tried: {TRAINING_CSV} and {TRAINING_CSV_STEP6}"
        )

    img_root = IMG_ROOT
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    HELDOUT_IMG_ROOT.mkdir(parents=True, exist_ok=True)
    out_img_dir = HELDOUT_IMG_ROOT / args.tag

    if not 0.0 <= args.bg_hardneg_share <= 1.0:
        raise SystemExit("--bg-hardneg-share must be in [0, 1]")

    n_waste_panoids = args.n_panoids // 2
    n_bg_panoids = args.n_panoids - n_waste_panoids
    n_waste_images = round(args.n_images * args.waste_share)
    n_bg_images = args.n_images - n_waste_images
    n_hard_p, n_hard_i, n_easy_p, n_easy_i = allocate_hardneg_counts(
        n_bg_panoids, n_bg_images, args.bg_hardneg_share
    )

    print("Building external GSVI pools...")
    print(f"  training inventory: {training_csv}")
    waste_pool, bg_pool = build_pools(img_root, training_csv, args.exclude_prior_heldout)
    hard_pool = bg_pool[bg_pool["bg_kind"] == "hardneg"]
    easy_pool = bg_pool[bg_pool["bg_kind"] == "easy"]
    print(
        f"  waste pool: {len(waste_pool):,} images / {waste_pool['panoid'].nunique():,} panoids "
        f"(≥2 views: {(waste_pool.groupby('panoid').size() >= 2).sum():,})"
    )
    print(
        f"  bg pool:    {len(bg_pool):,} images / {bg_pool['panoid'].nunique():,} panoids "
        f"(hardneg={len(hard_pool):,}/{hard_pool['panoid'].nunique():,}p, "
        f"easy={len(easy_pool):,}/{easy_pool['panoid'].nunique():,}p)"
    )
    print(
        f"  bg mix target: hardneg {n_hard_p}p/{n_hard_i}img; "
        f"easy {n_easy_p}p/{n_easy_i}img (share={args.bg_hardneg_share})"
    )

    selected_waste = select_panoid_views(
        waste_pool,
        label_class="waste",
        n_panoids=n_waste_panoids,
        n_images=n_waste_images,
        seed=args.seed,
    )
    # Ensure bg selection cannot collide with chosen waste panoids
    bg_pool = bg_pool[~bg_pool["panoid"].isin(set(selected_waste["panoid"]))].copy()
    selected_bg = select_background_views(
        bg_pool,
        n_panoids=n_bg_panoids,
        n_images=n_bg_images,
        seed=args.seed + 17,
        hardneg_share=args.bg_hardneg_share,
    )

    # Verify bg sources exist before export
    selected_bg["image_exists"] = selected_bg["source_image"].map(Path.exists)
    if not selected_bg["image_exists"].all():
        missing = selected_bg.loc[~selected_bg["image_exists"], "img_name"].tolist()
        raise FileNotFoundError(f"Selected background images missing on disk: {missing[:10]}")

    keep_cols = [
        "img_name",
        "year",
        "month",
        "lat",
        "lon",
        "panoid",
        "img_dir",
        "exist",
        "collection",
        "class",
        "bg_kind",
        "unit_id",
        "n_views_selected",
        "source_image",
    ]
    for df in (selected_waste, selected_bg):
        for c in keep_cols:
            if c not in df.columns:
                df[c] = pd.NA

    selected = pd.concat(
        [selected_waste[keep_cols], selected_bg[keep_cols]], ignore_index=True
    ).sort_values(["class", "panoid", "img_name"]).reset_index(drop=True)
    selected["in_training_695"] = False
    selected["held_out_gsvi_panoid_sample"] = True
    selected["sample_tag"] = args.tag
    selected["sample_seed"] = args.seed
    selected["bg_hardneg_share"] = args.bg_hardneg_share

    units = build_units(selected)

    csv_images = HELDOUT_IMAGES_CSV
    csv_units = HELDOUT_UNITS_CSV
    selected.drop(columns=["source_image"]).to_csv(csv_images, index=False)
    units.to_csv(csv_units, index=False)

    print("\nSelected:")
    print(f"  panoids: {selected['panoid'].nunique()}  images: {len(selected)}")
    print(selected.groupby("class").size().to_string())
    bg_sel = selected[selected["class"] == "background"]
    if len(bg_sel):
        print("  background mix:")
        print(
            bg_sel.groupby("bg_kind")
            .agg(images=("img_name", "size"), panoids=("panoid", "nunique"))
            .to_string()
        )
    print(
        "  views/panoid:\n",
        selected.groupby(["class", "panoid"]).size().groupby("class").describe().to_string(),
    )
    print(f"Saved {csv_images}")
    print(f"Saved {csv_units}")

    if args.copy_images:
        print(f"\nCopying images → {out_img_dir}")
        manifest = export_images(selected, out_img_dir, img_root)
        manifest_path = out_img_dir / "held_out_manifest.csv"
        manifest.to_csv(manifest_path, index=False)
        # Convenience: empty YOLO label stubs for background; waste left unlabeled
        labels_dir = out_img_dir / "labels_pending"
        labels_dir.mkdir(exist_ok=True)
        for _, row in manifest.iterrows():
            lbl = labels_dir / f"{row['img_name']}.txt"
            if row["class"] == "background":
                lbl.write_text("")
            # waste: do not create stub unless archive labels are linked below

        n_linked = 0
        if args.link_archive_labels:
            n_linked = link_archive_p100_labels(manifest, labels_dir)

        readme = out_img_dir / "README.txt"
        readme.write_text(
            "\n".join(
                [
                    f"Tag: {args.tag}",
                    f"Panoids: {selected['panoid'].nunique()}",
                    f"Images: {len(selected)} (waste={n_waste_images}, background={n_bg_images})",
                    "Method: sample panoids → choose 1–2 class-appropriate headings",
                    (
                        f"Background mix: {args.bg_hardneg_share:.0%} hard-neg "
                        f"(YOLO>0 & Qwen=no) / {1 - args.bg_hardneg_share:.0%} easy (YOLO=0); "
                        f"hardneg={n_hard_p}p/{n_hard_i}img, easy={n_easy_p}p/{n_easy_i}img."
                    ),
                    "Panoid-safe vs Train0315_695; excluded archived 20260714 GSVI held-out panoids.",
                    "",
                    "Labeling:",
                    "  - Put YOLO .txt boxes for waste/ into labels_pending/ (same stem).",
                    "  - Background already has empty .txt stubs.",
                    f"  - Archive label copies linked: {n_linked}",
                    f"  - Archive labeled set (reference): {ARCHIVE_SENS_IMG_ROOT / '20260807_heldout_GSVI_p100_label'}",
                    "",
                    f"Inventory CSV: {csv_images}",
                    f"Units CSV: {csv_units}",
                    "",
                ]
            )
        )
        print(f"Copied {len(manifest)} images")
        print(f"Manifest: {manifest_path}")
        waste_n = int((manifest["class"] == "waste").sum())
        waste_labeled = sum(
            1
            for _, row in manifest.iterrows()
            if row["class"] == "waste" and (labels_dir / f"{row['img_name']}.txt").exists()
            and (labels_dir / f"{row['img_name']}.txt").read_text().strip()
        )
        print(f"Waste images: {waste_n}  (already labeled from archive: {waste_labeled})")
        print(f"Still need boxes: {waste_n - waste_labeled}")
    else:
        print("\n--no-copy-images: CSVs only")


def link_archive_p100_labels(manifest: pd.DataFrame, labels_dir: Path) -> int:
    """Copy matching labels from archived p100 YOLO label folder when stems match."""
    archive_labels = ARCHIVE_SENS_IMG_ROOT / "20260807_heldout_GSVI_p100_label" / "labels"
    if not archive_labels.exists():
        print(f"No archive labels at {archive_labels}")
        return 0

    uuid_prefix = re.compile(r"^[0-9a-f]{8}-", re.I)

    def stem_key(name: str) -> str:
        s = str(name)
        if s.lower().endswith(".txt"):
            s = s[:-4]
        if uuid_prefix.match(s):
            s = s.split("-", 1)[1]
        return s

    by_key: dict[str, Path] = {}
    for p in archive_labels.glob("*.txt"):
        by_key[stem_key(p.stem)] = p

    n = 0
    for _, row in manifest.iterrows():
        key = stem_key(row["img_name"])
        src = by_key.get(key)
        if src is None:
            continue
        dest = labels_dir / f"{row['img_name']}.txt"
        shutil.copy2(src, dest)
        n += 1
    print(f"Linked {n} labels from {archive_labels}")
    return n


if __name__ == "__main__":
    main()

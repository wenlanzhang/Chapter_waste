#!/usr/bin/env python3
"""Build the 695-image YOLO training inventory CSV.

One row per Train0315_695 image with collection (GSVI/SC), class (waste/background),
coords, and panoid. Writes Train0315_695_training.csv under the new Step 6 data dir.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from paths import (
    BASIC_CSVS,
    IMAGES_DIR,
    LABELS_DIR,
    OUTPUT_DIR,
    SPLIT_FILE,
    TRAINING_CSV,
    TRAINING_CSV_STEP6,
)

UUID_PREFIX = re.compile(r"^[0-9a-f]{8}-", re.I)
GSVI_SUFFIX = re.compile(r"_(0|90|180|270)$")


def collection_from_name(img_name: str) -> str:
    return "GSVI" if GSVI_SUFFIX.search(str(img_name)) else "SC"


def strip_uuid_prefix(name: str) -> str:
    s = str(name)
    if UUID_PREFIX.match(s):
        return s.split("-", 1)[1]
    return s


def class_from_label(label_path: Path) -> str:
    if not label_path.exists():
        return "background"
    return "waste" if label_path.read_text().strip() else "background"


def load_split_names(split_file: Path) -> list[str]:
    with open(split_file) as f:
        raw = [Path(line.strip()).stem for line in f if line.strip()]
    return [n for n in raw if n and n != ".DS_Store"]


def load_metadata(basic_csvs: list[Path]) -> pd.DataFrame:
    parts = []
    for path in basic_csvs:
        if not path.exists():
            continue
        part = pd.read_csv(path)
        part["meta_source"] = path.stem.replace("_basic", "")
        parts.append(part)
    if not parts:
        raise FileNotFoundError(f"No metadata CSVs found in {basic_csvs}")
    meta = pd.concat(parts, ignore_index=True)
    meta["img_name_key"] = meta["img_name"].astype(str).map(strip_uuid_prefix)
    # Prefer first match; duplicates across Faith/ZWL/Google are rare for same stem
    return meta.drop_duplicates(subset=["img_name_key"], keep="first")


def build_training_table() -> pd.DataFrame:
    img_names = load_split_names(SPLIT_FILE)
    meta = load_metadata(BASIC_CSVS)
    meta_lookup = meta.set_index("img_name_key")

    rows = []
    missing_meta = []
    missing_image = []
    for img_name in img_names:
        image_path = IMAGES_DIR / f"{img_name}.jpg"
        if not image_path.exists():
            missing_image.append(img_name)
        label_path = LABELS_DIR / f"{img_name}.txt"
        key = strip_uuid_prefix(img_name)
        if key in meta_lookup.index:
            m = meta_lookup.loc[key]
            if isinstance(m, pd.DataFrame):
                m = m.iloc[0]
            lat, lon, panoid, img_dir = m.get("lat"), m.get("lon"), m.get("panoid"), m.get("img_dir")
            year, month = m.get("year"), m.get("month")
            meta_source = m.get("meta_source")
        else:
            missing_meta.append(img_name)
            lat = lon = panoid = img_dir = year = month = meta_source = pd.NA

        rows.append(
            {
                "img_name": img_name,
                "collection": collection_from_name(img_name),
                "class": class_from_label(label_path),
                "lat": lat,
                "lon": lon,
                "panoid": panoid,
                "year": year,
                "month": month,
                "img_dir": img_dir,
                "meta_source": meta_source,
                "image_path": str(image_path),
                "label_path": str(label_path),
            }
        )

    df = pd.DataFrame(rows)
    if missing_image:
        print(f"WARNING: {len(missing_image)} training images missing on disk (first 5): {missing_image[:5]}")
    if missing_meta:
        print(f"WARNING: {len(missing_meta)} images missing metadata (first 5): {missing_meta[:5]}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_CSV_STEP6.parent.mkdir(parents=True, exist_ok=True)
    df = build_training_table()
    df.to_csv(TRAINING_CSV, index=False)
    df.to_csv(TRAINING_CSV_STEP6, index=False)

    print(f"Wrote {TRAINING_CSV}  (n={len(df)})")
    print(f"Wrote {TRAINING_CSV_STEP6}")
    print(pd.crosstab(df["collection"], df["class"]))


if __name__ == "__main__":
    main()

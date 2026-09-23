"""Waste accumulation level classification for 100 m grid cells."""

from __future__ import annotations

import mapclassify
import numpy as np
import pandas as pd

# IDEAMaps validation bands (proportion, not percent)
LOW_MAX = 0.024       # 0 – 2.4%
MEDIUM_MAX = 0.164    # 2.5% – 16.4%; High is > 16.4%

CLASS_LABELS = {
    0: "No SVI data",
    1: "Low (0–2.4%)",
    2: "Medium (2.5–16.4%)",
    3: "High (>16.4%)",
}

JENKS_K = 3


def _ratio_for_classification(
    final_ratio: pd.Series,
    smoothed_ratio: pd.Series | None = None,
    raw_ratio: pd.Series | None = None,
) -> pd.Series:
    out = final_ratio.copy()
    if smoothed_ratio is not None:
        out = out.fillna(smoothed_ratio)
    if raw_ratio is not None:
        out = out.fillna(raw_ratio)
    return out


def classify_fixed_bands(
    final_ratio: pd.Series,
    has_svi: pd.Series,
    smoothed_ratio: pd.Series | None = None,
    raw_ratio: pd.Series | None = None,
) -> pd.Series:
    """
    IDEAMaps fixed probability bands on smoothed waste/SVI ratio.

    Class 0 = no SVI images in cell (from counts, not inferred from ratio).
    Classes 1–3 = Low / Medium / High where total_svi_images >= 1.
    """
    ratio = _ratio_for_classification(final_ratio, smoothed_ratio, raw_ratio)
    has_data = has_svi.astype(bool)

    out = pd.Series(np.int8(0), index=ratio.index)
    out.loc[has_data & (ratio <= LOW_MAX)] = 1
    out.loc[has_data & (ratio > LOW_MAX) & (ratio <= MEDIUM_MAX)] = 2
    out.loc[has_data & (ratio > MEDIUM_MAX)] = 3
    return out.astype(int)


def classify_jenks(
    final_ratio: pd.Series,
    has_svi: pd.Series,
    smoothed_ratio: pd.Series | None = None,
    raw_ratio: pd.Series | None = None,
    k: int = JENKS_K,
) -> pd.Series:
    """Jenks Natural Breaks on cells with SVI; class 0 reserved for no-data cells."""
    ratio = _ratio_for_classification(final_ratio, smoothed_ratio, raw_ratio)
    has_data = has_svi.astype(bool)

    out = pd.Series(np.int8(0), index=ratio.index)
    if not has_data.any():
        return out.astype(int)

    values = ratio.loc[has_data].fillna(0)
    classifier = mapclassify.NaturalBreaks(values, k=k)
    out.loc[has_data] = classifier.yb + 1
    return out.astype(int)


def classify_result(
    method: str,
    final_ratio: pd.Series,
    has_svi: pd.Series,
    smoothed_ratio: pd.Series | None = None,
    raw_ratio: pd.Series | None = None,
) -> pd.Series:
    if method == "fixed":
        return classify_fixed_bands(final_ratio, has_svi, smoothed_ratio, raw_ratio)
    if method == "jenks":
        return classify_jenks(final_ratio, has_svi, smoothed_ratio, raw_ratio)
    raise ValueError(f"Unknown classification method: {method!r}")

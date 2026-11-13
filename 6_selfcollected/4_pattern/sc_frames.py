"""Shared analysis frames for Step 6.4 — the same points, labelled once per arm.

Step 5 runs on the GSVI arm and loads its frame from ``lib.panoids``. Step 6.4
needs both arms side by side, labelled against the *same* settlement polygons
and with the same distance conventions, so every block of 6.4 (clustering,
settlement association, signed-distance GAM) compares like with like.

The sampling unit differs between the arms only in how it is keyed: a GSVI
panorama is keyed by ``panoid``, a self-collected image by ``img:<img_name>``
(it carries no panoid). ``lib.arms.observation_key`` handles that, and the
combined Step 2c layer already stores the result as ``obs_key``.

Both frames carry:
  obs_key, waste_positive, inside_settlement, signed_distance_m,
  distance_to_settlement_m (unsigned, 0 inside), year, is_self_collected
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir  # noqa: E402
from lib.panoids import (  # noqa: E402
    enrich_combined_frame,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

PATTERN_DIR = selfcollected_dir() / "4_pattern"

ARM_LABELS = {"gsvi": "GSVI", "gsvi_selfcollected": "GSVI + SC"}
ARM_KEYS = tuple(ARM_LABELS)

# Same mutually exclusive proximity bins as Step 5a's cluster context.
DISTANCE_CATEGORIES = [
    "Within Urban Poor",
    "0-250m buffer",
    "250-500m buffer",
    ">500m outside",
]


def categorize_distance(inside, distance_m) -> pd.Series:
    cats = pd.Series(">500m outside", index=range(len(distance_m)), dtype=object)
    d = pd.Series(distance_m).reset_index(drop=True)
    ins = pd.Series(inside).reset_index(drop=True).astype(bool)
    cats[d <= 500] = "250-500m buffer"
    cats[d <= 250] = "0-250m buffer"
    cats[ins | (d <= 1e-6)] = "Within Urban Poor"
    return cats


def _label(points: gpd.GeoDataFrame, slums: gpd.GeoDataFrame, key_col: str) -> gpd.GeoDataFrame:
    out = label_inside_settlement(points, slums)
    out["obs_key"] = out[key_col].astype(str)
    out["signed_distance_m"] = signed_distance_to_slums(out, slums)
    slum_union = unary_union(slums.geometry)
    unsigned = out.geometry.distance(slum_union).to_numpy(dtype=float)
    out["distance_to_settlement_m"] = unsigned
    # Keep distance exactly 0 for points labelled inside (floating-point safety)
    out.loc[out["inside_settlement"] == 1, "distance_to_settlement_m"] = 0.0
    out["distance_category"] = categorize_distance(
        out["inside_settlement"].to_numpy(), out["distance_to_settlement_m"].to_numpy()
    ).to_numpy()
    if "is_self_collected" not in out.columns:
        out["is_self_collected"] = 0
    out["waste_positive"] = pd.to_numeric(out["waste_positive"], errors="coerce").fillna(0).astype(int)
    return out.reset_index(drop=True)


def load_frames(verbose: bool = True) -> dict[str, gpd.GeoDataFrame]:
    """Both arms' observation frames, labelled against the same settlements."""
    slums = load_slums()
    if verbose:
        print("Labelling GSVI frame...")
    gsvi = _label(enrich_sviwaste_frame(), slums, "panoid")
    if verbose:
        print("Labelling GSVI + self-collected frame...")
    combined = _label(enrich_combined_frame(), slums, "obs_key")
    frames = {"gsvi": gsvi, "gsvi_selfcollected": combined}
    if verbose:
        for key, df in frames.items():
            print(f"  [{key}] {len(df):,} locations | {int(df['waste_positive'].sum()):,} "
                  f"waste-positive ({100 * df['waste_positive'].mean():.2f}%)")
    return frames

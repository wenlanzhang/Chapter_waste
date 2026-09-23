"""The two analysis arms: GSVI only vs GSVI + self-collected imagery.

Every aggregation downstream of Step 1 (road coverage, 100 m grid, hotspots)
runs once per arm. ``Arm.key`` doubles as the filename infix Step 1 writes
(``Nairobi_Waste_point_{key}_32737.gpkg``) and that later steps reuse for their
own per-arm outputs; ``Arm.tag`` is the short column prefix in side-by-side
tables (``gsvi_waste_points`` / ``gsc_waste_points``).

Typical use::

    from lib.arms import ARMS
    for arm in ARMS.values():
        waste = gpd.read_file(arm.waste_gpkg())
        out = OUTPUT_DIR / arm.filename("Nairobi_grid_coverage")
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from chapter_paths import prep_dir

SELF_SOURCES = frozenset({"Faith", "ZWL"})
GSVI_SOURCE = "Google"


@dataclass(frozen=True)
class Arm:
    key: str
    tag: str
    label: str
    column: str  # header in side-by-side thesis tables
    sources: frozenset[str]

    @property
    def includes_self_collected(self) -> bool:
        return bool(self.sources & SELF_SOURCES)

    def filename(self, stem: str, suffix: str = "_32737", ext: str = "gpkg") -> str:
        """``stem`` + arm infix, e.g. ``Nairobi_grid_coverage_gsvi_32737.gpkg``."""
        return f"{stem}_{self.key}{suffix}.{ext}"

    def tagged(self, tag: str) -> str:
        """Append the arm key to a Step 2 style file tag (``buf50m`` → ``buf50m_gsvi``)."""
        return f"{tag}_{self.key}"

    # Step 1 harmonised layers -------------------------------------------------
    def waste_gpkg(self) -> Path:
        return prep_dir() / self.filename("Nairobi_Waste_point")

    def svi_point_gpkg(self) -> Path:
        return prep_dir() / self.filename("Nairobi_SVI_point")

    def svi_image_gpkg(self) -> Path:
        return prep_dir() / self.filename("Nairobi_SVI_image")


GSVI = Arm(
    key="gsvi",
    tag="gsvi",
    label="GSVI only (Google)",
    column="GSVI",
    sources=frozenset({GSVI_SOURCE}),
)
GSVI_SC = Arm(
    key="gsvi_selfcollected",
    tag="gsc",
    label="GSVI + self-collected (Faith/ + ZWL/)",
    column="GSVI + SC",
    sources=frozenset({GSVI_SOURCE}) | SELF_SOURCES,
)

ARMS: dict[str, Arm] = {arm.key: arm for arm in (GSVI, GSVI_SC)}
ARM_KEYS: tuple[str, ...] = tuple(ARMS)


def get_arm(key: str) -> Arm:
    try:
        return ARMS[key]
    except KeyError:
        raise ValueError(f"Unknown arm {key!r}; expected one of {ARM_KEYS}") from None


# CLI plumbing ----------------------------------------------------------------
ALL_ARMS = "all"


def add_arm_argument(parser: argparse.ArgumentParser, default: str = ALL_ARMS) -> None:
    parser.add_argument(
        "--arm",
        choices=[*ARM_KEYS, ALL_ARMS],
        default=default,
        help=f"Analysis arm to run (default: {default})",
    )


def select_arms(value: str | None) -> list[Arm]:
    if value in (None, ALL_ARMS):
        return list(ARMS.values())
    return [get_arm(value)]


# Observation keys ------------------------------------------------------------
def observation_key(df: pd.DataFrame) -> pd.Series:
    """Stable per-sampling-point key across arms.

    GSVI rows share a ``panoid`` across their directional images; self-collected
    (Faith/ZWL) rows have no panoid, so each image is its own sampling point and
    is keyed by ``img_name``.
    """
    panoid = df["panoid"] if "panoid" in df.columns else pd.Series(pd.NA, index=df.index)
    has_panoid = panoid.notna() & (panoid.astype(str).str.strip() != "")
    img = "img:" + df["img_name"].astype(str)
    return panoid.astype(str).where(has_panoid, img)

"""HDBSCAN param sensitivity for GSVI vs GSVI+SC mitigation metrics.

Re-runs the footprint retention checks from 4_mitigation_comparison.py across a
small (min_cluster_size × min_samples) grid. Primary chapter result remains
min_cluster_size=25, min_samples=6.

Metrics per grid cell:
  - hotspot retention (≥30% hull-area overlap)
  - share of new SC locations inside GSVI hulls
  - hotspot counts and total hull area both arms
"""

from __future__ import annotations

import importlib.util
import itertools
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.hdbscan_fit import (  # noqa: E402
    MIN_CLUSTER_SIZE,
    MIN_SAMPLES,
    cluster_convex_hull,
    cluster_labels,
)
from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    load_gsvi_selfcollected_locations,
    load_gsvi_waste_panoids,
)


def _load_mitigation_module():
    path = SCRIPT_DIR / "4_mitigation_comparison.py"
    spec = importlib.util.spec_from_file_location("mitigation_comparison", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mit = _load_mitigation_module()
count_inside_existing_hotspots = _mit.count_inside_existing_hotspots
extract_new_observations = _mit.extract_new_observations
match_hotspots = _mit.match_hotspots
HOTSPOT_OVERLAP_FRAC = _mit.HOTSPOT_OVERLAP_FRAC

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"
OUT_CSV = OUTPUT_DIR / "Nairobi_mitigation_param_sensitivity.csv"
THESIS_CSV = TABLE_DIR / "table_mitigation_param_sensitivity.csv"

MIN_CLUSTER_SIZES = [15, 20, 25, 30, 35]
MIN_SAMPLES_LIST = [4, 5, 6, 8, 10]
BASELINE = (MIN_CLUSTER_SIZE, MIN_SAMPLES)


def run_arm(gdf: gpd.GeoDataFrame, mcs: int, ms: int) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    out = gdf.copy()
    out["HDB_cluster"] = cluster_labels(gdf, min_cluster_size=mcs, min_samples=ms)
    hulls = cluster_convex_hull(out)
    return out, hulls


def metrics_for_params(
    gsvi_pts: gpd.GeoDataFrame,
    sc_pts: gpd.GeoDataFrame,
    mcs: int,
    ms: int,
) -> dict:
    gsvi_gdf, gsvi_hulls = run_arm(gsvi_pts, mcs, ms)
    sc_gdf, sc_hulls = run_arm(sc_pts, mcs, ms)

    n_gsvi_hotspots = len(gsvi_hulls)
    n_sc_hotspots = len(sc_hulls)
    gsvi_area = float(gsvi_hulls["area_km2"].sum()) if n_gsvi_hotspots else 0.0
    sc_area = float(sc_hulls["area_km2"].sum()) if n_sc_hotspots else 0.0
    area_change_pct = (
        100.0 * (sc_area - gsvi_area) / gsvi_area if gsvi_area > 0 else float("nan")
    )

    new_obs = extract_new_observations(gsvi_gdf, sc_gdf)
    n_new = len(new_obs)
    n_inside, n_outside = count_inside_existing_hotspots(new_obs, gsvi_hulls)
    n_retained, n_new_hotspots = match_hotspots(gsvi_hulls, sc_hulls)

    retention_pct = (
        100.0 * n_retained / n_gsvi_hotspots if n_gsvi_hotspots else float("nan")
    )
    new_inside_pct = 100.0 * n_inside / n_new if n_new else float("nan")
    effective_ms = min(ms, mcs)

    return {
        "min_cluster_size": mcs,
        "min_samples": effective_ms,
        "is_baseline": (mcs, effective_ms) == BASELINE,
        "n_gsvi_hotspots": n_gsvi_hotspots,
        "n_sc_hotspots": n_sc_hotspots,
        "gsvi_hotspot_area_km2": round(gsvi_area, 3),
        "sc_hotspot_area_km2": round(sc_area, 3),
        "area_change_pct": round(area_change_pct, 1) if pd.notna(area_change_pct) else None,
        "n_new_locations": n_new,
        "n_new_inside_gsvi_hulls": n_inside,
        "n_new_outside_gsvi_hulls": n_outside,
        "new_inside_pct": round(new_inside_pct, 1) if pd.notna(new_inside_pct) else None,
        "n_gsvi_hotspots_retained": n_retained,
        "retention_pct": round(retention_pct, 1) if pd.notna(retention_pct) else None,
        "n_newly_created_hotspots": n_new_hotspots,
        "hotspot_overlap_frac": HOTSPOT_OVERLAP_FRAC,
    }


def thesis_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "min_cluster_size",
        "min_samples",
        "is_baseline",
        "n_gsvi_hotspots",
        "n_sc_hotspots",
        "gsvi_hotspot_area_km2",
        "sc_hotspot_area_km2",
        "area_change_pct",
        "new_inside_pct",
        "retention_pct",
        "n_newly_created_hotspots",
    ]
    return df[cols].copy()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading panoid / location inputs …")
    gsvi_pts = load_gsvi_waste_panoids()
    sc_pts = load_gsvi_selfcollected_locations()
    print(f"  GSVI: {len(gsvi_pts):,}  |  GSVI+SC: {len(sc_pts):,}")

    combos = list(itertools.product(MIN_CLUSTER_SIZES, MIN_SAMPLES_LIST))
    print(
        f"Sweeping {len(combos)} parameter combinations "
        f"(overlap threshold = {HOTSPOT_OVERLAP_FRAC:.0%}; "
        f"baseline = {BASELINE[0]}, {BASELINE[1]}) …"
    )

    rows = []
    for mcs, ms in combos:
        row = metrics_for_params(gsvi_pts, sc_pts, mcs, ms)
        rows.append(row)
        flag = " *" if row["is_baseline"] else ""
        print(
            f"  mcs={mcs:2d} ms={ms:2d} → "
            f"retain={row['retention_pct']}% "
            f"({row['n_gsvi_hotspots_retained']}/{row['n_gsvi_hotspots']})  "
            f"new_in={row['new_inside_pct']}%  "
            f"area={row['area_change_pct']:+}%  "
            f"hotspots {row['n_gsvi_hotspots']}→{row['n_sc_hotspots']}"
            f"{flag}"
        )

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    thesis = thesis_table(df)
    thesis.to_csv(THESIS_CSV, index=False)

    print(f"\nWrote {OUT_CSV}")
    print(f"Wrote {THESIS_CSV}")

    baseline = df.loc[df["is_baseline"]].iloc[0]
    print(
        "\nBaseline "
        f"(mcs={baseline['min_cluster_size']}, ms={baseline['min_samples']}): "
        f"retention={baseline['retention_pct']}%, "
        f"new_inside={baseline['new_inside_pct']}%"
    )
    print(
        "Grid summary — "
        f"retention {df['retention_pct'].min()}–{df['retention_pct'].max()}%, "
        f"new_inside {df['new_inside_pct'].min()}–{df['new_inside_pct'].max()}%"
    )


if __name__ == "__main__":
    main()

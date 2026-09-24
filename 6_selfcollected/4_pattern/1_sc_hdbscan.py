#!/usr/bin/env python3
"""Step 6.4a — do the waste hotspots change when self-collected imagery is added?

Step 5a clusters the 2,696 waste-positive GSVI panoramas with HDBSCAN
(min_cluster_size 25, min_samples 6) and finds 24 hotspots. This script fits the
same clusterer, with the same parameters, to the same points plus the 149
self-collected waste locations, and compares the two results side by side:

  how many hotspots, how much of the sample is clustered, how much area
  how many of the 24 GSVI hotspots survive (>=30% of their hull re-covered)
  how many hotspots are new
  where the added locations fall: inside an existing GSVI hull, or outside it

The last question is the one that matters for the chapter. A new location inside
an existing hotspot confirms what GSVI already saw; one outside it is a place the
platform never reported. The split is what 2plot_new_obs_stacked_bar.R draws.

Unit: panorama location, not image — a GSVI panoid, or one self-collected image
(which carries no panoid). Hotspot area is the sum of per-cluster convex hulls.

Outputs (Data/Chapter_waste/6_selfcollected/4_pattern/):
  1_Nairobi_sc_hdbscan_{gsvi,gsvi_selfcollected}_32737.gpkg   clustered points
  1_Nairobi_sc_hotspots_{gsvi,gsvi_selfcollected}_32737.gpkg  convex-hull footprints
  1_sc_hdbscan_new_locations.csv                              the inside/outside split
  thesis_table/table_6_4_hdbscan_comparison.csv               the chapter table
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import selfcollected_dir  # noqa: E402
from lib.hdbscan_fit import MIN_CLUSTER_SIZE, MIN_SAMPLES, cluster_convex_hull, cluster_points  # noqa: E402
from lib.panoids import (  # noqa: E402
    load_gsvi_selfcollected_locations,
    load_gsvi_waste_panoids,
    location_keys,
)

OUTPUT_DIR = selfcollected_dir() / "4_pattern"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

NEW_LOCATIONS_CSV = OUTPUT_DIR / "1_sc_hdbscan_new_locations.csv"
COMPARISON_TABLE = TABLE_DIR / "table_6_4_hdbscan_comparison.csv"

# A GSVI hotspot counts as retained when at least this share of its hull area is
# covered by some hotspot of the combined arm.
HOTSPOT_OVERLAP_FRAC = 0.30

ARMS = {
    "gsvi": {"column": "GSVI", "loader": load_gsvi_waste_panoids},
    "gsvi_selfcollected": {"column": "GSVI + SC", "loader": load_gsvi_selfcollected_locations},
}


def points_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_sc_hdbscan_{key}_32737.gpkg"


def hotspots_gpkg(key: str) -> Path:
    return OUTPUT_DIR / f"1_Nairobi_sc_hotspots_{key}_32737.gpkg"


def run_arm(key: str) -> dict:
    meta = ARMS[key]
    points = meta["loader"]()
    clustered, summary = cluster_points(points)
    hulls = cluster_convex_hull(clustered)
    summary["total_hotspot_area_km2"] = float(hulls["area_km2"].sum()) if len(hulls) else 0.0

    clustered.to_file(points_gpkg(key), driver="GPKG")
    hulls.to_file(hotspots_gpkg(key), driver="GPKG")
    print(f"[{key}] {summary['n_points']:,} locations | {summary['n_clusters']} clusters | "
          f"{summary['n_noise']:,} noise ({100 - summary['pct_waste_points_clustered']:.1f}%) | "
          f"{summary['total_hotspot_area_km2']:.3f} km²")
    print(f"  Wrote {points_gpkg(key).name}, {hotspots_gpkg(key).name}")
    return {"points": clustered, "hulls": hulls, "summary": summary}


def fmt(value: float, *, area: bool = False) -> str:
    return f"{value:,.3f}" if area else f"{int(round(value)):,}"


def pct_change(a: float, b: float) -> str:
    return "—" if a == 0 else f"{100.0 * (b - a) / a:+.1f}%"


def build_comparison(a: dict, b: dict) -> pd.DataFrame:
    sa, sb = a["summary"], b["summary"]
    rows = [
        ("Waste locations", sa["n_points"], sb["n_points"], False),
        ("Clustered locations", sa["n_clustered"], sb["n_clustered"], False),
        ("Noise locations", sa["n_noise"], sb["n_noise"], False),
        ("Number of hotspots", sa["n_clusters"], sb["n_clusters"], False),
        ("Total hotspot area (km²)", sa["total_hotspot_area_km2"], sb["total_hotspot_area_km2"], True),
    ]
    records = [
        {
            "Metric": metric,
            "GSVI": fmt(va, area=is_area),
            "GSVI + SC": fmt(vb, area=is_area),
            "Change": (f"{vb - va:+.3f}" if is_area else f"{int(round(vb - va)):+,}"),
            "Change %": pct_change(va, vb),
        }
        for metric, va, vb, is_area in rows
    ]
    out = pd.DataFrame(records)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(COMPARISON_TABLE, index=False)
    print(f"\n{out.to_string(index=False)}")
    print(f"Wrote {COMPARISON_TABLE}")
    return out


def new_locations(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Locations present in the combined arm but not in GSVI."""
    gsvi_keys = set(location_keys(a))
    return b.loc[~location_keys(b).isin(gsvi_keys)].copy()


def count_inside(new: gpd.GeoDataFrame, hulls: gpd.GeoDataFrame) -> tuple[int, int]:
    if new.empty or hulls.empty:
        return 0, len(new)
    joined = gpd.sjoin(new, hulls[["geometry"]], how="left", predicate="intersects")
    n_inside = len(joined.index[joined.index_right.notna()].unique())
    return n_inside, len(new) - n_inside


def match_hotspots(a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> tuple[int, int]:
    """(GSVI hulls retained in the combined arm, combined hulls with no GSVI counterpart)."""
    if a.empty:
        return 0, len(b)
    if b.empty:
        return 0, 0

    def best_overlap(geom, others) -> float:
        best = 0.0
        for other in others:
            inter = geom.intersection(other)
            if not inter.is_empty:
                best = max(best, inter.area / geom.area)
        return best

    retained = sum(best_overlap(g, b.geometry) >= HOTSPOT_OVERLAP_FRAC for g in a.geometry)
    created = sum(best_overlap(g, a.geometry) < HOTSPOT_OVERLAP_FRAC for g in b.geometry)
    return int(retained), int(created)


def share(part: int, whole: int) -> str:
    return "0 (0.0%)" if whole == 0 else f"{part:,} ({100.0 * part / whole:.1f}%)"


def build_new_locations_table(a: dict, b: dict) -> pd.DataFrame:
    new = new_locations(a["points"], b["points"])
    n_inside, n_outside = count_inside(new, a["hulls"])
    n_gsvi_hotspots = len(a["hulls"])
    n_retained, n_created = match_hotspots(a["hulls"], b["hulls"])
    retained_pct = 100.0 * n_retained / n_gsvi_hotspots if n_gsvi_hotspots else 0.0

    out = pd.DataFrame(
        [
            {"Metric": "New locations added", "Value": f"{len(new):,}"},
            {"Metric": "New locations inside existing hotspots", "Value": share(n_inside, len(new))},
            {"Metric": "New locations forming new hotspots", "Value": share(n_outside, len(new))},
            {"Metric": "Existing hotspots retained",
             "Value": f"{n_retained} / {n_gsvi_hotspots} ({retained_pct:.1f}%)"},
            {"Metric": "Newly created hotspots", "Value": f"{n_created:,}"},
        ]
    )
    out.to_csv(NEW_LOCATIONS_CSV, index=False)
    print(f"\n{out.to_string(index=False)}")
    print(f"Wrote {NEW_LOCATIONS_CSV}")
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"HDBSCAN (min_cluster_size={MIN_CLUSTER_SIZE}, min_samples={MIN_SAMPLES}), "
          "identical on both arms\n")

    gsvi = run_arm("gsvi")
    combined = run_arm("gsvi_selfcollected")

    build_comparison(gsvi, combined)
    build_new_locations_table(gsvi, combined)


if __name__ == "__main__":
    main()

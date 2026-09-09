#!/usr/bin/env python3
"""Descriptive n_positive_views summaries after HDBSCAN (sensitivity only).

Primary HDBSCAN still uses one point per waste-positive panoid.
This script joins directional-view counts and reports per-cluster summaries.
Does not re-run or re-weight clustering.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from panoid_locations import PATTERN_DIR, load_n_positive_views  # noqa: E402

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

CLUSTERED_GPKG = OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_32737.gpkg"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    if not CLUSTERED_GPKG.exists():
        raise SystemExit(
            f"Missing {CLUSTERED_GPKG}. Run 3_hdbscan_waste.py first."
        )

    print("HDBSCAN cluster × n_positive_views (descriptive)...")
    gdf = gpd.read_file(CLUSTERED_GPKG)
    gdf["panoid"] = gdf["panoid"].astype(str)
    n_views = load_n_positive_views()
    gdf["n_positive_views"] = gdf["panoid"].map(n_views).fillna(0).astype(int)

    enriched_path = OUTPUT_DIR / "Nairobi_waste_hdbscan_gsvi_with_views_32737.gpkg"
    gdf.to_file(enriched_path, driver="GPKG")

    overall = {
        "scope": "all_positive_panoramas",
        "n_panoids": int(len(gdf)),
        "mean_n_positive_views": float(gdf["n_positive_views"].mean()),
        "share_multi_view": float((gdf["n_positive_views"] >= 2).mean()),
        "n_multi_view": int((gdf["n_positive_views"] >= 2).sum()),
        "max_n_positive_views": int(gdf["n_positive_views"].max()),
    }

    clustered = gdf[gdf["HDB_cluster"] != -1].copy()
    noise = gdf[gdf["HDB_cluster"] == -1].copy()

    cluster_rows = []
    for cid, sub in clustered.groupby("HDB_cluster"):
        cluster_rows.append(
            {
                "HDB_cluster": int(cid),
                "n_panoids": int(len(sub)),
                "mean_n_positive_views": float(sub["n_positive_views"].mean()),
                "share_multi_view": float((sub["n_positive_views"] >= 2).mean()),
                "n_multi_view": int((sub["n_positive_views"] >= 2).sum()),
                "max_n_positive_views": int(sub["n_positive_views"].max()),
            }
        )
    cluster_rows.append(
        {
            "HDB_cluster": -1,
            "n_panoids": int(len(noise)),
            "mean_n_positive_views": float(noise["n_positive_views"].mean())
            if len(noise)
            else np_nan(),
            "share_multi_view": float((noise["n_positive_views"] >= 2).mean())
            if len(noise)
            else np_nan(),
            "n_multi_view": int((noise["n_positive_views"] >= 2).sum())
            if len(noise)
            else 0,
            "max_n_positive_views": int(noise["n_positive_views"].max())
            if len(noise)
            else 0,
        }
    )
    cluster_df = pd.DataFrame(cluster_rows).sort_values("HDB_cluster")
    cluster_path = OUTPUT_DIR / "Nairobi_hdbscan_cluster_n_positive_views.csv"
    cluster_df.to_csv(cluster_path, index=False)

    summary = pd.DataFrame(
        [
            overall,
            {
                "scope": "clustered_only",
                "n_panoids": int(len(clustered)),
                "mean_n_positive_views": float(clustered["n_positive_views"].mean())
                if len(clustered)
                else np_nan(),
                "share_multi_view": float((clustered["n_positive_views"] >= 2).mean())
                if len(clustered)
                else np_nan(),
                "n_multi_view": int((clustered["n_positive_views"] >= 2).sum())
                if len(clustered)
                else 0,
                "max_n_positive_views": int(clustered["n_positive_views"].max())
                if len(clustered)
                else 0,
            },
            {
                "scope": "noise_only",
                "n_panoids": int(len(noise)),
                "mean_n_positive_views": float(noise["n_positive_views"].mean())
                if len(noise)
                else np_nan(),
                "share_multi_view": float((noise["n_positive_views"] >= 2).mean())
                if len(noise)
                else np_nan(),
                "n_multi_view": int((noise["n_positive_views"] >= 2).sum())
                if len(noise)
                else 0,
                "max_n_positive_views": int(noise["n_positive_views"].max())
                if len(noise)
                else 0,
            },
        ]
    )
    summary_path = OUTPUT_DIR / "Nairobi_hdbscan_n_positive_views_summary.csv"
    summary.to_csv(summary_path, index=False)

    thesis_path = TABLE_DIR / "table_hdbscan_n_positive_views.csv"
    summary.to_csv(thesis_path, index=False)

    print(
        f"  Overall mean views={overall['mean_n_positive_views']:.2f} | "
        f"multi-view share={100 * overall['share_multi_view']:.1f}%"
    )
    print(f"Wrote {enriched_path}")
    print(f"Wrote {cluster_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {thesis_path}")


def np_nan() -> float:
    return float("nan")


if __name__ == "__main__":
    main()

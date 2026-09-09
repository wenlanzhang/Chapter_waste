#!/usr/bin/env python3
"""Period-stratified HDBSCAN on waste-positive GSVI panoids (temporal robustness).

Same HDBSCAN parameters as the main analysis:
  min_cluster_size = 25
  min_samples = 6

Periods:
  2015–2019 and 2021–2022 waste-positive panoids (GSVI only).
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import hdbscan
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))

from panoid_locations import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
)

OUTPUT_DIR = PATTERN_DIR / "HDBSCAN" / "period_stratified_robustness"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

MIN_CLUSTER_SIZE = 25
MIN_SAMPLES = 6

PERIODS = {
    "2015_2019": {
        "label": "2015–2019",
        "years": {2015, 2016, 2017, 2018, 2019},
    },
    "2021_2022": {
        "label": "2021–2022",
        "years": {2021, 2022},
    },
}


def prepare_waste_by_period() -> gpd.GeoDataFrame:
    """Waste-positive GSVI panoids with capture year and period label."""
    points = enrich_sviwaste_frame()
    waste = points.loc[points["waste_positive"] == 1].copy()
    waste["year"] = pd.to_numeric(waste["year"], errors="coerce")
    waste = waste.dropna(subset=["year"]).copy()
    waste["year"] = waste["year"].astype(int)

    def _period(y: int) -> str | None:
        for key, meta in PERIODS.items():
            if y in meta["years"]:
                return key
        return None

    waste["period"] = waste["year"].map(_period)
    waste = waste.loc[waste["period"].notna()].copy()
    waste["location_kind"] = "gsvi_panoid"
    return waste.reset_index(drop=True)


def run_hdbscan(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    coords = np.column_stack([gdf.geometry.x, gdf.geometry.y])
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        gen_min_span_tree=True,
    )
    labels = clusterer.fit_predict(coords)

    out = gdf.copy()
    out["HDB_cluster"] = labels

    n_noise = int((labels == -1).sum())
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_pts = int(len(labels))
    n_clustered = n_pts - n_noise
    summary = {
        "min_cluster_size": MIN_CLUSTER_SIZE,
        "min_samples": MIN_SAMPLES,
        "n_waste_positive": n_pts,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "n_clustered": n_clustered,
        "pct_waste_points_clustered": 100.0 * n_clustered / n_pts if n_pts else np.nan,
        "noise_ratio": n_noise / n_pts if n_pts else np.nan,
        "unit": "waste_positive_panoid",
    }
    return out, summary


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {OUTPUT_DIR}")
    print("Period-stratified HDBSCAN (waste-positive GSVI panoids)...")
    waste = prepare_waste_by_period()

    # Full period denominator (all panoids, not just waste+)
    all_pts = enrich_sviwaste_frame()
    all_pts["year"] = pd.to_numeric(all_pts["year"], errors="coerce")
    all_pts = all_pts.dropna(subset=["year"]).copy()
    all_pts["year"] = all_pts["year"].astype(int)

    summaries: list[dict] = []
    for key, meta in PERIODS.items():
        sub = waste.loc[waste["period"] == key].copy()
        n_all = int(all_pts["year"].isin(meta["years"]).sum())
        print(f"\n[{meta['label']}] waste+ panoids: {len(sub):,} | period GSVI: {n_all:,}")

        if len(sub) < MIN_CLUSTER_SIZE:
            print("  Too few waste-positive panoids; skipping HDBSCAN")
            summaries.append(
                {
                    "period": key,
                    "period_label": meta["label"],
                    "years": "|".join(str(y) for y in sorted(meta["years"])),
                    "n_gsvi_panoids": n_all,
                    "n_waste_positive": int(len(sub)),
                    "n_clusters": 0,
                    "n_noise": int(len(sub)),
                    "n_clustered": 0,
                    "pct_waste_points_clustered": 0.0 if len(sub) else np.nan,
                    "noise_ratio": 1.0 if len(sub) else np.nan,
                    "min_cluster_size": MIN_CLUSTER_SIZE,
                    "min_samples": MIN_SAMPLES,
                    "note": "skipped_too_few_points",
                }
            )
            continue

        clustered, summary = run_hdbscan(sub)
        summary["period"] = key
        summary["period_label"] = meta["label"]
        summary["years"] = "|".join(str(y) for y in sorted(meta["years"]))
        summary["n_gsvi_panoids"] = n_all

        gpkg = OUTPUT_DIR / f"Nairobi_waste_hdbscan_{key}_32737.gpkg"
        clustered.to_file(gpkg, driver="GPKG")
        print(f"  Wrote {gpkg}")
        print(
            f"  Clusters: {summary['n_clusters']} | "
            f"clustered: {summary['n_clustered']:,} "
            f"({summary['pct_waste_points_clustered']:.1f}%) | "
            f"noise: {summary['n_noise']:,}"
        )
        summaries.append(summary)

        stand_summary = OUTPUT_DIR / f"Nairobi_waste_hdbscan_summary_{key}.csv"
        pd.DataFrame([summary]).to_csv(stand_summary, index=False)
        print(f"  Wrote {stand_summary}")

    summary_df = pd.DataFrame(summaries)
    # Friendly column order for the reviewer-style table
    col_order = [
        "period_label",
        "years",
        "n_gsvi_panoids",
        "n_waste_positive",
        "n_clusters",
        "n_clustered",
        "pct_waste_points_clustered",
        "n_noise",
        "noise_ratio",
        "min_cluster_size",
        "min_samples",
        "period",
        "unit",
    ]
    ordered = [c for c in col_order if c in summary_df.columns]
    ordered += [c for c in summary_df.columns if c not in ordered]
    summary_df = summary_df[ordered]

    comparison_path = OUTPUT_DIR / "Nairobi_period_hdbscan_summary.csv"
    summary_df.to_csv(comparison_path, index=False)
    print(f"\nWrote {comparison_path}")

    thesis_rows = []
    for _, row in summary_df.iterrows():
        label = row.get("period_label", row.get("period", ""))
        thesis_rows.extend(
            [
                (f"{label}: GSVI panoids", f"{int(row['n_gsvi_panoids']):,}", ""),
                (
                    f"{label}: waste-positive",
                    f"{int(row['n_waste_positive']):,}",
                    "",
                ),
                (f"{label}: HDBSCAN clusters", f"{int(row['n_clusters'])}", ""),
                (
                    f"{label}: % waste points clustered",
                    f"{float(row['pct_waste_points_clustered']):.1f}",
                    "%",
                ),
            ]
        )
    thesis_rows.append(
        (
            "HDBSCAN parameters",
            f"min_cluster_size={MIN_CLUSTER_SIZE}, min_samples={MIN_SAMPLES}",
            "",
        )
    )
    thesis_rows.append(
        (
            "Interpretation",
            "Period-stratified hotspots; not evidence of temporal persistence",
            "",
        )
    )
    thesis_path = TABLE_DIR / "table_period_hdbscan.csv"
    pd.DataFrame(thesis_rows, columns=["Variable", "Value", "Unit"]).to_csv(
        thesis_path, index=False
    )
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Optional: join GSVI panoids to Nairobi SE admin polygons and summarise.

Port of the core workflow in SVI_Waste/Code/SVI/SVI_Social_economic.ipynb,
re-expressed on the chapter panorama unit (Step 2c sviwaste points).

Not part of Snakemake ``all``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from shapely import wkt

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import optional_se_dir, waste_raw_dir  # noqa: E402
from lib.panoids import enrich_sviwaste_frame  # noqa: E402

SE_DROP_COLS = ["index", "source_id", "location", "sublocation"]
# Covariates highlighted in the original notebook + a few stable density/wealth proxies.
FOCUS_COVARIATES = [
    "density_pop",
    "grdi",
    "nr_buildings",
    "rwi_weight",
    "area_pop",
    "area_young_share",
    "density_building",
    "density_gsm",
    "mean_ndvi",
    "mean_ghm",
    "shdi",
    "imr",
    "built",
]


def se_csv_path(year: int) -> Path:
    return waste_raw_dir() / "SE" / f"cleaned_Nairobi_{year}.csv"


def load_se_polygons(year: int) -> gpd.GeoDataFrame:
    path = se_csv_path(year)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    drop = [c for c in SE_DROP_COLS if c in df.columns]
    df = df.drop(columns=drop).reset_index(drop=True)
    df["admin_id"] = df.index.astype(int)
    df["geometry"] = df["geometry"].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.to_crs(epsg=32737)
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.is_valid].copy()
    gdf["area_km2"] = gdf.geometry.area / 1e6
    return gdf


def summarise_by_admin(
    points: gpd.GeoDataFrame,
    se: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    joined = gpd.sjoin(
        points[["panoid", "waste_positive", "geometry"]],
        se[["admin_id", "geometry"]],
        how="inner",
        predicate="within",
    )
    if joined.empty:
        raise RuntimeError("No panoids fell inside SE admin polygons.")

    agg = (
        joined.groupby("admin_id", as_index=False)
        .agg(
            panoid_count=("panoid", "size"),
            waste_positive_panoids=("waste_positive", "sum"),
        )
    )
    agg["waste_positive_rate"] = np.where(
        agg["panoid_count"] > 0,
        agg["waste_positive_panoids"] / agg["panoid_count"],
        np.nan,
    )

    out = se.merge(agg, on="admin_id", how="left")
    out["panoid_count"] = out["panoid_count"].fillna(0).astype(int)
    out["waste_positive_panoids"] = out["waste_positive_panoids"].fillna(0).astype(int)
    out["waste_positive_rate"] = out["waste_positive_rate"].fillna(0.0)
    out["waste_density_per_km2"] = np.where(
        out["area_km2"] > 0,
        out["waste_positive_panoids"] / out["area_km2"],
        np.nan,
    )
    out["waste_rate_per_km2"] = np.where(
        out["area_km2"] > 0,
        out["waste_positive_rate"] / out["area_km2"],
        np.nan,
    )
    # Units with no SVI coverage stay in the layer but are flagged for correlation subset.
    out["has_svi"] = out["panoid_count"] > 0
    return out


def correlation_table(gdf: gpd.GeoDataFrame, target: str = "waste_positive_rate") -> pd.DataFrame:
    work = gdf.loc[gdf["has_svi"]].copy()
    rows: list[dict] = []
    for col in FOCUS_COVARIATES:
        if col not in work.columns:
            continue
        pair = work[[target, col]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(pair) < 10:
            continue
        if pair[col].nunique() < 2 or pair[target].nunique() < 2:
            continue
        r, p = pearsonr(pair[target], pair[col])
        rows.append(
            {
                "target": target,
                "covariate": col,
                "n_admin_units": int(len(pair)),
                "pearson_r": float(r),
                "p_value": float(p),
                "abs_r": float(abs(r)),
            }
        )
    table = pd.DataFrame(rows).sort_values("abs_r", ascending=False)
    return table.drop(columns=["abs_r"])


def global_moran(gdf: gpd.GeoDataFrame, column: str = "waste_positive_rate") -> pd.DataFrame:
    try:
        import libpysal
        from esda import Moran
    except ImportError:
        return pd.DataFrame(
            [{"metric": "Moran_I", "value": np.nan, "p_sim": np.nan, "note": "libpysal/esda unavailable"}]
        )

    work = gdf.loc[gdf["has_svi"] & gdf[column].notna()].copy().reset_index(drop=True)
    if len(work) < 10:
        return pd.DataFrame(
            [{"metric": "Moran_I", "value": np.nan, "p_sim": np.nan, "note": "too few units"}]
        )

    w = libpysal.weights.Queen.from_dataframe(work, use_index=False)
    w.transform = "r"
    if w.islands:
        work = work.drop(index=list(w.islands)).reset_index(drop=True)
        w = libpysal.weights.Queen.from_dataframe(work, use_index=False)
        w.transform = "r"
    moran = Moran(work[column].to_numpy(), w)
    return pd.DataFrame(
        [
            {
                "metric": "Moran_I",
                "value": float(moran.I),
                "p_sim": float(moran.p_sim),
                "n_admin_units": int(len(work)),
                "note": column,
            }
        ]
    )


def summary_table(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    covered = gdf.loc[gdf["has_svi"]]
    rate = covered["waste_positive_rate"]
    return pd.DataFrame(
        [
            {"variable": "admin_units_total", "value": float(len(gdf)), "unit": "count"},
            {"variable": "admin_units_with_svi", "value": float(len(covered)), "unit": "count"},
            {"variable": "panoids_joined", "value": float(gdf["panoid_count"].sum()), "unit": "count"},
            {
                "variable": "waste_positive_panoids_joined",
                "value": float(gdf["waste_positive_panoids"].sum()),
                "unit": "count",
            },
            {"variable": "mean_waste_positive_rate", "value": float(rate.mean()), "unit": "share"},
            {"variable": "median_waste_positive_rate", "value": float(rate.median()), "unit": "share"},
            {"variable": "sd_waste_positive_rate", "value": float(rate.std(ddof=1)), "unit": "share"},
        ]
    )


def run(year: int) -> None:
    out_dir = optional_se_dir()
    table_dir = out_dir / "thesis_table"
    out_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading SE polygons ({year})...")
    se = load_se_polygons(year)
    print(f"  {len(se):,} admin units")

    print("Loading GSVI panoids (Step 2c)...")
    points = enrich_sviwaste_frame()
    n_pos = int((points["waste_positive"] == 1).sum())
    print(f"  {len(points):,} panoids | {n_pos:,} waste-positive")

    print("Spatial join + metrics...")
    gdf = summarise_by_admin(points, se)
    n_covered = int(gdf["has_svi"].sum())
    print(f"  {n_covered:,}/{len(gdf):,} units contain ≥1 panoid")

    stem = f"Nairobi_admin_se_waste_{year}"
    gpkg_path = out_dir / f"{stem}.gpkg"
    csv_path = out_dir / f"{stem}.csv"
    gdf.to_file(gpkg_path, driver="GPKG")
    gdf.drop(columns="geometry").to_csv(csv_path, index=False)
    print(f"Wrote {gpkg_path}")
    print(f"Wrote {csv_path}")

    corr = correlation_table(gdf)
    corr_path = table_dir / f"se_waste_correlations_{year}.csv"
    corr.to_csv(corr_path, index=False)
    print(f"Wrote {corr_path}")
    if not corr.empty:
        top = corr.iloc[0]
        print(
            f"  strongest |r|: {top['covariate']} "
            f"r={top['pearson_r']:.3f} p={top['p_value']:.3g}"
        )

    summary = summary_table(gdf)
    summary_path = table_dir / f"se_waste_summary_{year}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}")

    moran = global_moran(gdf)
    moran_path = table_dir / f"se_moran_{year}.csv"
    moran.to_csv(moran_path, index=False)
    print(f"Wrote {moran_path}")
    if pd.notna(moran.loc[0, "value"]):
        print(f"  Moran I={moran.loc[0, 'value']:.4f} p_sim={moran.loc[0, 'p_sim']:.4f}")

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        default=2019,
        choices=[2019, 2023],
        help="SE table year (default: 2019)",
    )
    args = parser.parse_args()
    run(args.year)


if __name__ == "__main__":
    main()

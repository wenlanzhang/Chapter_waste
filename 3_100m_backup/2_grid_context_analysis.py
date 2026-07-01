"""
Stratified context analysis for 100 m grid waste/SVI ratio (gsvi vs g+self).

Assigns overlapping context flags per cell, merges both arms, and writes
summary tables plus a merged GeoPackage for maps.

Outputs (no duplicates):
  thesis_table/  — stratified comparison + class-changed transition (thesis)
  3_100m/        — full-detail stratified + all-cell transition (QA)
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from grid_classification import CLASS_LABELS

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GSVI_GPKG = OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_32737.gpkg"
SC_GPKG = OUTPUT_DIR / "Nairobi_grid_waste_ratio_gsvi_selfcollected_32737.gpkg"
ROAD_GPKG = INPUT_DIR / "Nairobi_road_line_32737.gpkg"
MERGED_GPKG = OUTPUT_DIR / "Nairobi_grid_waste_ratio_context_32737.gpkg"

THESIS_STRATIFIED_CSV = TABLE_DIR / "Nairobi_grid_waste_ratio_context_stratified.csv"
THESIS_TRANSITION_CSV = TABLE_DIR / "Nairobi_grid_waste_ratio_class_transition.csv"
DETAIL_STRATIFIED_CSV = OUTPUT_DIR / "Nairobi_grid_waste_ratio_context_detail.csv"
DETAIL_TRANSITION_CSV = OUTPUT_DIR / "Nairobi_grid_waste_ratio_class_transition_all_cells.csv"

ROAD_MIN_M = 25.0

STRATIFIED_ROWS = [
    ("city", "City-wide", "ctx_citywide"),
    ("road", "Road (≥25 m)", "ctx_road"),
    ("svi", "SVI (≥1 GSVI image)", "ctx_svi"),
    ("waste", "Waste detected (either arm)", "ctx_waste"),
    ("self_collected", "Self-collected touch", "ctx_improvement"),
    ("self_collected_waste", "Self-collected new waste", "ctx_new_waste"),
    ("class_changed", "Class changed (any shift)", "ctx_class_changed"),
    ("band_shift", "Band shift (had GSVI, level changed)", "ctx_band_shift"),
    ("new_coverage", "New coverage (no GSVI → level)", "ctx_new_coverage"),
]

LEVELS = list(range(4))

# Obsolete outputs removed by cleanup (do not recreate)
OBSOLETE_OUTPUTS = [
    OUTPUT_DIR / "Nairobi_grid_waste_ratio_context_summary.csv",
    TABLE_DIR / "Nairobi_grid_waste_ratio_context_comparison.csv",
    TABLE_DIR / "Nairobi_grid_waste_ratio_class_transition_matrix.csv",
    TABLE_DIR / "Nairobi_grid_waste_ratio_class_transition_class_changed.csv",
    TABLE_DIR / "Nairobi_grid_waste_ratio_class_transition_matrix_wide.csv",
]


def road_length_by_cell(grid: gpd.GeoDataFrame, roads: gpd.GeoDataFrame) -> pd.Series:
    grid = grid.reset_index(drop=True).copy()
    grid["_grid_idx"] = grid.index
    road_cells = gpd.overlay(
        roads[["geometry"]].copy(),
        grid[["_grid_idx", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    road_cells = road_cells.explode(index_parts=False).reset_index(drop=True)
    road_cells = road_cells[road_cells.geometry.length > 0]
    lengths = road_cells.groupby("_grid_idx")["geometry"].apply(
        lambda geoms: float(geoms.length.sum())
    )
    return grid.index.to_series().map(lengths).fillna(0.0)


def load_arm(path: Path, prefix: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    rename = {
        "waste_points": f"waste_{prefix}",
        "total_svi_images": f"svi_{prefix}",
        "waste_ratio": f"ratio_{prefix}",
        "final_waste_ratio": f"final_{prefix}",
        "result": f"result_{prefix}",
    }
    keep = ["cell_id", "geometry", *rename.keys()]
    missing = [c for c in keep if c not in gdf.columns]
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")
    return gdf[keep].rename(columns=rename)


def build_merged_frame(gsvi: gpd.GeoDataFrame, sc: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    merged = gsvi.merge(
        sc.drop(columns=["geometry"]),
        on="cell_id",
        how="inner",
        validate="one_to_one",
    )
    merged["delta_svi"] = merged["svi_sc"] - merged["svi_gsvi"]
    merged["delta_waste"] = merged["waste_sc"] - merged["waste_gsvi"]
    merged["delta_final"] = merged["final_sc"] - merged["final_gsvi"]

    merged["ctx_citywide"] = np.uint8(1)
    merged["ctx_road"] = np.uint8(0)
    merged["ctx_svi"] = np.uint8(merged["svi_gsvi"] >= 1)
    merged["ctx_waste"] = np.uint8(
        (merged["waste_gsvi"] > 0) | (merged["waste_sc"] > 0)
    )
    merged["ctx_improvement"] = np.uint8(
        (merged["delta_svi"] > 0) | (merged["delta_waste"] > 0)
    )
    merged["ctx_new_waste"] = np.uint8(merged["delta_waste"] > 0)
    merged["ctx_class_changed"] = np.uint8(merged["result_gsvi"] != merged["result_sc"])
    merged["ctx_band_shift"] = np.uint8(
        (merged["ctx_class_changed"] == 1) & (merged["svi_gsvi"] >= 1)
    )
    merged["ctx_new_coverage"] = np.uint8(
        (merged["ctx_class_changed"] == 1) & (merged["svi_gsvi"] == 0)
    )
    return merged


def pooled_ratio(waste: pd.Series, svi: pd.Series) -> float:
    total_svi = float(svi.sum())
    if total_svi <= 0:
        return float("nan")
    return float(waste.sum()) / total_svi


def pct(n: int, denom: int) -> float:
    if denom <= 0:
        return float("nan")
    return 100.0 * n / denom


def summarise_row(df: gpd.GeoDataFrame, slug: str, label: str, flag_col: str) -> dict:
    sub = df[df[flag_col] == 1]
    n = len(sub)
    pooled_gsvi = pooled_ratio(sub["waste_gsvi"], sub["svi_gsvi"])
    pooled_sc = pooled_ratio(sub["waste_sc"], sub["svi_sc"])
    delta_pooled = (
        pooled_sc - pooled_gsvi
        if pd.notna(pooled_gsvi) and pd.notna(pooled_sc)
        else float("nan")
    )

    n_class = int(sub["ctx_class_changed"].sum())
    return {
        "context": slug,
        "label": label,
        "n_cells": n,
        "waste_gsvi": int(sub["waste_gsvi"].sum()),
        "svi_gsvi": int(sub["svi_gsvi"].sum()),
        "waste_sc": int(sub["waste_sc"].sum()),
        "svi_sc": int(sub["svi_sc"].sum()),
        "pooled_ratio_gsvi": pooled_gsvi,
        "pooled_ratio_sc": pooled_sc,
        "pooled_ratio_gsvi_pct": 100.0 * pooled_gsvi if pd.notna(pooled_gsvi) else float("nan"),
        "pooled_ratio_sc_pct": 100.0 * pooled_sc if pd.notna(pooled_sc) else float("nan"),
        "delta_pooled_pct_points": 100.0 * delta_pooled if pd.notna(delta_pooled) else float("nan"),
        "n_class_changed": n_class,
        "pct_class_changed": pct(n_class, n),
        "n_band_shift": int(sub["ctx_band_shift"].sum()),
        "pct_band_shift": pct(int(sub["ctx_band_shift"].sum()), n),
        "n_new_coverage": int(sub["ctx_new_coverage"].sum()),
        "pct_new_coverage": pct(int(sub["ctx_new_coverage"].sum()), n),
        "n_new_waste": int(sub["ctx_new_waste"].sum()),
        "pct_new_waste": pct(int(sub["ctx_new_waste"].sum()), n),
    }


def to_thesis_stratified(detail: pd.DataFrame) -> pd.DataFrame:
    out = detail.copy()
    for col in (
        "pooled_ratio_gsvi_pct",
        "pooled_ratio_sc_pct",
        "delta_pooled_pct_points",
        "pct_class_changed",
    ):
        out[col] = out[col].round(2)
    return out[
        [
            "label",
            "n_cells",
            "pooled_ratio_gsvi_pct",
            "pooled_ratio_sc_pct",
            "delta_pooled_pct_points",
            "n_class_changed",
            "pct_class_changed",
            "n_new_coverage",
            "n_band_shift",
            "n_new_waste",
        ]
    ]


def build_transition_matrix(
    df: gpd.GeoDataFrame,
    *,
    only_changed: bool = False,
) -> pd.DataFrame:
    sub = df if not only_changed else df[df["ctx_class_changed"] == 1]

    full = pd.MultiIndex.from_product([LEVELS, LEVELS], names=["result_gsvi", "result_sc"])
    counts = (
        sub.groupby(["result_gsvi", "result_sc"], observed=True)
        .size()
        .reindex(full, fill_value=0)
        .reset_index(name="n_cells")
    )
    counts["gsvi_label"] = counts["result_gsvi"].map(CLASS_LABELS)
    counts["sc_label"] = counts["result_sc"].map(CLASS_LABELS)
    counts["transition"] = counts["gsvi_label"] + " → " + counts["sc_label"]

    denom = int(counts["n_cells"].sum())
    counts["pct_of_subset"] = counts["n_cells"].apply(
        lambda x: 100.0 * x / denom if denom else float("nan")
    )
    return counts


def to_thesis_transition(changed: pd.DataFrame) -> pd.DataFrame:
    out = changed[changed["n_cells"] > 0].copy()
    out["pct_of_class_changed"] = out["pct_of_subset"].round(1)
    return out.sort_values("n_cells", ascending=False)[
        ["transition", "n_cells", "pct_of_class_changed"]
    ]


def remove_obsolete_outputs() -> None:
    for path in OBSOLETE_OUTPUTS:
        if path.exists():
            path.unlink()
            print(f"Removed obsolete {path.name}")


def print_stratified_table(thesis: pd.DataFrame) -> None:
    print("\nStratified comparison (thesis table)")
    print("-" * 95)
    for _, row in thesis.iterrows():
        gsvi = row["pooled_ratio_gsvi_pct"]
        sc = row["pooled_ratio_sc_pct"]
        gsvi_s = f"{gsvi:.2f}%" if pd.notna(gsvi) else "—"
        sc_s = f"{sc:.2f}%" if pd.notna(sc) else "—"
        delta = row["delta_pooled_pct_points"]
        delta_s = f"{delta:+.2f}pp" if pd.notna(delta) else "—"
        print(
            f"  {row['label']:<40}  n={row['n_cells']:>6,}  "
            f"GSVI {gsvi_s:>7}  G+self {sc_s:>7}  Δ {delta_s:>8}  "
            f"classΔ {row['n_class_changed']:>4} ({row['pct_class_changed']:>5.1f}%)  "
            f"cov {row['n_new_coverage']:>3}  band {row['n_band_shift']:>3}  "
            f"newW {row['n_new_waste']:>3}"
        )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    remove_obsolete_outputs()

    print("Loading arm outputs...")
    gsvi = load_arm(GSVI_GPKG, "gsvi")
    sc = load_arm(SC_GPKG, "sc")

    print("Merging arms and assigning context flags...")
    merged = build_merged_frame(gsvi, sc)

    print("Computing road length per cell...")
    roads = gpd.read_file(ROAD_GPKG)
    merged["road_length_m"] = road_length_by_cell(merged, roads).values
    merged["ctx_road"] = np.uint8(merged["road_length_m"] >= ROAD_MIN_M)

    print(f"Writing {MERGED_GPKG.name}...")
    merged.to_file(MERGED_GPKG, driver="GPKG")

    detail_df = pd.DataFrame(
        [summarise_row(merged, slug, label, flag) for slug, label, flag in STRATIFIED_ROWS]
    )
    thesis_stratified = to_thesis_stratified(detail_df)
    thesis_stratified.to_csv(THESIS_STRATIFIED_CSV, index=False)
    detail_df.to_csv(DETAIL_STRATIFIED_CSV, index=False)
    print(f"Wrote {THESIS_STRATIFIED_CSV.name} (thesis)")
    print(f"Wrote {DETAIL_STRATIFIED_CSV.name} (detail)")

    transition_all = build_transition_matrix(merged, only_changed=False)
    transition_changed = build_transition_matrix(merged, only_changed=True)
    thesis_transition = to_thesis_transition(transition_changed)
    thesis_transition.to_csv(THESIS_TRANSITION_CSV, index=False)
    transition_all.to_csv(DETAIL_TRANSITION_CSV, index=False)
    print(f"Wrote {THESIS_TRANSITION_CSV.name} (thesis)")
    print(f"Wrote {DETAIL_TRANSITION_CSV.name} (detail)")

    print_stratified_table(thesis_stratified)

    print("\nClass transitions (thesis table)")
    for _, row in thesis_transition.iterrows():
        print(
            f"  {row['transition']:<45}  n={int(row['n_cells']):>4}  "
            f"({row['pct_of_class_changed']:>5.1f}%)"
        )


if __name__ == "__main__":
    main()

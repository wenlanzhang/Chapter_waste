"""
100 m IDEAMaps grid coverage — cell counts and nested coverage matrix.

Uses the Nairobi-clipped Angela 100 m grid (Step 1) and assigns road, SVI image,
and waste detection coverage per cell. Writes thesis tables and a GeoPackage for
downstream maps.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "3_100m"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GRID_GPKG = INPUT_DIR / "Nairobi_grid_100m_32737.gpkg"
ROAD_GPKG = INPUT_DIR / "Nairobi_road_line_32737.gpkg"
SVI_GPKG = INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg"
WASTE_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"

COVERAGE_GPKG = OUTPUT_DIR / "Nairobi_grid_coverage_32737.gpkg"
CELL_COUNTS_CSV = TABLE_DIR / "Nairobi_grid_coverage_cell_counts.csv"
MATRIX_CSV = TABLE_DIR / "Nairobi_grid_coverage_matrix_pct.csv"
MATRIX_LONG_CSV = OUTPUT_DIR / "Nairobi_grid_coverage_matrix_long.csv"

ROAD_MIN_M = 25.0

CONTEXTS = [
    ("city", "City", "ctx_city"),
    ("road", "Road (>=25 m)", "ctx_road"),
    ("svi", "SVI (>=1 image)", "ctx_svi"),
    ("waste", "Waste (>=1 detection)", "ctx_waste"),
]


def count_points_in_grid(
    grid: gpd.GeoDataFrame, points: gpd.GeoDataFrame, value_col: str
) -> gpd.GeoDataFrame:
    grid = grid.reset_index(drop=True).copy()
    grid["_grid_idx"] = grid.index

    joined = gpd.sjoin(
        points, grid[["_grid_idx", "geometry"]], how="inner", predicate="within"
    )
    counts = joined.groupby("_grid_idx").size().rename(value_col)

    out = grid.drop(columns=["_grid_idx"], errors="ignore")
    out[value_col] = out.index.map(counts).fillna(0).astype(int)
    return out


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


def assign_context_flags(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = grid.copy()
    out["road_length_m"] = road_length_by_cell(out, gpd.read_file(ROAD_GPKG))
    out = count_points_in_grid(out, gpd.read_file(SVI_GPKG), "svi_images")
    out = count_points_in_grid(out, gpd.read_file(WASTE_GPKG), "waste_images")

    out["ctx_city"] = np.uint8(1)
    out["ctx_road"] = np.uint8(out["road_length_m"] >= ROAD_MIN_M)
    out["ctx_svi"] = np.uint8(out["svi_images"] >= 1)
    out["ctx_waste"] = np.uint8(out["waste_images"] >= 1)
    return out


def build_cell_counts_table(grid: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    for _slug, label, flag_col in CONTEXTS:
        rows.append(
            {
                "Context": label,
                "Grid cells": int(grid[flag_col].sum()),
            }
        )
    table = pd.DataFrame(rows)
    table["Grid cells"] = table["Grid cells"].map(lambda n: f"{n:,}")
    return table


def build_coverage_matrix(grid: gpd.GeoDataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    flag_cols = [flag_col for _, _, flag_col in CONTEXTS]
    labels = [label for _, label, _ in CONTEXTS]
    masks = {flag_col: grid[flag_col].astype(bool).to_numpy() for flag_col in flag_cols}

    wide_rows = []
    long_rows = []
    for row_slug, row_label, row_flag in CONTEXTS:
        row = {"Context": row_label}
        row_mask = masks[row_flag]
        for col_slug, col_label, col_flag in CONTEXTS:
            col_mask = masks[col_flag]
            n_col = int(col_mask.sum())
            n_both = int((row_mask & col_mask).sum())
            pct = 100.0 * n_both / n_col if n_col > 0 else float("nan")
            row[col_label] = round(pct, 1)
            long_rows.append(
                {
                    "row_context": row_label,
                    "col_context": col_label,
                    "n_cells": n_both,
                    "n_col_cells": n_col,
                    "pct_of_col": round(pct, 1),
                }
            )
        wide_rows.append(row)

    return pd.DataFrame(wide_rows), pd.DataFrame(long_rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    grid = gpd.read_file(GRID_GPKG)
    if "cell_id" not in grid.columns:
        raise ValueError(f"{GRID_GPKG.name} must include a cell_id column")

    grid = assign_context_flags(grid)
    grid.to_file(COVERAGE_GPKG, driver="GPKG")

    counts_table = build_cell_counts_table(grid)
    matrix_wide, matrix_long = build_coverage_matrix(grid)

    counts_table.to_csv(CELL_COUNTS_CSV, index=False)
    matrix_wide.to_csv(MATRIX_CSV, index=False)
    matrix_long.to_csv(MATRIX_LONG_CSV, index=False)

    print(f"Wrote {COVERAGE_GPKG}")
    print(f"Wrote {CELL_COUNTS_CSV}")
    print(f"Wrote {MATRIX_CSV}")
    print(f"Wrote {MATRIX_LONG_CSV}")
    print()
    print("Cell counts:")
    print(counts_table.to_string(index=False))
    print()
    print("Coverage matrix (% of column context):")
    print(matrix_wide.to_string(index=False))


if __name__ == "__main__":
    main()

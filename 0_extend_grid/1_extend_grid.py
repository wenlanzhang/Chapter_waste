#!/usr/bin/env python3
"""
Extend Angela's 100 m grid using the IDEAMaps / GHSL Mollweide fishnet.

Docs: https://www.ideamapsdataecosystem.org/docs/our-data/the-grid
  - 100 x 100 m cells
  - Mollweide / GHSL reference system ESRI:54009

Angela's IDEAmaps_grid-boundary-nairobi.gpkg is an exact 100 m square lattice
in ESRI:54009 (global origin). This script keeps existing clipped Angela cells
and cell_id values, and fills constituency gaps with new Mollweide 100 m cells.

Standalone experiment — does not modify Step 1 / 3_100m outputs.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste")
INPUT_DIR = DATA_ROOT / "1prepare_chapter_data"
RAW_ANGELA = Path(
    "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Waste/Angela/"
    "IDEAmaps_grid-boundary-nairobi.gpkg"
)
OUTPUT_DIR = DATA_ROOT / "0_extend_grid"

CLIPPED_GRID = INPUT_DIR / "Nairobi_grid_100m_32737.gpkg"
BOUNDARY_GPKG = INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg"

OUT_GRID = OUTPUT_DIR / "Nairobi_grid_100m_extended_32737.gpkg"
OUT_NEW = OUTPUT_DIR / "Nairobi_grid_100m_extension_cells_32737.gpkg"
OUT_SUMMARY = OUTPUT_DIR / "Nairobi_grid_extension_summary.csv"

CRS_MOLL = "ESRI:54009"
CRS_EA = "EPSG:32737"
CELL_M = 100.0
SOURCE_ANGELA = "angela_original"
SOURCE_EXTENSION = "extension_mollweide_100m"


def existing_index_pairs(raw_moll: gpd.GeoDataFrame) -> set[tuple[int, int]]:
    """Global 100 m indices from lower-left corners (origin 0,0)."""
    llx = np.array([g.bounds[0] for g in raw_moll.geometry])
    lly = np.array([g.bounds[1] for g in raw_moll.geometry])
    ix = np.round(llx / CELL_M).astype(int)
    iy = np.round(lly / CELL_M).astype(int)
    return set(zip(ix.tolist(), iy.tolist()))


def build_mollweide_fill(
    boundary_moll,
    existing_pairs: set[tuple[int, int]],
) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = boundary_moll.bounds
    ix0 = int(np.floor(minx / CELL_M)) - 1
    ix1 = int(np.ceil(maxx / CELL_M)) + 1
    iy0 = int(np.floor(miny / CELL_M)) - 1
    iy1 = int(np.ceil(maxy / CELL_M)) + 1

    geoms = []
    for iy in range(iy0, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            if (ix, iy) in existing_pairs:
                continue
            x0 = ix * CELL_M
            y0 = iy * CELL_M
            cell = box(x0, y0, x0 + CELL_M, y0 + CELL_M)
            if cell.centroid.within(boundary_moll):
                geoms.append(cell)

    return gpd.GeoDataFrame({"geometry": geoms}, geometry="geometry", crs=CRS_MOLL)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading grids (Mollweide ESRI:54009 = IDEAMaps/GHSL)...")
    clipped = gpd.read_file(CLIPPED_GRID).to_crs(CRS_EA)
    raw = gpd.read_file(RAW_ANGELA)
    boundary_ea = gpd.read_file(BOUNDARY_GPKG).to_crs(CRS_EA)

    if "cell_id" not in clipped.columns:
        raise ValueError(f"{CLIPPED_GRID.name} must include cell_id")

    clipped = clipped.copy()
    clipped["cell_id"] = clipped["cell_id"].astype(int)
    clipped["grid_source"] = SOURCE_ANGELA

    raw_moll = raw.to_crs(CRS_MOLL)
    boundary_moll = unary_union(boundary_ea.to_crs(CRS_MOLL).geometry)
    existing = existing_index_pairs(raw_moll)
    print(f"  Angela clipped cells: {len(clipped):,}")
    print(f"  Raw Angela Mollweide cells: {len(raw_moll):,}")
    print(f"  Unique 100 m index pairs: {len(existing):,}")

    print("Building Mollweide 100 m fill...")
    new_moll = build_mollweide_fill(boundary_moll, existing)
    print(f"  New Mollweide cells: {len(new_moll):,}")
    if len(new_moll) == 0:
        raise RuntimeError("No Mollweide extension cells generated.")

    new_ea = new_moll.to_crs(CRS_EA)
    angela_u = unary_union(clipped.geometry)
    keep = ~new_ea.geometry.centroid.within(angela_u)
    new_ea = new_ea.loc[keep].copy().reset_index(drop=True)
    print(f"  After dropping centroids inside Angela clip: {len(new_ea):,}")

    max_id = int(clipped["cell_id"].max())
    new_ea["cell_id"] = np.arange(max_id + 1, max_id + 1 + len(new_ea), dtype=int)
    new_ea["grid_source"] = SOURCE_EXTENSION
    new_out = new_ea[["cell_id", "grid_source", "geometry"]]

    extended = gpd.GeoDataFrame(
        pd.concat(
            [clipped[["cell_id", "grid_source", "geometry"]], new_out],
            ignore_index=True,
        ),
        geometry="geometry",
        crs=CRS_EA,
    )

    bound_u = unary_union(boundary_ea.geometry)
    uncovered_before = bound_u.difference(angela_u)
    uncovered_after = bound_u.difference(unary_union(extended.geometry))

    summary = pd.DataFrame(
        [
            {"item": "method", "value": "mollweide_ESRI54009_100m"},
            {
                "item": "docs",
                "value": "ideamapsdataecosystem.org/docs/our-data/the-grid",
            },
            {"item": "angela_original_cells_n", "value": len(clipped)},
            {"item": "extension_cells_n", "value": len(new_out)},
            {"item": "extended_grid_cells_n", "value": len(extended)},
            {"item": "boundary_area_km2", "value": round(bound_u.area / 1e6, 3)},
            {
                "item": "uncovered_before_pct",
                "value": round(100 * uncovered_before.area / bound_u.area, 2),
            },
            {
                "item": "uncovered_after_pct",
                "value": round(
                    0.0
                    if uncovered_after.is_empty
                    else 100 * uncovered_after.area / bound_u.area,
                    2,
                ),
            },
            {"item": "new_cell_id_start", "value": max_id + 1},
        ]
    )

    print(f"Writing {OUT_GRID.name}...")
    extended.to_file(OUT_GRID, driver="GPKG")
    print(f"Writing {OUT_NEW.name}...")
    new_out.to_file(OUT_NEW, driver="GPKG")
    print(f"Writing {OUT_SUMMARY.name}...")
    summary.to_csv(OUT_SUMMARY, index=False)
    print(summary.to_string(index=False))
    print(f"\nOutputs in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

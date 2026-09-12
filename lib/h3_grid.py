"""Shared H3 grid helpers for coverage analysis scripts."""

from __future__ import annotations

import geopandas as gpd
import h3
from shapely.geometry import Polygon

WGS84 = "EPSG:4326"
PROJECTED_CRS = "EPSG:32737"
MIN_CITY_AREA_M2 = 1.0


def boundary_to_h3_cells(boundary_wgs84: gpd.GeoDataFrame, res: int) -> set[str]:
    geometry = boundary_wgs84.union_all()
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)

    cells: set[str] = set()
    for poly in polygons:
        coords = [(lat, lon) for lon, lat in poly.exterior.coords]
        cells.update(h3.polygon_to_cells(h3.LatLngPoly(coords), res))
    return cells


def h3_cell_to_polygon_wgs84(h3_index: str) -> Polygon:
    coords = [(lon, lat) for lat, lon in h3.cell_to_boundary(h3_index)]
    return Polygon(coords)


def build_h3_grid(boundary: gpd.GeoDataFrame, res: int) -> gpd.GeoDataFrame:
    cells = boundary_to_h3_cells(boundary.to_crs(WGS84), res)
    grid_wgs84 = gpd.GeoDataFrame(
        {"h3_index": list(cells)},
        geometry=[h3_cell_to_polygon_wgs84(cell) for cell in cells],
        crs=WGS84,
    )
    grid = grid_wgs84.to_crs(PROJECTED_CRS)
    grid["cell_area_m2"] = grid.geometry.area
    grid["h3_res"] = res
    return grid


def clip_grid_to_city(grid: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    city_cells = gpd.overlay(
        grid[["h3_index", "h3_res", "cell_area_m2", "geometry"]],
        boundary[["geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    city_cells["city_area_m2"] = city_cells.geometry.area
    city_cells = city_cells[city_cells["city_area_m2"] >= MIN_CITY_AREA_M2].copy()
    city_cells["in_city"] = 1
    return city_cells

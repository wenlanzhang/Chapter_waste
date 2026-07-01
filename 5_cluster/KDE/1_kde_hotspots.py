"""
KDE robustness check — neighbourhood-scale hotspot footprints (gsvi vs gsvi_selfcollected).

Supplementary to HDBSCAN: same Step 1 waste points, fixed 400 m bandwidth (Scott
over-smooths city-wide data), shared density threshold, union hotspot polygons.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
from rasterio.transform import from_origin
from scipy.stats import gaussian_kde  # noqa: F401 — Scott reference only
from shapely.geometry import shape
from shapely.ops import unary_union

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "5_cluster" / "KDE"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GSVI_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg"
GSVI_SELF_COLLECTED_GPKG = INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg"
BOUNDARY_GPKG = INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg"

GRID_CELL_M = 150
# Fixed isotropic bandwidth (m) — Scott on city-wide points (~1.7 km) over-smooths; use neighbourhood scale.
KDE_BANDWIDTH_M = 400
KDE_HOTSPOT_PERCENTILE = 2  # top N% of gsvi density values → shared absolute threshold

ARMS = {
    "gsvi": {
        "column": "Google SVI",
        "gpkg": GSVI_GPKG,
        "hotspot_gpkg": OUTPUT_DIR / "Nairobi_kde_hotspot_polygons_gsvi_32737.gpkg",
    },
    "gsvi_selfcollected": {
        "column": "GSVI + self-collected",
        "gpkg": GSVI_SELF_COLLECTED_GPKG,
        "hotspot_gpkg": OUTPUT_DIR
        / "Nairobi_kde_hotspot_polygons_gsvi_selfcollected_32737.gpkg",
    },
}

PARAMS_PATH = OUTPUT_DIR / "Nairobi_kde_params.csv"
TABLE_PATH = TABLE_DIR / "Nairobi_kde_robustness_comparison.csv"


def load_points(path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.crs is None or gdf.crs.to_epsg() != 32737:
        gdf = gdf.to_crs(epsg=32737)
    return gdf


def point_coords(gdf: gpd.GeoDataFrame) -> np.ndarray:
    return np.column_stack([gdf.geometry.x.values, gdf.geometry.y.values])


def make_grid(boundary: gpd.GeoDataFrame, cell_m: float) -> tuple[np.ndarray, np.ndarray, dict]:
    minx, miny, maxx, maxy = boundary.total_bounds
    xs = np.arange(minx, maxx + cell_m, cell_m)
    ys = np.arange(miny, maxy + cell_m, cell_m)
    grid_x, grid_y = np.meshgrid(xs, ys)
    meta = {
        "minx": float(minx),
        "maxy": float(maxy),
        "cell_m": cell_m,
        "n_cols": len(xs),
        "n_rows": len(ys),
    }
    return grid_x, grid_y, meta


def boundary_mask(
    boundary: gpd.GeoDataFrame, grid_x: np.ndarray, grid_y: np.ndarray
) -> np.ndarray:
    boundary_geom = unary_union(boundary.geometry)
    rows, cols = grid_x.shape
    cell = float(np.abs(grid_x[0, 1] - grid_x[0, 0])) if cols > 1 else 150.0
    transform = from_origin(grid_x.min(), grid_y.max() + cell, cell, cell)
    mask = rasterio.features.geometry_mask(
        [boundary_geom],
        out_shape=(rows, cols),
        transform=transform,
        invert=True,
    )
    return mask


def fixed_bandwidth_covariance(bandwidth_m: float) -> np.ndarray:
    return np.diag([bandwidth_m**2, bandwidth_m**2])


def evaluate_kde_on_grid(
    coords: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    bandwidth_cov: np.ndarray,
    *,
    chunk_size: int = 5000,
) -> np.ndarray:
    """Gaussian KDE on a grid using a fixed bandwidth matrix (gsvi Scott rule)."""
    n = coords.shape[0]
    inv_cov = np.linalg.inv(bandwidth_cov)
    det = np.linalg.det(bandwidth_cov)
    coef = 1.0 / (n * (2.0 * np.pi) * np.sqrt(det))

    grid_pts = np.column_stack([grid_x.ravel(), grid_y.ravel()])
    out = np.zeros(grid_pts.shape[0], dtype=float)
    for start in range(0, grid_pts.shape[0], chunk_size):
        end = start + chunk_size
        gp = grid_pts[start:end]
        diff = gp[:, None, :] - coords[None, :, :]
        mahal = np.einsum("...i,ij,...j->...", diff, inv_cov, diff)
        out[start:end] = coef * np.exp(-0.5 * mahal).sum(axis=1)
    return out.reshape(grid_x.shape)


def density_threshold(density: np.ndarray, mask: np.ndarray, top_percent: float) -> float:
    values = density[mask]
    if values.size == 0:
        return float("inf")
    return float(np.percentile(values, 100.0 - top_percent))


def raster_to_hotspot_polygons(
    density: np.ndarray,
    threshold: float,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    boundary: gpd.GeoDataFrame,
    mask: np.ndarray,
) -> gpd.GeoDataFrame:
    hotspot = (density >= threshold) & mask
    if not hotspot.any():
        return gpd.GeoDataFrame(
            columns=["area_m2", "area_km2", "geometry"],
            geometry="geometry",
            crs=boundary.crs,
        )

    cell = float(np.abs(grid_x[0, 1] - grid_x[0, 0])) if grid_x.shape[1] > 1 else GRID_CELL_M
    transform = from_origin(grid_x.min(), grid_y.max() + cell, cell, cell)
    shapes = rasterio.features.shapes(
        hotspot.astype(np.uint8),
        mask=hotspot,
        transform=transform,
    )

    polys = []
    for geom, value in shapes:
        if int(value) != 1:
            continue
        polys.append(shape(geom))

    if not polys:
        return gpd.GeoDataFrame(
            columns=["area_m2", "area_km2", "geometry"],
            geometry="geometry",
            crs=boundary.crs,
        )

    dissolved = unary_union(polys)
    boundary_geom = unary_union(boundary.geometry)
    clipped = dissolved.intersection(boundary_geom)
    if clipped.is_empty:
        return gpd.GeoDataFrame(
            columns=["area_m2", "area_km2", "geometry"],
            geometry="geometry",
            crs=boundary.crs,
        )

    gdf = gpd.GeoDataFrame(geometry=[clipped], crs=boundary.crs)
    gdf["area_m2"] = gdf.geometry.area
    gdf["area_km2"] = gdf["area_m2"] / 1e6
    return gdf


def union_geom(gdf: gpd.GeoDataFrame):
    if gdf.empty:
        return None
    return unary_union(gdf.geometry)


def area_km2(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    return float(geom.area) / 1e6


def format_count(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}"


def format_change(gsvi_val: float, sc_val: float, *, area: bool = False) -> str:
    delta = sc_val - gsvi_val
    if area:
        return f"{delta:+.3f}"
    return f"{int(round(delta)):+,}"


def format_change_percent(gsvi_val: float, sc_val: float) -> str:
    if gsvi_val == 0:
        return "—"
    pct = 100.0 * (sc_val - gsvi_val) / gsvi_val
    return f"{pct:+.1f}%"


def build_comparison_table(
    area_gsvi: float,
    area_sc: float,
    overlap_km2: float,
    jaccard: float,
    pct_retained: float,
    pct_added: float,
) -> pd.DataFrame:
    rows = [
        (
            "Hotspot area (km²)",
            area_gsvi,
            area_sc,
            True,
        ),
        (
            "Hotspot area change (km²)",
            area_gsvi,
            area_sc,
            True,
        ),
        (
            "Spatial overlap (km²)",
            overlap_km2,
            overlap_km2,
            True,
        ),
        (
            "Overlap ratio (Jaccard)",
            jaccard,
            jaccard,
            False,
        ),
        (
            "% original area retained",
            pct_retained,
            pct_retained,
            False,
        ),
        (
            "% added area",
            pct_added,
            pct_added,
            False,
        ),
    ]

    records = []
    for metric, gsvi_val, sc_val, is_area in rows:
        if metric == "Hotspot area change (km²)":
            change = format_change(gsvi_val, sc_val, area=True)
            change_pct = format_change_percent(gsvi_val, sc_val)
        elif metric in {
            "Spatial overlap (km²)",
            "Overlap ratio (Jaccard)",
            "% original area retained",
            "% added area",
        }:
            change = "—"
            change_pct = "—"
        else:
            change = format_change(gsvi_val, sc_val, area=is_area)
            change_pct = format_change_percent(gsvi_val, sc_val)

        records.append(
            {
                "Metric": metric,
                ARMS["gsvi"]["column"]: format_count(gsvi_val),
                ARMS["gsvi_selfcollected"]["column"]: format_count(sc_val),
                "Change": change,
                "Change percent": change_pct,
            }
        )
    return pd.DataFrame(records)


def write_params_csv(
    path: Path,
    *,
    n_gsvi: int,
    n_sc: int,
    bandwidth_m: float,
    scott_factor_gsvi: float,
    scott_h_x_m: float,
    scott_h_y_m: float,
    threshold: float,
    grid_meta: dict,
) -> None:
    rows = [
        ("n_points_gsvi", n_gsvi, "count"),
        ("n_points_gsvi_selfcollected", n_sc, "count"),
        ("kde_bandwidth_m", bandwidth_m, "m"),
        ("scott_factor_gsvi_reference", scott_factor_gsvi, "dimensionless"),
        ("scott_h_x_m_reference", scott_h_x_m, "m"),
        ("scott_h_y_m_reference", scott_h_y_m, "m"),
        ("grid_cell_m", grid_meta["cell_m"], "m"),
        ("grid_n_cols", grid_meta["n_cols"], "count"),
        ("grid_n_rows", grid_meta["n_rows"], "count"),
        ("kde_hotspot_percentile", KDE_HOTSPOT_PERCENTILE, "percent"),
        ("density_threshold", threshold, "density"),
    ]
    pd.DataFrame(rows, columns=["Parameter", "Value", "Unit"]).to_csv(path, index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    print("KDE robustness — hotspot polygons (gsvi vs gsvi_selfcollected)...")
    boundary = load_points(BOUNDARY_GPKG)
    gsvi_gdf = load_points(GSVI_GPKG)
    sc_gdf = load_points(GSVI_SELF_COLLECTED_GPKG)

    gsvi_coords = point_coords(gsvi_gdf)
    sc_coords = point_coords(sc_gdf)

    kde_ref = gaussian_kde(gsvi_coords.T)
    scott_factor = float(kde_ref.factor)
    scott_cov = kde_ref.covariance
    scott_h_x = float(np.sqrt(scott_cov[0, 0]))
    scott_h_y = float(np.sqrt(scott_cov[1, 1]))
    bandwidth_cov = fixed_bandwidth_covariance(KDE_BANDWIDTH_M)

    grid_x, grid_y, grid_meta = make_grid(boundary, GRID_CELL_M)
    in_boundary = boundary_mask(boundary, grid_x, grid_y)

    gsvi_density = evaluate_kde_on_grid(gsvi_coords, grid_x, grid_y, bandwidth_cov)
    threshold = density_threshold(gsvi_density, in_boundary, KDE_HOTSPOT_PERCENTILE)
    print(f"  KDE bandwidth: {KDE_BANDWIDTH_M} m (Scott reference h_x={scott_h_x:.0f} m)")
    print(f"  Shared density threshold (top {KDE_HOTSPOT_PERCENTILE}% gsvi): {threshold:.6e}")

    hotspot_gdfs: dict[str, gpd.GeoDataFrame] = {}
    for key, meta in ARMS.items():
        coords = gsvi_coords if key == "gsvi" else sc_coords
        density = evaluate_kde_on_grid(coords, grid_x, grid_y, bandwidth_cov)
        polys = raster_to_hotspot_polygons(
            density, threshold, grid_x, grid_y, boundary, in_boundary
        )
        polys.to_file(meta["hotspot_gpkg"], driver="GPKG")
        hotspot_gdfs[key] = polys
        area = float(polys["area_km2"].sum()) if not polys.empty else 0.0
        print(f"  {key}: hotspot area = {area:.3f} km² → {meta['hotspot_gpkg'].name}")

    gsvi_union = union_geom(hotspot_gdfs["gsvi"])
    sc_union = union_geom(hotspot_gdfs["gsvi_selfcollected"])

    area_gsvi = area_km2(gsvi_union)
    area_sc = area_km2(sc_union)

    if gsvi_union is None or sc_union is None or gsvi_union.is_empty or sc_union.is_empty:
        overlap_km2 = 0.0
        union_km2 = area_gsvi + area_sc
        jaccard = 0.0 if union_km2 == 0 else overlap_km2 / union_km2
    else:
        overlap_geom = gsvi_union.intersection(sc_union)
        overlap_km2 = area_km2(overlap_geom)
        union_geom_val = gsvi_union.union(sc_union)
        union_km2 = area_km2(union_geom_val)
        jaccard = overlap_km2 / union_km2 if union_km2 > 0 else 0.0

    pct_retained = 100.0 * overlap_km2 / area_gsvi if area_gsvi > 0 else 0.0
    pct_added = 100.0 * (area_sc - overlap_km2) / area_gsvi if area_gsvi > 0 else 0.0

    table = build_comparison_table(
        area_gsvi, area_sc, overlap_km2, jaccard, pct_retained, pct_added
    )
    table.to_csv(TABLE_PATH, index=False)

    write_params_csv(
        PARAMS_PATH,
        n_gsvi=len(gsvi_gdf),
        n_sc=len(sc_gdf),
        bandwidth_m=KDE_BANDWIDTH_M,
        scott_factor_gsvi=scott_factor,
        scott_h_x_m=scott_h_x,
        scott_h_y_m=scott_h_y,
        threshold=threshold,
        grid_meta=grid_meta,
    )

    print(f"Wrote {TABLE_PATH}")
    print(f"Wrote {PARAMS_PATH}")
    print()
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

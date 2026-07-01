"""
Clean, harmonise, export, and map Nairobi waste/SVI spatial datasets.

Reads raw inputs from PhD_UCL/Data (read-only), writes clipped/projected
GeoPackages to Chapter_waste/1prepare_chapter_data.

SVI points are deduplicated by panoid (one row per panorama, not per image).
"""

from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union

from road_utils import ROAD_FILES, clean_road_segments, node_road_segments, prepare_raw_local

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
OUTPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"

WASTE_CSV = DATA_ROOT / "Waste/img/Correct_SVI.csv"
SVI_CSV = DATA_ROOT / "Waste/img/Combined_SVI.csv"
BOUNDARY_SHP = DATA_ROOT / "Shp/NariobiShp/Shp_from_Constituency/Nairobi_shp_C.shp"
SLUM_SHP = DATA_ROOT / "Waste/Angela/slumaps_nairobi_sett/slumaps_nairobi_sett.shp"
ROAD_GPKG = DATA_ROOT / "Waste/Angela/OSM_NAI_AOI.gpkg"
GRID_GPKG = DATA_ROOT / "Waste/Angela/IDEAmaps_grid-boundary-nairobi.gpkg"
VALIDATION_CSV = (
    DATA_ROOT / "Waste/IDEAMaps/260701validation/validation-dataset.csv"
)

WGS84 = "EPSG:4326"
PROJECTED_CRS = "EPSG:32737"

EXCLUDED_IMG_DIRS = {"ZWL/", "Faith/"}
SVI_DROP_COLUMNS = [
    "year",
    "month",
    "day",
    "hour",
    "exist",
    "yolo_conf",
    "yolo_bbox",
    "yolo_num",
    "prediction",
    "Construction",
]

OUTPUT_FILES = {
    "waste_gsvi": "Nairobi_Waste_point_gsvi_32737.gpkg",
    "waste_gsvi_selfcollected": "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    "svi_gsvi": "Nairobi_SVI_point_gsvi_32737.gpkg",
    "svi_gsvi_selfcollected": "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
    "svi_image_gsvi": "Nairobi_SVI_image_gsvi_32737.gpkg",
    "svi_image_gsvi_selfcollected": "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
    "road": "Nairobi_road_line_32737.gpkg",
    "boundary": "Nairobi_boundary_polygon_32737.gpkg",
    "slum": "Nairobi_slum_polygon_32737.gpkg",
    "slum_cluster": "Nairobi_slum_cluster_polygon_32737.gpkg",
    "grid_100m": "Nairobi_grid_100m_32737.gpkg",
    "validation_point": "Nairobi_validation_point_32737.gpkg",
    "validation_grid": "Nairobi_validation_grid_32737.gpkg",
}


def csv_to_points(df: pd.DataFrame) -> gpd.GeoDataFrame:
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs=WGS84)


def filter_excluded_dirs(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["img_dir"].isin(EXCLUDED_IMG_DIRS)]


def filter_and_dedup_waste(df: pd.DataFrame) -> pd.DataFrame:
    filtered = filter_excluded_dirs(df)
    return filtered.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")


def filter_and_dedup_svi_images(df: pd.DataFrame) -> pd.DataFrame:
    """One row per SVI image file (same dedupe key as waste detections)."""
    filtered = filter_excluded_dirs(df)
    return filtered.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")


def filter_and_dedup_svi_images_all_sources(df: pd.DataFrame) -> pd.DataFrame:
    """All sources; one row per image file."""
    return df.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")


def filter_and_dedup_svi(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one row per panorama (panoid); each panoid has up to 4 viewing angles."""
    filtered = filter_excluded_dirs(df)
    filtered = filtered.dropna(subset=["panoid"])
    return filtered.drop_duplicates(subset=["panoid"], keep="first")


def classify_source(img_dir: str) -> str:
    if img_dir == "Faith/":
        return "Faith"
    if img_dir == "ZWL/":
        return "ZWL"
    return "Google"


def add_source_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["source"] = out["img_dir"].map(classify_source)
    return out


def filter_and_dedup_waste_all_sources(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")


def filter_and_dedup_svi_all_sources(df: pd.DataFrame) -> pd.DataFrame:
    """GSVI rows deduped by panoid; self-collected rows deduped by lat/lon/img_name."""
    gsvi_df = df[~df["img_dir"].isin(EXCLUDED_IMG_DIRS)].copy()
    gsvi_df = gsvi_df.dropna(subset=["panoid"])
    gsvi_df = gsvi_df.drop_duplicates(subset=["panoid"], keep="first")

    self_df = df[df["img_dir"].isin(EXCLUDED_IMG_DIRS)].copy()
    self_df = self_df.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")

    return pd.concat([gsvi_df, self_df], ignore_index=True)


def load_waste_gsvi() -> gpd.GeoDataFrame:
    df = pd.read_csv(WASTE_CSV)
    df = filter_and_dedup_waste(df)
    df = add_source_column(df)
    return csv_to_points(df)


def load_waste_gsvi_selfcollected() -> gpd.GeoDataFrame:
    df = pd.read_csv(WASTE_CSV)
    df = filter_and_dedup_waste_all_sources(df)
    df = add_source_column(df)
    return csv_to_points(df)


def load_svi_gsvi() -> tuple[gpd.GeoDataFrame, int]:
    raw = pd.read_csv(SVI_CSV, low_memory=False)
    raw_filtered = filter_excluded_dirs(raw)
    df = filter_and_dedup_svi(raw)
    df = df.drop(columns=[c for c in SVI_DROP_COLUMNS if c in df.columns])
    df = add_source_column(df)
    return csv_to_points(df), len(raw_filtered)


def load_svi_gsvi_selfcollected() -> gpd.GeoDataFrame:
    raw = pd.read_csv(SVI_CSV, low_memory=False)
    df = filter_and_dedup_svi_all_sources(raw)
    df = df.drop(columns=[c for c in SVI_DROP_COLUMNS if c in df.columns])
    df = add_source_column(df)
    return csv_to_points(df)


def load_svi_image_gsvi() -> gpd.GeoDataFrame:
    raw = pd.read_csv(SVI_CSV, low_memory=False)
    df = filter_and_dedup_svi_images(raw)
    df = df.drop(columns=[c for c in SVI_DROP_COLUMNS if c in df.columns])
    df = add_source_column(df)
    return csv_to_points(df)


def load_svi_image_gsvi_selfcollected() -> gpd.GeoDataFrame:
    raw = pd.read_csv(SVI_CSV, low_memory=False)
    df = filter_and_dedup_svi_images_all_sources(raw)
    df = df.drop(columns=[c for c in SVI_DROP_COLUMNS if c in df.columns])
    df = add_source_column(df)
    return csv_to_points(df)


def cluster_slum_polygons(slums_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Merge touching slum polygons into connected settlement clusters."""
    slums = slums_gdf.explode(index_parts=False).reset_index(drop=True)

    graph = nx.Graph()
    for idx, geom in slums.geometry.items():
        graph.add_node(idx)
        for neighbor in slums[slums.geometry.touches(geom)].index:
            graph.add_edge(idx, neighbor)

    cluster_geoms = [
        unary_union(slums.loc[list(cluster)].geometry)
        for cluster in nx.connected_components(graph)
    ]
    clusters = gpd.GeoDataFrame(geometry=cluster_geoms, crs=slums.crs)
    clusters["area_km2"] = clusters.to_crs(PROJECTED_CRS).geometry.area / 1e6
    return clusters


def load_validation_points() -> gpd.GeoDataFrame:
    """IDEAMaps crowd validation clicks (lat/lon + model vs human labels)."""
    raw = pd.read_csv(VALIDATION_CSV)
    df = raw.rename(
        columns={
            "Latitude": "lat",
            "Longitude": "lon",
            "Validation Result": "validation_result",
            "Model Result": "model_result",
        }
    )
    df["validation_result"] = df["validation_result"].astype(int)
    df["model_result"] = df["model_result"].astype(int)
    df["is_waste"] = (df["validation_result"] > 0).astype(np.uint8)
    df["model_is_waste"] = (df["model_result"] > 0).astype(np.uint8)
    return csv_to_points(df)


def assign_validation_cell_ids(
    points: gpd.GeoDataFrame, grid: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Spatial join validation points to clipped 100 m grid (cell_id)."""
    grid_idx = grid[["cell_id", "geometry"]].copy()
    joined = gpd.sjoin(
        points.to_crs(grid.crs),
        grid_idx,
        how="left",
        predicate="within",
    )
    if "index_right" in joined.columns:
        joined = joined.drop(columns="index_right")
    return joined


def aggregate_validation_by_cell(
    points: gpd.GeoDataFrame, grid: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    One row per validated grid cell.

    Multiple validators on the same cell → max severity (0/1/2) for both
    validation_result and model_result.
    """
    validated = points.dropna(subset=["cell_id"]).copy()
    validated["cell_id"] = validated["cell_id"].astype(int)

    agg = (
        validated.groupby("cell_id")
        .agg(
            n_validations=("validation_result", "size"),
            n_validators=("user_id", "nunique"),
            validation_result=("validation_result", "max"),
            model_result=("model_result", "max"),
        )
        .reset_index()
    )
    agg["is_waste"] = (agg["validation_result"] > 0).astype(np.uint8)
    agg["model_is_waste"] = (agg["model_result"] > 0).astype(np.uint8)

    out = grid[["cell_id", "geometry"]].merge(agg, on="cell_id", how="inner")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=grid.crs)


def prepare_grid_100m(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clip Angela 100 m grid to Nairobi constituency (centroid within boundary)."""
    grid = gpd.read_file(GRID_GPKG)
    n_raw = len(grid)
    boundary_union = unary_union(boundary.geometry)
    grid = grid.to_crs(boundary.crs)
    grid = grid[grid.intersects(boundary_union)].copy()
    centroids = grid.geometry.centroid
    grid = grid[centroids.within(boundary_union)].copy()
    grid = grid.reset_index(drop=True)
    grid["cell_id"] = grid.index.astype(int)
    out = grid.to_crs(PROJECTED_CRS)
    print(f"  Grid cells (clipped): {len(out):,}  (raw {n_raw:,})")
    return out


def save_gpkg(gdf: gpd.GeoDataFrame, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    gdf.to_file(path, driver="GPKG")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading raw inputs...")
    waste_gsvi = load_waste_gsvi()
    waste_gsvi_selfcollected = load_waste_gsvi_selfcollected()
    svi_gsvi, svi_before_panoid_dedup = load_svi_gsvi()
    svi_gsvi_selfcollected = load_svi_gsvi_selfcollected()
    svi_image_gsvi = load_svi_image_gsvi()
    svi_image_gsvi_selfcollected = load_svi_image_gsvi_selfcollected()
    validation_raw = load_validation_points()
    boundary = gpd.read_file(BOUNDARY_SHP)
    slums = gpd.read_file(SLUM_SHP)
    roads = gpd.read_file(ROAD_GPKG)

    print(f"  SVI rows after dir filter: {svi_before_panoid_dedup:,}")
    print(f"  SVI unique panoids (gsvi arm): {len(svi_gsvi):,}")
    print(f"  SVI images (gsvi arm):         {len(svi_image_gsvi):,}")
    print(f"  SVI all sources (panoid):      {len(svi_gsvi_selfcollected):,}")
    print(f"  SVI all sources (images):      {len(svi_image_gsvi_selfcollected):,}")
    print(f"  Waste gsvi arm:              {len(waste_gsvi):,}")
    print(f"  Waste gsvi+selfcollected:    {len(waste_gsvi_selfcollected):,}")
    print(f"  Validation clicks (raw):     {len(validation_raw):,}")

    print("Clipping to Nairobi boundary...")
    waste_gsvi_clipped = gpd.clip(waste_gsvi, boundary)
    waste_gsvi_selfcollected_clipped = gpd.clip(waste_gsvi_selfcollected, boundary)
    svi_gsvi_clipped = gpd.clip(svi_gsvi, boundary)
    svi_gsvi_selfcollected_clipped = gpd.clip(svi_gsvi_selfcollected, boundary)
    svi_image_gsvi_clipped = gpd.clip(svi_image_gsvi, boundary)
    svi_image_gsvi_selfcollected_clipped = gpd.clip(svi_image_gsvi_selfcollected, boundary)
    validation_clipped = gpd.clip(validation_raw, boundary)
    slums_clipped = gpd.clip(slums, boundary)

    print("Preparing local road layers (raw + cleaned + noded)...")
    roads_raw = prepare_raw_local(roads, boundary)
    roads_clean = clean_road_segments(roads, boundary)
    print("Noding local roads at intersections...")
    roads_noded = node_road_segments(roads_clean)

    print("Reprojecting to EPSG:32737...")
    waste_gsvi_out = waste_gsvi_clipped.to_crs(PROJECTED_CRS)
    waste_gsvi_selfcollected_out = waste_gsvi_selfcollected_clipped.to_crs(PROJECTED_CRS)
    svi_gsvi_out = svi_gsvi_clipped.to_crs(PROJECTED_CRS)
    svi_gsvi_selfcollected_out = svi_gsvi_selfcollected_clipped.to_crs(PROJECTED_CRS)
    svi_image_gsvi_out = svi_image_gsvi_clipped.to_crs(PROJECTED_CRS)
    svi_image_gsvi_selfcollected_out = svi_image_gsvi_selfcollected_clipped.to_crs(PROJECTED_CRS)
    boundary_out = boundary.to_crs(PROJECTED_CRS)
    slums_out = slums_clipped.to_crs(PROJECTED_CRS)
    slum_clusters_out = cluster_slum_polygons(slums_clipped).to_crs(PROJECTED_CRS)

    print("Preparing clipped 100 m grid...")
    grid_100m_out = prepare_grid_100m(boundary)

    print("Assigning validation clicks to 100 m grid (max severity per cell)...")
    validation_with_cells = assign_validation_cell_ids(validation_clipped, grid_100m_out)
    validation_point_out = validation_with_cells.to_crs(PROJECTED_CRS)
    validation_grid_out = aggregate_validation_by_cell(
        validation_with_cells, grid_100m_out
    )
    n_validation_points = len(validation_point_out)
    n_validation_cells = len(validation_grid_out)
    n_multi = int((validation_grid_out["n_validations"] > 1).sum())
    print(
        f"  Validation points in grid: {validation_point_out['cell_id'].notna().sum():,} / "
        f"{n_validation_points:,}"
    )
    print(
        f"  Validated grid cells: {n_validation_cells:,}  "
        f"({n_multi:,} with 2+ clicks, max-severity rule)"
    )

    datasets = {
        "waste_gsvi": waste_gsvi_out,
        "waste_gsvi_selfcollected": waste_gsvi_selfcollected_out,
        "svi_gsvi": svi_gsvi_out,
        "svi_gsvi_selfcollected": svi_gsvi_selfcollected_out,
        "svi_image_gsvi": svi_image_gsvi_out,
        "svi_image_gsvi_selfcollected": svi_image_gsvi_selfcollected_out,
        "boundary": boundary_out,
        "slum": slums_out,
        "slum_cluster": slum_clusters_out,
        "grid_100m": grid_100m_out,
        "validation_point": validation_point_out,
        "validation_grid": validation_grid_out,
    }

    print(f"Writing outputs to {OUTPUT_DIR}...")
    for key, gdf in datasets.items():
        path = save_gpkg(gdf, OUTPUT_FILES[key])
        print(f"  {path.name}: {len(gdf):,} features")

    roads_raw.to_file(OUTPUT_DIR / ROAD_FILES["local_raw"], driver="GPKG")
    roads_clean.to_file(OUTPUT_DIR / ROAD_FILES["local_cleaned"], driver="GPKG")
    roads_noded.to_file(OUTPUT_DIR / ROAD_FILES["local_noded"], driver="GPKG")
    roads_noded.to_file(OUTPUT_DIR / ROAD_FILES["local_cleaned_legacy"], driver="GPKG")
    print(f"  {ROAD_FILES['local_raw']}: {len(roads_raw):,} features")
    print(f"  {ROAD_FILES['local_cleaned']}: {len(roads_clean):,} features")
    print(f"  {ROAD_FILES['local_noded']}: {len(roads_noded):,} features")
    print(f"  {ROAD_FILES['local_cleaned_legacy']}: {len(roads_noded):,} features (legacy alias, noded)")

    print("\nFigures: Rscript 1prepare_chapter_data/plot_maps.R")
    print("         Rscript 1prepare_chapter_data/plot_road_figures.R")
    print("         Rscript 1prepare_chapter_data/plot_road_type_composition.R")

    boundary_km2 = boundary_out.geometry.area.sum() / 1e6
    slum_km2 = slums_out.geometry.area.sum() / 1e6
    slum_pct = (slum_km2 / boundary_km2) * 100

    print("\nSummary")
    print(f"  Boundary area: {boundary_km2:.2f} km²")
    print(f"  Slum area:     {slum_km2:.2f} km² ({slum_pct:.1f}% of boundary)")
    print(
        f"  Waste gsvi:              {len(waste_gsvi_out):,}  "
        f"(raw {len(waste_gsvi):,})"
    )
    print(
        f"  Waste gsvi+selfcollected: {len(waste_gsvi_selfcollected_out):,}  "
        f"(raw {len(waste_gsvi_selfcollected):,})"
    )
    print(
        f"  SVI gsvi (panoid):       {len(svi_gsvi_out):,}  "
        f"(images {len(svi_image_gsvi_out):,}, raw rows {svi_before_panoid_dedup:,})"
    )
    print(
        f"  SVI gsvi+selfcollected:  {len(svi_gsvi_selfcollected_out):,} panoids  "
        f"({len(svi_image_gsvi_selfcollected_out):,} images)"
    )
    print(
        f"  Road segments: {len(roads_noded):,} noded "
        f"({len(roads_clean):,} cleaned, {len(roads_raw):,} raw, "
        f"{roads_noded['length_m'].sum() / 1000:,.1f} km)"
    )
    print(f"  Slum polygons: {len(slums_out):,}  (raw {len(slums):,})")
    print(f"  Slum clusters: {len(slum_clusters_out):,}")
    print(f"  Grid 100 m cells: {len(grid_100m_out):,}")
    print(
        f"  Validation: {n_validation_points:,} points → "
        f"{n_validation_cells:,} grid cells (max severity)"
    )


if __name__ == "__main__":
    main()

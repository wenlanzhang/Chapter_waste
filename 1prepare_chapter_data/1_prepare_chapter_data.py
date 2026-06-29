"""
Clean, harmonise, export, and map Nairobi waste/SVI spatial datasets.

Reads raw inputs from PhD_UCL/Data (read-only), writes clipped/projected
GeoPackages to Chapter_waste/1prepare_chapter_data.

SVI points are deduplicated by panoid (one row per panorama, not per image).
"""

from pathlib import Path

import geopandas as gpd
import networkx as nx
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
    "waste": "Nairobi_Waste_point_32737.gpkg",
    "svi": "Nairobi_SVI_point_32737.gpkg",
    "road": "Nairobi_road_line_32737.gpkg",
    "boundary": "Nairobi_boundary_polygon_32737.gpkg",
    "slum": "Nairobi_slum_polygon_32737.gpkg",
    "slum_cluster": "Nairobi_slum_cluster_polygon_32737.gpkg",
}


def csv_to_points(df: pd.DataFrame) -> gpd.GeoDataFrame:
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    return gpd.GeoDataFrame(df, geometry=geometry, crs=WGS84)


def filter_excluded_dirs(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["img_dir"].isin(EXCLUDED_IMG_DIRS)]


def filter_and_dedup_waste(df: pd.DataFrame) -> pd.DataFrame:
    filtered = filter_excluded_dirs(df)
    return filtered.drop_duplicates(subset=["lat", "lon", "img_name"], keep="first")


def filter_and_dedup_svi(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one row per panorama (panoid); each panoid has up to 4 viewing angles."""
    filtered = filter_excluded_dirs(df)
    filtered = filtered.dropna(subset=["panoid"])
    return filtered.drop_duplicates(subset=["panoid"], keep="first")


def load_waste_points() -> gpd.GeoDataFrame:
    df = pd.read_csv(WASTE_CSV)
    df = filter_and_dedup_waste(df)
    return csv_to_points(df)


def load_svi_points() -> tuple[gpd.GeoDataFrame, int]:
    raw = pd.read_csv(SVI_CSV, low_memory=False)
    raw_filtered = filter_excluded_dirs(raw)
    df = filter_and_dedup_svi(raw)
    df = df.drop(columns=[c for c in SVI_DROP_COLUMNS if c in df.columns])
    return csv_to_points(df), len(raw_filtered)


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


def save_gpkg(gdf: gpd.GeoDataFrame, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    gdf.to_file(path, driver="GPKG")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading raw inputs...")
    waste = load_waste_points()
    svi, svi_before_panoid_dedup = load_svi_points()
    boundary = gpd.read_file(BOUNDARY_SHP)
    slums = gpd.read_file(SLUM_SHP)
    roads = gpd.read_file(ROAD_GPKG)

    print(f"  SVI rows after dir filter: {svi_before_panoid_dedup:,}")
    print(f"  SVI unique panoids:        {len(svi):,}")

    print("Clipping to Nairobi boundary...")
    waste_clipped = gpd.clip(waste, boundary)
    svi_clipped = gpd.clip(svi, boundary)
    slums_clipped = gpd.clip(slums, boundary)

    print("Preparing local road layers (raw + cleaned + noded)...")
    roads_raw = prepare_raw_local(roads, boundary)
    roads_clean = clean_road_segments(roads, boundary)
    print("Noding local roads at intersections...")
    roads_noded = node_road_segments(roads_clean)

    print("Reprojecting to EPSG:32737...")
    waste_out = waste_clipped.to_crs(PROJECTED_CRS)
    svi_out = svi_clipped.to_crs(PROJECTED_CRS)
    boundary_out = boundary.to_crs(PROJECTED_CRS)
    slums_out = slums_clipped.to_crs(PROJECTED_CRS)
    slum_clusters_out = cluster_slum_polygons(slums_clipped).to_crs(PROJECTED_CRS)

    datasets = {
        "waste": waste_out,
        "svi": svi_out,
        "boundary": boundary_out,
        "slum": slums_out,
        "slum_cluster": slum_clusters_out,
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
    print(f"  Waste points:  {len(waste_out):,}  (raw {len(waste):,})")
    print(f"  SVI panoids:   {len(svi_out):,}  (raw images {svi_before_panoid_dedup:,}, unique panoids {len(svi):,})")
    print(
        f"  Road segments: {len(roads_noded):,} noded "
        f"({len(roads_clean):,} cleaned, {len(roads_raw):,} raw, "
        f"{roads_noded['length_m'].sum() / 1000:,.1f} km)"
    )
    print(f"  Slum polygons: {len(slums_out):,}  (raw {len(slums):,})")
    print(f"  Slum clusters: {len(slum_clusters_out):,}")


if __name__ == "__main__":
    main()

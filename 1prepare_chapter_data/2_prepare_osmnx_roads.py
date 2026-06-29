"""
Download, clean, and export Nairobi roads with OSMnx.

Produces numbered road layers:
  02 osmnx raw   — download, project, truncate (no simplify)
  04 osmnx cleaned — simplify + standard cleaning
  05 comparison  — overlap / local_only / osmnx_only on cleaned layers
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import osmnx as ox

from road_utils import (
    ROAD_FILES,
    WGS84,
    analyze_svi_on_road_network,
    build_cleaned_comparison,
    clean_road_segments,
    compare_road_networks,
    compare_svi_on_road_networks,
    prepare_raw_osmnx_edges,
)

DATA_ROOT = Path("/Users/wenlanzhang/Downloads/PhD_UCL/Data")
INPUT_DIR = DATA_ROOT / "Chapter_waste" / "1prepare_chapter_data"
OUTPUT_DIR = INPUT_DIR

BOUNDARY_GPKG = INPUT_DIR / "Nairobi_boundary_polygon_32737.gpkg"
SVI_GPKG = INPUT_DIR / "Nairobi_SVI_point_32737.gpkg"
LOCAL_CLEANED_GPKG = INPUT_DIR / ROAD_FILES["local_cleaned"]


def download_osmnx_graph(boundary: gpd.GeoDataFrame):
    boundary_wgs84 = boundary.to_crs(WGS84)
    polygon_wgs84 = boundary_wgs84.union_all()
    polygon_projected = boundary.union_all()

    print("Downloading OSM network with OSMnx (network_type='all', simplify=False)...")
    graph = ox.graph_from_polygon(polygon_wgs84, network_type="all", simplify=False)

    print("Projecting and truncating to Nairobi boundary...")
    graph = ox.project_graph(graph, to_crs=boundary.crs)
    graph = ox.truncate.truncate_graph_polygon(graph, polygon=polygon_projected)
    return graph


def write_comparison_tables(local: gpd.GeoDataFrame, osmnx: gpd.GeoDataFrame) -> None:
    summary, type_comparison, composition_long = compare_road_networks(local, osmnx)

    summary.to_csv(OUTPUT_DIR / "Nairobi_road_comparison_summary.csv", index=False)
    type_comparison.to_csv(OUTPUT_DIR / "Nairobi_road_type_comparison.csv", index=False)
    composition_long.to_csv(
        OUTPUT_DIR / "Nairobi_road_type_composition_comparison.csv", index=False
    )

    print("\nComparison summary")
    for _, row in summary.iterrows():
        print(
            f"  {row['metric']}: local={row['local']:,.2f} | "
            f"osmnx={row['osmnx']:,.2f} | diff={row['diff_osmnx_minus_local']:,.2f} "
            f"({row['pct_diff']:.1f}%)"
        )


def write_svi_road_snap_analysis(
    svi: gpd.GeoDataFrame,
    local: gpd.GeoDataFrame,
    osmnx: gpd.GeoDataFrame,
) -> None:
    print("\nSVI panoid snap to road networks (nearest segment distance)...")
    local_snapped, osmnx_snapped, comparison = compare_svi_on_road_networks(svi, local, osmnx)

    comparison.to_csv(OUTPUT_DIR / "Nairobi_svi_road_snap_summary.csv", index=False)
    local_snapped.to_csv(OUTPUT_DIR / "Nairobi_svi_road_snap_local_cleaned.csv", index=False)
    osmnx_snapped.to_csv(OUTPUT_DIR / "Nairobi_svi_road_snap_osmnx_cleaned.csv", index=False)

    max_threshold = 50
    for source, snapped in (("local_cleaned", local_snapped), ("osmnx_cleaned", osmnx_snapped)):
        off = snapped[snapped["dist_to_road_m"] > max_threshold].copy()
        if len(off):
            off.to_csv(OUTPUT_DIR / f"Nairobi_svi_off_network_{source}_gt{max_threshold}m.csv", index=False)

    print("\nSVI on road network summary")
    for _, row in comparison.iterrows():
        print(f"  [{row['road_source']}]")
        print(f"    SVI panoids:           {int(row['svi_panoid_count']):,}")
        print(f"    Median dist to road:   {row['median_dist_to_road_m']:.1f} m")
        print(f"    Max dist to road:      {row['max_dist_to_road_m']:.1f} m")
        for label in ("within_10m", "within_25m", "within_50m"):
            print(
                f"    Panoids {label.replace('_', ' ')}: "
                f"{int(row[f'panoids_{label}']):,} ({row[f'pct_{label}']:.1f}%)"
            )
        print(
            f"    Off network (>50 m):   {int(row['panoids_off_network']):,} "
            f"({row['pct_off_network']:.1f}%)"
        )
        all_on = "YES" if row["all_on_network"] else "NO"
        print(f"    All SVI on network:    {all_on} (within 50 m threshold)")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    boundary = gpd.read_file(BOUNDARY_GPKG)
    graph = download_osmnx_graph(boundary)

    print("Extracting raw OSMnx edges (no simplify)...")
    edges_raw = ox.graph_to_gdfs(graph, nodes=False, edges=True, fill_edge_geometry=True)
    osmnx_raw = prepare_raw_osmnx_edges(edges_raw.reset_index(drop=True), boundary)

    print("Simplifying graph and cleaning...")
    graph = ox.simplify_graph(graph)
    edges_clean = ox.graph_to_gdfs(graph, nodes=False, edges=True, fill_edge_geometry=True)
    osmnx_clean = clean_road_segments(edges_clean.reset_index(drop=True), boundary)

    print(f"Writing {ROAD_FILES['osmnx_raw']}...")
    osmnx_raw.to_file(OUTPUT_DIR / ROAD_FILES["osmnx_raw"], driver="GPKG")

    print(f"Writing {ROAD_FILES['osmnx_cleaned']}...")
    osmnx_clean.to_file(OUTPUT_DIR / ROAD_FILES["osmnx_cleaned"], driver="GPKG")
    osmnx_clean.to_file(OUTPUT_DIR / ROAD_FILES["osmnx_cleaned_legacy"], driver="GPKG")

    print("\nOSMnx summary")
    print(f"  Raw segments:     {len(osmnx_raw):,}  ({osmnx_raw['length_m'].sum() / 1000:,.1f} km)")
    print(f"  Cleaned segments: {len(osmnx_clean):,}  ({osmnx_clean['length_m'].sum() / 1000:,.1f} km)")

    local_path = LOCAL_CLEANED_GPKG
    if not local_path.exists():
        local_path = INPUT_DIR / ROAD_FILES["local_cleaned_legacy"]

    if local_path.exists():
        print(f"\nComparing cleaned layers ({local_path.name} vs {ROAD_FILES['osmnx_cleaned']})...")
        local_clean = gpd.read_file(local_path)
        write_comparison_tables(local_clean, osmnx_clean)

        print("Building spatial overlap comparison...")
        comparison_gdf, coverage_summary = build_cleaned_comparison(local_clean, osmnx_clean)
        comparison_gdf.to_file(OUTPUT_DIR / ROAD_FILES["comparison"], driver="GPKG")
        coverage_summary.to_csv(
            OUTPUT_DIR / "Nairobi_road_05_cleaned_comparison_summary.csv", index=False
        )

        print(f"\nWrote {ROAD_FILES['comparison']}")
        print("Coverage summary (cleaned layers)")
        for _, row in coverage_summary.iterrows():
            print(
                f"  {row['class']}: {int(row['segment_count']):,} segments | "
                f"{row['length_km']:,.1f} km"
            )
    else:
        print(f"\nLocal cleaned road file not found. Run 1_prepare_chapter_data.py first.")

    if SVI_GPKG.exists() and local_path.exists():
        svi = gpd.read_file(SVI_GPKG)
        local_for_svi = gpd.read_file(local_path)
        write_svi_road_snap_analysis(svi, local_for_svi, osmnx_clean)
    elif not SVI_GPKG.exists():
        print(f"\nSVI file not found ({SVI_GPKG.name}). Run 1_prepare_chapter_data.py first.")

    print("\nFigures:")
    print("  Rscript 1prepare_chapter_data/plot_road_figures.R")
    print("  Rscript 1prepare_chapter_data/plot_road_type_composition_osmnx.R")
    print("  Rscript 1prepare_chapter_data/plot_road_network_comparison.R")


if __name__ == "__main__":
    main()

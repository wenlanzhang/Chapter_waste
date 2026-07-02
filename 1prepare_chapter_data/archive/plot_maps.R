#!/usr/bin/env Rscript
# Plot harmonised Nairobi layers produced by 1_prepare_chapter_data.py

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(scales)
})

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "1prepare_chapter_data")
CRS_EA <- 32737

read_layer <- function(filename) {
  st_read(file.path(DATA_DIR, filename), quiet = TRUE) |> st_transform(CRS_EA)
}

plot_and_save <- function(p, filename) {
  save_map(p, file.path(FIG_DIR, filename))
}

boundary <- read_layer("Nairobi_boundary_polygon_32737.gpkg")
waste <- read_layer("Nairobi_Waste_point_gsvi_32737.gpkg")
svi <- read_layer("Nairobi_SVI_point_gsvi_32737.gpkg")
slums <- read_layer("Nairobi_slum_polygon_32737.gpkg")
slum_clusters <- read_layer("Nairobi_slum_cluster_polygon_32737.gpkg")

message("Writing figures to ", FIG_DIR)

plot_and_save(
  make_base_map(
    boundary,
    title = "Nairobi waste (fly-tipping) points",
    subtitle = paste0(comma(nrow(waste)), " points | EPSG:", CRS_EA),
    caption = "Source: harmonised Correct_SVI.csv"
  ) +
    geom_sf(data = waste, color = "#cb181d", size = 0.45, alpha = 0.75),
  "Nairobi_Waste_point_gsvi_32737.png"
)

plot_and_save(
  make_base_map(
    boundary,
    title = "Nairobi street-view imagery (SVI) sample points",
    subtitle = paste0(comma(nrow(svi)), " panoids | EPSG:", CRS_EA),
    caption = "Source: harmonised Combined_SVI.csv (unique by panoid)"
  ) +
    geom_sf(data = svi, color = "#2171b5", size = 0.03, alpha = 0.18),
  "Nairobi_SVI_point_gsvi_32737.png"
)

# Road maps: use plot_road_figures.R for the numbered 01–05 road figure set.

plot_and_save(
  ggplot(boundary) +
    geom_sf(fill = "#f5f5f5", color = "black", linewidth = 0.6) +
    coord_sf(crs = map_crs(), datum = NA, expand = FALSE) +
    labs(
      title = "Nairobi study-area boundary",
      subtitle = paste0("EPSG:", CRS_EA),
      x = "Easting (m)",
      y = "Northing (m)"
    ) +
    map_theme() +
    map_elements(),
  "Nairobi_boundary_polygon_32737.png"
)

plot_and_save(
  make_base_map(
    boundary,
    title = "Nairobi informal settlement polygons",
    subtitle = paste0(comma(nrow(slums)), " polygons | EPSG:", CRS_EA),
    caption = "Source: slumaps_nairobi_sett.shp"
  ) +
    geom_sf(data = slums, fill = "#bdbdbd", color = "#737373", linewidth = 0.08, alpha = 0.85),
  "Nairobi_slum_polygon_32737.png"
)

plot_and_save(
  make_base_map(
    boundary,
    title = "Nairobi informal settlement clusters",
    subtitle = paste0(comma(nrow(slum_clusters)), " clusters | EPSG:", CRS_EA),
    caption = "Connected slum polygons merged by adjacency"
  ) +
    geom_sf(data = slum_clusters, aes(fill = area_km2), color = "#4d4d4d", linewidth = 0.12) +
    scale_fill_viridis_c(option = "C", name = "Area (km²)", labels = label_number(accuracy = 0.01)),
  "Nairobi_slum_cluster_polygon_32737.png"
)

message("Done.")

#!/usr/bin/env Rscript
# Waste detections by source — GSVI (Google) vs self-collected (Faith + ZWL), no clustering

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_cluster_mitigation")

WGS84 <- 4326

ALL_SVI_COLOUR <- "#D4CCC2"
GSVI_COLOUR <- "#C9A27F"
SELF_COLLECTED_COLOUR <- "#6B4226"
SLUM_FILL <- "#496142"
SLUM_EDGE <- "#112721"
SLUM_ALPHA <- 0.22

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

load_waste_by_source <- function() {
  gsvi <- read_wgs84(file.path(INPUT_DIR, "Nairobi_Waste_point_gsvi_32737.gpkg"))
  all_waste <- read_wgs84(
    file.path(INPUT_DIR, "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg")
  )
  self_collected <- all_waste |> filter(source %in% c("ZWL", "Faith"))
  list(gsvi = gsvi, self_collected = self_collected)
}

build_waste_sources_map <- function(
  all_svi,
  gsvi_waste,
  self_waste,
  boundary,
  slums_union,
  base_size = 11
) {
  legend_info <- make_source_legend(
    n_all_svi = nrow(all_svi),
    n_gsvi = nrow(gsvi_waste),
    n_self = nrow(self_waste)
  )
  legend_labels <- legend_info$labels
  legend_df <- make_source_legend_df(legend_labels)
  legend_colours <- make_source_legend_colours(
    legend_labels,
    ALL_SVI_COLOUR,
    GSVI_COLOUR,
    SELF_COLLECTED_COLOUR,
    SLUM_FILL
  )

  p <- ggplot() +
    geom_sf(
      data = all_svi,
      colour = ALL_SVI_COLOUR,
      size = 0.08,
      alpha = 0.32,
      linewidth = 0
    ) +
    geom_sf(
      data = gsvi_waste,
      colour = GSVI_COLOUR,
      size = 0.95,
      alpha = 0.82,
      linewidth = 0
    ) +
    geom_sf(
      data = self_waste,
      colour = SELF_COLLECTED_COLOUR,
      size = 0.95,
      alpha = 0.88,
      linewidth = 0
    ) +
    geom_sf(
      data = slums_union,
      fill = alpha(SLUM_FILL, SLUM_ALPHA),
      colour = SLUM_EDGE,
      linewidth = 0.35
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.1) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      inherit.aes = FALSE,
      na.rm = FALSE
    ) +
    scale_colour_manual(name = NULL, values = legend_colours, breaks = legend_labels) +
    guides(
      colour = source_legend_guide(
        legend_labels,
        ALL_SVI_COLOUR,
        GSVI_COLOUR,
        SELF_COLLECTED_COLOUR,
        SLUM_FILL,
        SLUM_EDGE,
        SLUM_ALPHA
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = "Waste Detections by Source in Nairobi",
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size)

  mitigation_map_decorations(p)
}

message("Reading layers...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
slums <- read_wgs84(file.path(INPUT_DIR, "Nairobi_slum_polygon_32737.gpkg"))
slums_union <- slums |>
  st_union() |>
  st_as_sf() |>
  st_make_valid()

message("Loading SVI and waste layers from Step 1 gpkgs...")
all_svi <- read_wgs84(
  file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg")
)
waste_layers <- load_waste_by_source()

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

p <- build_waste_sources_map(
  all_svi = all_svi,
  gsvi_waste = waste_layers$gsvi,
  self_waste = waste_layers$self_collected,
  boundary = boundary,
  slums_union = slums_union
)
out_path <- file.path(FIG_DIR, "Waste_sources_gsvi_selfcollected.png")
save_mitigation_map(p, out_path, boundary)
message("Wrote ", out_path)
message("Done.")

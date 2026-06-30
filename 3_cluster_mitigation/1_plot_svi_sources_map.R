#!/usr/bin/env Rscript
# All SVI panoids — GSVI base with self-collected (Faith + ZWL) highlighted

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
SVI_GPKG <- file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg")

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

load_svi_by_source <- function() {
  all_svi <- read_wgs84(SVI_GPKG)
  gsvi_svi <- all_svi |> filter(source == "Google")
  self_svi <- all_svi |> filter(source %in% c("Faith", "ZWL"))
  list(gsvi = gsvi_svi, self_collected = self_svi, all = all_svi)
}

build_svi_sources_map <- function(
  all_svi,
  gsvi_svi,
  self_svi,
  boundary,
  slums_union,
  base_size = 11
) {
  legend_info <- make_source_legend(
    n_all_svi = nrow(all_svi),
    n_gsvi = nrow(gsvi_svi),
    n_self = nrow(self_svi)
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
      data = gsvi_svi,
      colour = GSVI_COLOUR,
      size = 0.08,
      alpha = 0.38,
      linewidth = 0
    ) +
    geom_sf(
      data = self_svi,
      colour = SELF_COLLECTED_COLOUR,
      size = 0.55,
      alpha = 0.92,
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
      title = "Street View Imagery by Source in Nairobi",
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

message("Loading SVI panoids from Step 1 gpkg...")
svi_layers <- load_svi_by_source()

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

p <- build_svi_sources_map(
  all_svi = svi_layers$all,
  gsvi_svi = svi_layers$gsvi,
  self_svi = svi_layers$self_collected,
  boundary = boundary,
  slums_union = slums_union
)
out_path <- file.path(FIG_DIR, "SVI_sources_gsvi_selfcollected.png")
save_mitigation_map(p, out_path, boundary)
message("Wrote ", out_path)
message("Done.")

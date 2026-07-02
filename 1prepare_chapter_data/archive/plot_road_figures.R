#!/usr/bin/env Rscript
# Five Nairobi road figures:
#   01 local raw | 02 osmnx raw | 03 local cleaned | 04 osmnx cleaned | 05 cleaned comparison

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "1prepare_chapter_data")
CRS_EA <- 32737

ROAD_FILES <- list(
  local_raw = "Nairobi_road_01_local_raw_32737.gpkg",
  osmnx_raw = "Nairobi_road_02_osmnx_raw_32737.gpkg",
  local_cleaned = "Nairobi_road_03_local_cleaned_32737.gpkg",
  osmnx_cleaned = "Nairobi_road_04_osmnx_cleaned_32737.gpkg",
  comparison = "Nairobi_road_05_cleaned_comparison_32737.gpkg"
)

FIG_FILES <- list(
  local_raw = "Nairobi_road_01_local_raw_32737.png",
  osmnx_raw = "Nairobi_road_02_osmnx_raw_32737.png",
  local_cleaned = "Nairobi_road_03_local_cleaned_32737.png",
  osmnx_cleaned = "Nairobi_road_04_osmnx_cleaned_32737.png",
  comparison = "Nairobi_road_05_cleaned_comparison_32737.png",
  comparison_hires = "Nairobi_road_05_cleaned_comparison_32737_hires.png"
)

read_roads <- function(filename) {
  st_read(file.path(DATA_DIR, filename), quiet = TRUE) |> st_transform(CRS_EA)
}

road_stats <- function(roads) {
  km <- sum(roads$length_m, na.rm = TRUE) / 1000
  sprintf("%s segments | %s km", comma(nrow(roads)), comma(round(km, 1)))
}

plot_single_road <- function(boundary, roads, title, caption, linewidth = 0.08) {
  make_base_map(
    boundary,
    title = title,
    subtitle = road_stats(roads),
    caption = caption
  ) +
    geom_sf(data = roads, color = "#4d4d4d", linewidth = linewidth, alpha = 0.92)
}

COMPARISON_COLORS <- c(
  overlap = "#525252",
  local_only = "#d73027",
  osmnx_only = "#4575b4"
)

COMPARISON_LABELS <- c(
  overlap = "Overlap (both)",
  local_only = "Local only",
  osmnx_only = "OSMnx only"
)

plot_comparison <- function(boundary, comparison, linewidth = 0.05) {
  comparison <- comparison |>
    mutate(
      coverage_class = factor(
        coverage_class,
        levels = c("osmnx_only", "overlap", "local_only"),
        labels = COMPARISON_LABELS[c("osmnx_only", "overlap", "local_only")]
      )
    )

  counts <- comparison |>
    st_drop_geometry() |>
    count(coverage_class, name = "n")

  overlap_n <- counts$n[match(COMPARISON_LABELS["overlap"], counts$coverage_class)]
  local_n <- counts$n[match(COMPARISON_LABELS["local_only"], counts$coverage_class)]
  osmnx_n <- counts$n[match(COMPARISON_LABELS["osmnx_only"], counts$coverage_class)]

  make_base_map(
    boundary,
    title = "Cleaned road network comparison",
    subtitle = sprintf(
      "Overlap %s | Local only %s | OSMnx only %s",
      comma(ifelse(is.na(overlap_n), 0, overlap_n)),
      comma(ifelse(is.na(local_n), 0, local_n)),
      comma(ifelse(is.na(osmnx_n), 0, osmnx_n))
    ),
    caption = "Source: local cleaned vs OSMnx cleaned (EPSG:32737)"
  ) +
    geom_sf(
      data = comparison,
      aes(color = coverage_class),
      linewidth = linewidth,
      alpha = 0.92
    ) +
    scale_color_manual(
      values = setNames(
        COMPARISON_COLORS[c("osmnx_only", "overlap", "local_only")],
        COMPARISON_LABELS[c("osmnx_only", "overlap", "local_only")]
      ),
      name = NULL
    ) +
    guides(color = guide_legend(override.aes = list(linewidth = 1.2, alpha = 1)))
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
message("Writing road figures to ", FIG_DIR)

boundary <- st_read(
  file.path(DATA_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |> st_transform(CRS_EA)

local_raw <- read_roads(ROAD_FILES$local_raw)
osmnx_raw <- read_roads(ROAD_FILES$osmnx_raw)
local_clean <- read_roads(ROAD_FILES$local_cleaned)
osmnx_clean <- read_roads(ROAD_FILES$osmnx_cleaned)
comparison <- read_roads(ROAD_FILES$comparison)

save_map(
  plot_single_road(
    boundary, local_raw,
    title = "01 — Local OSM road (raw)",
    caption = "Source: OSM_NAI_AOI.gpkg, clipped to Nairobi boundary",
    linewidth = 0.10
  ),
  file.path(FIG_DIR, FIG_FILES$local_raw)
)

save_map(
  plot_single_road(
    boundary, osmnx_raw,
    title = "02 — OSMnx OSM road (raw)",
    caption = "Source: OSMnx download, projected and clipped (no simplify)",
    linewidth = 0.06
  ),
  file.path(FIG_DIR, FIG_FILES$osmnx_raw)
)

save_map(
  plot_single_road(
    boundary, local_clean,
    title = "03 — Local OSM road (cleaned)",
    caption = "Source: exploded, clipped, standardised local extract",
    linewidth = 0.08
  ),
  file.path(FIG_DIR, FIG_FILES$local_cleaned)
)

save_map(
  plot_single_road(
    boundary, osmnx_clean,
    title = "04 — OSMnx OSM road (cleaned)",
    caption = "Source: OSMnx download, simplified and cleaned",
    linewidth = 0.05
  ),
  file.path(FIG_DIR, FIG_FILES$osmnx_cleaned)
)

p_comparison <- plot_comparison(boundary, comparison, linewidth = 0.04)
save_map(p_comparison, file.path(FIG_DIR, FIG_FILES$comparison))
save_map(
  p_comparison,
  file.path(FIG_DIR, FIG_FILES$comparison_hires),
  width = 20,
  height = 20,
  dpi = 600
)

message("Done.")

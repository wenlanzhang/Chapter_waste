#!/usr/bin/env Rscript
# SVI sampling baseline with waste-positive panoids highlighted

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/2coverage_analysis"
INPUT_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737

points <- st_read(file.path(DATA_DIR, "Nairobi_sviwaste_points.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)
summary <- read.csv(file.path(DATA_DIR, "Nairobi_sviwaste_summary.csv"))
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |> st_transform(CRS_EA)

waste_positive <- points |> filter(waste_positive == 1)

subtitle <- sprintf(
  "%s SVI sampling panoids | %s waste-positive (%.2f%%)",
  comma(summary$total_svi_panoids),
  comma(summary$svi_waste_positive_panoids),
  summary$pct_svi_with_waste
)

p <- ggplot() +
  geom_sf(data = points, aes(color = "SVI sampling"), size = 0.12, alpha = 0.35) +
  geom_sf(data = waste_positive, aes(color = "Waste positive"), size = 0.55, alpha = 0.9) +
  geom_sf(data = boundary, fill = NA, color = "black", linewidth = 0.45) +
  scale_color_manual(
    name = NULL,
    values = c(
      "SVI sampling" = "#9ecae1",
      "Waste positive" = "#cb181d"
    )
  ) +
  guides(color = guide_legend(override.aes = list(size = c(2.0, 2.8), alpha = 1))) +
  coord_sf(crs = map_crs(), datum = NA, expand = FALSE) +
  labs(
    title = "Spatial distribution of Street View observations and waste-positive locations",
    subtitle = subtitle,
    caption = "SVI = unique panoids | Waste positive = panoid in waste dataset",
    x = "Easting (m)",
    y = "Northing (m)"
  ) +
  map_theme() +
  map_elements()

message("Writing figures to ", FIG_DIR)

report_path <- file.path(FIG_DIR, "Nairobi_sviwaste_positive.png")
hires_path <- file.path(FIG_DIR, "Nairobi_sviwaste_positive_hires.png")

save_map(p, report_path, width = 10, height = 10, dpi = 300)
save_map(p, hires_path, width = 20, height = 20, dpi = 600)

message("Done.")

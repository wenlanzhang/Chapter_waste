#!/usr/bin/env Rscript
# Road baseline (light grey) with SVI-uncovered road metres highlighted

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

parse_args <- function() {
  defaults <- list(svi_buffer = 50)
  args <- commandArgs(trailingOnly = TRUE)
  for (arg in args) {
    if (grepl("^--svi-buffer-m=", arg)) defaults$svi_buffer <- as.numeric(sub("^--svi-buffer-m=", "", arg))
  }
  defaults
}

file_tag <- function(svi_buffer) {
  sprintf("buf%dm", as.integer(svi_buffer))
}

args <- parse_args()
tag <- file_tag(args$svi_buffer)

coverage <- st_read(
  file.path(DATA_DIR, paste0("Nairobi_roadsvi_coverage_", tag, ".gpkg")),
  quiet = TRUE
) |> st_transform(CRS_EA)

summary <- read.csv(file.path(DATA_DIR, paste0("Nairobi_roadsvi_summary_", tag, ".csv")))
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |> st_transform(CRS_EA)

uncovered <- coverage |> filter(.data$coverage_status == "uncovered")

subtitle <- sprintf(
  "%.1f km uncovered (%.1f%%) | %s coverage parts | SVI buffer %dm",
  summary$uncovered_road_length_km,
  summary$pct_road_length_not_covered,
  comma(summary$coverage_part_count),
  as.integer(args$svi_buffer)
)

p <- ggplot() +
  geom_sf(data = coverage, aes(color = "All roads"), linewidth = 0.10, alpha = 0.95) +
  geom_sf(data = uncovered, aes(color = "Not covered by SVI"), linewidth = 0.28, alpha = 0.95) +
  geom_sf(data = boundary, fill = NA, color = "black", linewidth = 0.45) +
  scale_color_manual(
    name = NULL,
    values = c(
      "All roads" = "#c8c8c8",
      "Not covered by SVI" = "#cb181d"
    )
  ) +
  guides(color = guide_legend(override.aes = list(linewidth = c(1.0, 1.6), alpha = 1))) +
  coord_sf(crs = map_crs(), datum = NA, expand = FALSE) +
  labs(
    title = "Road metres not covered by SVI",
    subtitle = subtitle,
    caption = paste0(
      "SVI coverage = road metres outside ", as.integer(args$svi_buffer),
      " m panoid buffer union (partial gaps shown)"
    ),
    x = "Easting (m)",
    y = "Northing (m)"
  ) +
  map_theme() +
  map_elements()

message("Writing figures to ", FIG_DIR)

report_path <- file.path(FIG_DIR, paste0("Nairobi_roadsvi_uncovered_", tag, ".png"))
hires_path <- file.path(FIG_DIR, paste0("Nairobi_roadsvi_uncovered_", tag, "_hires.png"))

# Report quality (~3000 x 3000 px)
save_map(p, report_path, width = 10, height = 10, dpi = 300)

# High resolution for zooming (~12000 x 12000 px)
save_map(p, hires_path, width = 20, height = 20, dpi = 600)

message("Done.")

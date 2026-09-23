#!/usr/bin/env Rscript
# City -> road on the 100 m grid: distribution panels from 1cityroad.py
#   A: road density across cells with road
#   B: distance to nearest road across road-excluded cells

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
  library(hrbrthemes)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
# Light tan bars; median/mean lines in the two darkest chapter browns
FILL_COLOUR <- GSVI_COLOUR          # #C9A27F
MEDIAN_COLOUR <- WASTE_DARK_COLOUR  # #4D2D18
MEAN_COLOUR <- WASTE_COLOUR         # #6B4226

parse_args <- function() {
  defaults <- list(road_buffer = 50)
  for (arg in commandArgs(trailingOnly = TRUE)) {
    if (grepl("^--road-buffer-m=", arg)) defaults$road_buffer <- as.numeric(sub("^--road-buffer-m=", "", arg))
  }
  defaults
}

panel_theme <- function() {
  theme_ipsum(base_size = 11) +
    theme(
      plot.background = element_rect(fill = NA, color = NA),
      panel.background = element_rect(fill = NA, color = NA),
      plot.title = element_text(face = "bold", size = 12.5, hjust = 0, color = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.5, hjust = 0, color = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      plot.tag = element_text(size = 12, face = "bold", color = CHAPTER_TITLE_COLOUR),
      plot.tag.position = c(0.02, 0.98),
      axis.title = element_text(size = 10, color = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 9, color = CHAPTER_SUBTITLE_COLOUR),
      plot.margin = margin(10, 14, 8, 12)
    )
}

args <- parse_args()
buf <- as.integer(args$road_buffer)
tag <- sprintf("buf%dm", buf)

cells <- st_read(file.path(DATA_DIR, "1_Nairobi_cityroad_grid100m_32737.gpkg"), quiet = TRUE) |> st_drop_geometry()
summary <- read.csv(file.path(DATA_DIR, sprintf("1_Nairobi_cityroad_summary_%s.csv", tag)))

with_road <- cells |> filter(intersects_road == 1)
excluded <- cells |> filter(road_accessible == 0)

# --- A: road density, cells with road ---------------------------------------
dens_cap <- quantile(with_road$road_density_km_per_km2, 0.99)
p_density <- ggplot(with_road, aes(x = pmin(road_density_km_per_km2, dens_cap))) +
  geom_histogram(bins = 40, fill = FILL_COLOUR, color = "white", linewidth = 0.2) +
  geom_vline(xintercept = median(with_road$road_density_km_per_km2), color = MEDIAN_COLOUR, linewidth = 0.9) +
  geom_vline(xintercept = mean(with_road$road_density_km_per_km2), color = MEAN_COLOUR, linewidth = 0.9, linetype = "dashed") +
  scale_x_continuous(labels = label_number(accuracy = 1)) +
  scale_y_continuous(labels = comma) +
  labs(
    tag = "A",
    title = "Road density, cells with road",
    subtitle = sprintf(
      "n = %s  |  median = %.1f  |  mean = %.1f km/km²  (x capped at 99th pct)",
      comma(nrow(with_road)), median(with_road$road_density_km_per_km2), mean(with_road$road_density_km_per_km2)
    ),
    x = "Road density (km/km²)",
    y = "100 m cells"
  ) +
  panel_theme()

# --- B: distance to nearest road, excluded cells -----------------------------
dist_cap <- quantile(excluded$dist_road_edge_m, 0.99)
p_dist <- ggplot(excluded, aes(x = pmin(dist_road_edge_m, dist_cap))) +
  geom_histogram(bins = 40, fill = FILL_COLOUR, color = "white", linewidth = 0.2) +
  geom_vline(xintercept = median(excluded$dist_road_edge_m), color = MEDIAN_COLOUR, linewidth = 0.9) +
  geom_vline(xintercept = mean(excluded$dist_road_edge_m), color = MEAN_COLOUR, linewidth = 0.9, linetype = "dashed") +
  scale_x_continuous(labels = label_number(accuracy = 1)) +
  scale_y_continuous(labels = comma) +
  labs(
    tag = "B",
    title = "Distance to nearest road, road-excluded cells",
    subtitle = sprintf(
      "n = %s (%.1f%% of cells)  |  median = %s m  |  90th pct = %s m",
      comma(nrow(excluded)), summary$pct_cells_road_excluded,
      comma(round(median(excluded$dist_road_edge_m))), comma(round(quantile(excluded$dist_road_edge_m, 0.9)))
    ),
    x = "Distance from cell edge to nearest road (m)",
    y = "100 m cells"
  ) +
  panel_theme()

analysis <- (p_density + p_dist) +
  plot_annotation(
    title = "Road access on the 100 m grid",
    subtitle = sprintf(
      "Nairobi | %s cells | road-accessible (≤%d m) %.1f%% | road-excluded %.1f%%",
      comma(summary$n_cells), buf, summary$pct_cells_road_accessible, summary$pct_cells_road_excluded
    ),
    caption = "Solid = median | Dashed = mean",
    theme = theme(
      plot.title = element_text(size = 14, color = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 10, color = CHAPTER_SUBTITLE_COLOUR),
      plot.caption = element_text(size = 8, color = CHAPTER_SUBTITLE_COLOUR),
      plot.background = element_rect(fill = NA, color = NA)
    )
  )

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
path <- file.path(FIG_DIR, sprintf("1_Nairobi_cityroad_analysis_%s.png", tag))
save_map(analysis, path, width = 12, height = 5.5, dpi = 300, bg = "transparent")
message("Done.")

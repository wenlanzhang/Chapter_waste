#!/usr/bin/env Rscript
# 100 m grid waste/SVI ratio maps — gsvi vs gsvi_selfcollected (IDEAMaps fixed bands)

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(patchwork)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
GRID_DIR <- file.path(DATA_ROOT, "3_100m")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")

WGS84 <- 4326

RESULT_PALETTE <- c(
  "0" = "#f0ede8",
  "1" = "#E5C8A9",
  "2" = "#C9A27F",
  "3" = "#6B4226"
)

RESULT_LABELS <- c(
  "0" = "No SVI data",
  "1" = "Low (0–2.4%)",
  "2" = "Medium (2.5–16.4%)",
  "3" = "High (>16.4%)"
)

MAP_SPECS <- list(
  list(
    tag = "gsvi",
    gpkg = "Nairobi_grid_waste_ratio_gsvi_32737.gpkg",
    panel = "(A) GSVI only (Google)",
    subtitle = "Waste detections / GSVI images per 100 m cell"
  ),
  list(
    tag = "gsvi_selfcollected",
    gpkg = "Nairobi_grid_waste_ratio_gsvi_selfcollected_32737.gpkg",
    panel = "(B) GSVI + self-collected",
    subtitle = "Waste detections / all SVI images per 100 m cell"
  )
)

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

build_grid_map <- function(grid, boundary, panel_title, subtitle_text, base_size = 11) {
  grid <- grid |>
    mutate(result_chr = as.character(as.integer(result)))

  cells_with_data <- grid |> filter(total_svi_images > 0L)
  n_svi <- sum(grid$total_svi_images, na.rm = TRUE)
  n_waste <- sum(grid$waste_points, na.rm = TRUE)

  p <- ggplot() +
    geom_sf(data = grid, fill = "#fafafa", colour = NA) +
    geom_sf(
      data = cells_with_data,
      aes(fill = result_chr),
      colour = NA
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.0) +
    scale_fill_manual(
      name = "Waste accumulation level",
      values = RESULT_PALETTE,
      labels = RESULT_LABELS,
      drop = FALSE
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = panel_title,
      subtitle = paste0(
        subtitle_text,
        "SVI images: ",
        format(n_svi, big.mark = ",", trim = TRUE),
        " | Waste: ",
        format(n_waste, big.mark = ",", trim = TRUE),
        " | Fixed bands: Low ≤2.4%, Medium ≤16.4%, High >16.4%"
      ),
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size) +
    theme(
      plot.subtitle = element_text(
        size = base_size - 1.5,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 6)
      )
    )

  mitigation_map_decorations(p)
}

message("Reading boundary...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
plots <- list()

for (spec in MAP_SPECS) {
  message("Building map: ", spec$tag)
  grid <- read_wgs84(file.path(GRID_DIR, spec$gpkg))

  p <- build_grid_map(
    grid = grid,
    boundary = boundary,
    panel_title = spec$panel,
    subtitle_text = spec$subtitle,
    base_size = 11
  )

  out_path <- file.path(FIG_DIR, paste0("Grid_waste_ratio_", spec$tag, ".png"))
  save_mitigation_map(p, out_path, boundary)
  message("  ", basename(out_path))

  plots[[spec$tag]] <- build_grid_map(
    grid = grid,
    boundary = boundary,
    panel_title = spec$panel,
    subtitle_text = spec$subtitle,
    base_size = 9.5
  )
}

message("Building comparison panel...")
comparison <- wrap_plots(plots$gsvi, plots$gsvi_selfcollected, ncol = 2) +
  plot_annotation(
    title = "100 m Grid Waste Ratio — Nairobi",
    subtitle = "IDEAMaps fixed probability bands on Empirical Bayes smoothed waste/SVI ratio",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 10, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 8))
    )
  )

comparison_path <- file.path(FIG_DIR, "Grid_waste_ratio_comparison.png")
comparison_size <- mitigation_fig_size(boundary, width = 8, title_pad = 0.9)
ggsave(
  comparison_path,
  plot = comparison,
  width = 16,
  height = comparison_size$height,
  dpi = 600,
  bg = "white"
)
message("  ", basename(comparison_path))
message("Done.")

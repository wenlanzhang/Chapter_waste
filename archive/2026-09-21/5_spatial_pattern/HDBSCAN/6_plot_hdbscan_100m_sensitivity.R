#!/usr/bin/env Rscript
# Experiment 4 sensitivity: panoid HDBSCAN vs 100 m-cell HDBSCAN hotspots

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
DATA_ROOT <- chapter_data_root
HDB_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "HDBSCAN")
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "HDBSCAN")

source(file.path(script_dir, "..", "..", "R", "mitigation_map_theme.R"))

panoid_hull <- file.path(HDB_DIR, "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg")
cell_hull <- file.path(HDB_DIR, "Nairobi_waste_hotspot_polygons_100m_cells_32737.gpkg")
boundary_path <- file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg")
summary_path <- file.path(HDB_DIR, "Nairobi_hdbscan_100m_sensitivity_summary.csv")

if (!file.exists(cell_hull)) {
  stop(
    "Missing 100 m sensitivity polygons. Run:\n",
    "  python 5_spatial_pattern/HDBSCAN/6_hdbscan_100m_sensitivity.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cells <- st_read(cell_hull, quiet = TRUE)
boundary <- st_read(boundary_path, quiet = TRUE)
panoids <- if (file.exists(panoid_hull)) st_read(panoid_hull, quiet = TRUE) else NULL
summary <- if (file.exists(summary_path)) read.csv(summary_path) else NULL

jacc <- if (!is.null(summary) && "jaccard_vs_panoid_hotspots" %in% names(summary)) {
  sprintf("Jaccard = %.3f", summary$jaccard_vs_panoid_hotspots[1])
} else {
  ""
}

p <- ggplot() +
  geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 0.4)

if (!is.null(panoids) && nrow(panoids) > 0) {
  p <- p +
    geom_sf(
      data = panoids,
      aes(fill = "Panoid HDBSCAN"),
      colour = NA,
      alpha = 0.45
    )
}

p <- p +
  geom_sf(
    data = cells,
    aes(fill = "100 m-cell HDBSCAN"),
    colour = NA,
    alpha = 0.45
  ) +
  scale_fill_manual(
    values = c(
      "Panoid HDBSCAN" = "#C9A27F",
      "100 m-cell HDBSCAN" = "#6B4226"
    )
  ) +
  labs(
    title = "HDBSCAN sensitivity: panoid vs 100 m positive cells",
    subtitle = paste(
      "Cell positive if ≥1 waste-positive panorama; one centroid per cell.",
      jacc
    ),
    fill = NULL
  ) +
  mitigation_map_theme()

out <- file.path(FIG_DIR, "HDBSCAN_100m_cell_sensitivity.png")
ggsave(out, p, width = 8.5, height = 8.0, dpi = 300)
message("Wrote ", out)

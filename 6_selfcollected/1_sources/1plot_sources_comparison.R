#!/usr/bin/env Rscript
# Step 6.1 — where the two kinds of imagery are.
#   1_Sources_gsvi_selfcollected.png
#     (A) street-level imagery by source
#     (B) verified waste detections by source
#
# Self-collected points are drawn on top of the GSVI cloud, so the figure reads
# as "what was added and where", not as two independent maps.
#
# Inputs (1prepare_chapter_data/):
#   Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg
#   Nairobi_Waste_point_{gsvi,gsvi_selfcollected}_32737.gpkg
#   Nairobi_boundary_polygon_32737.gpkg, Nairobi_slum_polygon_32737.gpkg

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "mitigation_map_theme.R"))
source(file.path(script_dir, "../..", "R", "compare_sources_maps.R"))

INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "1_sources")
SVI_GPKG <- file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg")
OUT_PATH <- file.path(FIG_DIR, "1_Sources_gsvi_selfcollected.png")

if (!file.exists(SVI_GPKG)) {
  stop("Missing ", SVI_GPKG, " — run 1prepare_chapter_data/1_prepare_chapter_data.py first")
}

message("Reading layers...")
layers <- load_compare_layers(INPUT_DIR, SVI_GPKG)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

panel_svi <- build_svi_sources_map(
  all_svi = layers$svi_layers$all,
  gsvi_svi = layers$svi_layers$gsvi,
  self_svi = layers$svi_layers$self_collected,
  boundary = layers$boundary,
  slums_union = layers$slums_union,
  panel_title = "(A) Street-level imagery by source",
  base_size = 9.5
)

panel_waste <- build_waste_sources_map(
  all_svi = layers$svi_layers$all,
  gsvi_waste = layers$waste_layers$gsvi,
  self_waste = layers$waste_layers$self_collected,
  boundary = layers$boundary,
  slums_union = layers$slums_union,
  panel_title = "(B) Verified waste detections by source",
  base_size = 9.5
)

message("Building comparison panel...")
fig <- wrap_plots(panel_svi, panel_waste, ncol = 2) +
  plot_annotation(
    title = "Self-collected imagery alongside Google Street View",
    subtitle = sprintf(
      "Nairobi | %s GSVI locations + %s self-collected images (Faith/ + ZWL/)",
      comma(nrow(layers$svi_layers$gsvi)), comma(nrow(layers$svi_layers$self_collected))
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 10, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 8))
    )
  )

fig_size <- mitigation_fig_size(layers$boundary, width = 8, title_pad = 0.9)
ggsave(OUT_PATH, plot = fig, width = 16, height = fig_size$height, dpi = 600, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

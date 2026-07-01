#!/usr/bin/env Rscript
# Two-panel comparison: SVI imagery by source (A) and waste detections by source (B)

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
source(file.path(script_dir, "..", "R", "mitigation_map_theme.R"))
source(file.path(script_dir, "..", "R", "compare_sources_maps.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "4_compare")
SVI_GPKG <- file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg")

message("Reading layers...")
layers <- load_compare_layers(INPUT_DIR, SVI_GPKG)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

panel_svi <- build_svi_sources_map(
  all_svi = layers$svi_layers$all,
  gsvi_svi = layers$svi_layers$gsvi,
  self_svi = layers$svi_layers$self_collected,
  boundary = layers$boundary,
  slums_union = layers$slums_union,
  panel_title = "(A) Street View Imagery by Source",
  base_size = 9.5
)

panel_waste <- build_waste_sources_map(
  all_svi = layers$svi_layers$all,
  gsvi_waste = layers$waste_layers$gsvi,
  self_waste = layers$waste_layers$self_collected,
  boundary = layers$boundary,
  slums_union = layers$slums_union,
  panel_title = "(B) Waste Detections by Source",
  base_size = 9.5
)

message("Building comparison panel...")
comparison <- wrap_plots(panel_svi, panel_waste, ncol = 2) +
  plot_annotation(
    title = "GSVI and Self-Collected Imagery in Nairobi",
    subtitle = "Google Street View (GSVI) vs supplementary field imagery (Faith/ + ZWL/)",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(
        size = 10,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 8)
      )
    )
  )

comparison_path <- file.path(FIG_DIR, "Sources_gsvi_selfcollected_comparison.png")
comparison_size <- mitigation_fig_size(layers$boundary, width = 8, title_pad = 0.9)
ggsave(
  comparison_path,
  plot = comparison,
  width = 16,
  height = comparison_size$height,
  dpi = 600,
  bg = "white"
)
message("Wrote ", comparison_path)
message("Done.")

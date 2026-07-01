#!/usr/bin/env Rscript
# Waste detections by source — GSVI (Google) vs self-collected (Faith + ZWL)

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
source(file.path(script_dir, "..", "R", "compare_sources_maps.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "4_compare")
SVI_GPKG <- file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg")

message("Reading layers...")
layers <- load_compare_layers(INPUT_DIR, SVI_GPKG)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

p <- build_waste_sources_map(
  all_svi = layers$svi_layers$all,
  gsvi_waste = layers$waste_layers$gsvi,
  self_waste = layers$waste_layers$self_collected,
  boundary = layers$boundary,
  slums_union = layers$slums_union
)
out_path <- file.path(FIG_DIR, "Waste_sources_gsvi_selfcollected.png")
save_mitigation_map(p, out_path, layers$boundary)
message("Wrote ", out_path)
message("Done.")

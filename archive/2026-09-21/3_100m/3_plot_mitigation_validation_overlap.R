#!/usr/bin/env Rscript
# Self-collected overlap (n = 133) — binary vs 3-class, GSVI vs G+Self

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(cowplot)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "mitigation_validation_charts.R"))

plot_mitigation_overlap("colour", script_dir)

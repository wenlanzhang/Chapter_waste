#!/usr/bin/env Rscript
# GSVI -> analytical grid: two maps from 5_gridsvi.py
#   (1) direct observation: cells with >=1 GSVI image vs none
#   (2) distance to nearest GSVI panorama for unobserved cells

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "chapter_arms.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

ARM <- parse_arm_arg()
OBS_NAME <- if (ARM == "gsvi") "GSVI" else "SVI"

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737

grid <- st_read(file.path(DATA_DIR, arm_filename("5_Nairobi_gridsvi_grid100m", ARM)), quiet = TRUE) |>
  st_transform(CRS_EA)
summary <- read.csv(file.path(DATA_DIR, arm_filename("5_Nairobi_gridsvi_summary", ARM, suffix = "", ext = "csv")))
boundary <- st_read(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)
far_m <- as.integer(summary$far_m)
sfx <- arm_fig_suffix(ARM)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
message("Writing figures to ", FIG_DIR)

# --- (1) Direct observation --------------------------------------------------
OBS_LEVELS <- c("observed", "unobserved")
OBS_LABELS <- c(observed = sprintf("≥1 %s image", OBS_NAME), unobserved = sprintf("No %s image", OBS_NAME))
OBS_COLOURS <- c(observed = WASTE_DARK_COLOUR, unobserved = ROAD_BASELINE_COLOUR)

grid <- grid |>
  mutate(obs_class = factor(if_else(has_gsvi == 1, "observed", "unobserved"), levels = OBS_LEVELS))

p_obs <- make_base_map(
  boundary,
  title = sprintf("Direct %s observation on the 100 m grid", OBS_NAME),
  subtitle = sprintf(
    "%s cells | %.1f%% with ≥1 image | median %d images per observed cell",
    comma(summary$n_cells), summary$pct_cells_observed, as.integer(round(summary$median_images_per_observed_cell))
  ),
  caption = sprintf("%s images (Step 1) counted within each cell", OBS_NAME),
  transparent_bg = TRUE
) +
  geom_sf(data = grid, aes(fill = obs_class), color = NA, linewidth = 0) +
  scale_fill_manual(name = "Observation", values = OBS_COLOURS, labels = OBS_LABELS, drop = FALSE) +
  theme(legend.key.size = unit(0.55, "cm"), legend.text = element_text(size = 7.5))

save_map(p_obs, file.path(FIG_DIR, paste0("5_Nairobi_gridsvi_observed_grid100m", sfx, ".png")),
         limits = boundary, base_size = 10, bg = "transparent")

# --- (2) Distance to nearest observation, unobserved cells -------------------
unobserved <- grid |> filter(has_gsvi == 0)
p_dist <- make_base_map(
  boundary,
  title = sprintf("Distance to nearest %s observation, unobserved cells", OBS_NAME),
  subtitle = sprintf(
    "%s unobserved cells (%.1f%%) | median %s m | %.1f%% of all cells >%d m",
    comma(nrow(unobserved)), summary$pct_cells_unobserved,
    comma(round(summary$median_dist_unobserved_m)), summary$pct_cells_beyond_far, far_m
  ),
  caption = sprintf("Cell centroid to nearest %s panorama | observed cells in grey", OBS_NAME),
  transparent_bg = TRUE
) +
  geom_sf(data = grid |> filter(has_gsvi == 1), fill = ROAD_BASELINE_COLOUR, color = NA, linewidth = 0) +
  geom_sf(data = unobserved, aes(fill = dist_nearest_obs_m), color = NA, linewidth = 0) +
  scale_fill_gradientn(
    name = "Distance to\nobservation (m)",
    colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR),
    limits = c(0, quantile(unobserved$dist_nearest_obs_m, 0.99)),
    oob = squish,
    labels = label_number(accuracy = 1)
  )

save_map(p_dist, file.path(FIG_DIR, paste0("5_Nairobi_gridsvi_distance_grid100m", sfx, ".png")),
         limits = boundary, base_size = 10, bg = "transparent")

message("Done.")

#!/usr/bin/env Rscript
# Step 4 figure 1 — construction of the 100 m visible-waste indicator.
#   1_Nairobi_indicator_panels_grid100m_gsvi.png
#     A. Directly observed indicator  — Empirical Bayes ratio, cells with GSVI imagery only
#     B. Interpolated indicator       — after the linear spatial fill, all represented cells
#     C. Published 3-class indicator  — Jenks classes as submitted to IDEAMaps
#
# The point of putting A beside B is that the reader can see where the surface
# rests on measurement and where it is spatial estimation. C shows what that
# becomes once it is discretised for the platform.
#
# Input: 4_100m/1_Nairobi_indicator_grid100m_gsvi_32737.gpkg (1_indicator_build.py)

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "4_100m")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
GRID_GPKG <- file.path(DATA_DIR, "1_Nairobi_indicator_grid100m_gsvi_32737.gpkg")
FIG_DIR <- file.path(script_dir, "..", "Figure", "4_100m")
CRS_EA <- 32737

if (!file.exists(GRID_GPKG)) {
  stop("Missing ", GRID_GPKG, " — run 4_100m/1_indicator_build.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

grid <- st_read(GRID_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
boundary <- st_read(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)

DIRECT <- "Direct observation"
INTERPOLATED <- "Interpolated support"
UNSUPPORTED <- "Unsupported, platform-coded low"

observed <- grid |> filter(indicator_provenance == DIRECT)
represented <- grid |> filter(indicator_provenance != UNSUPPORTED)
unsupported <- grid |> filter(indicator_provenance == UNSUPPORTED)

n_cells <- nrow(grid)
n_obs <- nrow(observed)
n_rep <- nrow(represented)
n_unsup <- nrow(unsupported)

# Panels A and B must share a colour scale or the comparison is meaningless.
# The ratio is heavily zero-inflated, so cap at the 99th percentile of the
# represented surface and squish the tail rather than let a few cells set the range.
ratio_cap <- as.numeric(quantile(represented$final_waste_ratio, 0.99, na.rm = TRUE))
RATIO_COLOURS <- c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR, WASTE_DARK_COLOUR)

ratio_scale <- function(name) {
  scale_fill_gradientn(
    name = name,
    colours = RATIO_COLOURS,
    limits = c(0, ratio_cap),
    oob = squish,
    labels = label_number(accuracy = 0.001),
    guide = guide_colorbar(
      barwidth = unit(0.42, "cm"), barheight = unit(2.6, "cm"),
      frame.colour = "grey78", frame.linewidth = 0.3
    )
  )
}

panel_theme <- function(p) {
  p + theme(
    plot.title = element_text(face = "bold", size = 11.5, hjust = 0, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, hjust = 0, colour = CHAPTER_SUBTITLE_COLOUR,
                                 margin = margin(b = 4)),
    legend.title = element_text(size = 8, face = "bold", colour = CHAPTER_AXIS_COLOUR),
    legend.text = element_text(size = 7.2, colour = CHAPTER_SUBTITLE_COLOUR),
    legend.key.size = unit(0.4, "cm"),
    plot.margin = margin(4, 6, 4, 4)
  )
}

# --- A. directly observed ----------------------------------------------------
p_a <- make_base_map(
  boundary,
  title = "A. Directly observed indicator",
  subtitle = sprintf(
    "%s cells (%.1f%% of grid) with ≥1 GSVI image | grey = no imagery",
    comma(n_obs), 100 * n_obs / n_cells
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid, fill = ROAD_BASELINE_COLOUR, colour = NA, linewidth = 0) +
  geom_sf(data = observed, aes(fill = smoothed_waste_ratio), colour = NA, linewidth = 0) +
  ratio_scale("Waste /\nimage ratio")

# --- B. interpolated ---------------------------------------------------------
p_b <- make_base_map(
  boundary,
  title = "B. Interpolated indicator",
  subtitle = sprintf(
    "%s cells represented (%.1f%%) | %s beyond the fill, coded lowest",
    comma(n_rep), 100 * n_rep / n_cells, comma(n_unsup)
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid, fill = ROAD_BASELINE_COLOUR, colour = NA, linewidth = 0) +
  geom_sf(data = represented, aes(fill = final_waste_ratio), colour = NA, linewidth = 0) +
  ratio_scale("Waste /\nimage ratio")

# --- C. published classes ----------------------------------------------------
CLASS_LEVELS <- c("Low", "Medium", "High")
CLASS_COLOURS <- c(Low = CHAPTER_SEQ_LOW, Medium = GSVI_COLOUR, High = WASTE_COLOUR)
grid_cls <- grid |>
  mutate(class_label = factor(CLASS_LEVELS[result + 1], levels = CLASS_LEVELS))
cls_n <- table(grid_cls$class_label)

p_c <- make_base_map(
  boundary,
  title = "C. Published 3-class indicator",
  subtitle = sprintf(
    "Jenks k=3, IDEAMaps submission breaks | Low %s / Medium %s / High %s",
    comma(cls_n[["Low"]]), comma(cls_n[["Medium"]]), comma(cls_n[["High"]])
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid_cls, aes(fill = class_label), colour = NA, linewidth = 0) +
  scale_fill_manual(name = "Class", values = CLASS_COLOURS, drop = FALSE)

fig <- (panel_theme(p_a) | panel_theme(p_b) | panel_theme(p_c)) +
  plot_annotation(
    title = "Construction of the 100 m visible-waste indicator",
    subtitle = sprintf(
      "Nairobi | %s cells | GSVI arm | Empirical Bayes waste/image ratio, linear spatial fill, Jenks k=3",
      comma(n_cells)
    ),
    caption = paste0(
      "A shows only cells whose value comes from imagery actually collected there; B adds the cells whose value is estimated ",
      "by interpolating between them.\nThe two panels share a colour scale, capped at the 99th percentile of the represented surface. ",
      sprintf(
        "Of the %s represented cells, %.1f%% rest on direct observation.",
        comma(n_rep), 100 * n_obs / n_rep
      )
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 15, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR,
                                   margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

out <- file.path(FIG_DIR, "1_Nairobi_indicator_panels_grid100m_gsvi.png")
ggsave(out, fig, width = 15.5, height = 6.4, dpi = 400, bg = "white")
message("Wrote ", out)
message("Done.")

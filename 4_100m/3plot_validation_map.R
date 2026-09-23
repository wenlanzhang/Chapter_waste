#!/usr/bin/env Rscript
# Step 4 figure 3 — where the validation points sit, and where they disagree.
#   3_Nairobi_indicator_validation_map_grid100m_gsvi.png
#     A. Validated cells over the interpolated indicator surface
#     B. The same cells over indicator provenance (direct / interpolated / unsupported)
#
# Figure 2 says the indicator is far less precise where it rests on interpolation.
# This figure puts that on the map: panel B shows whether the disagreements fall
# where there was never any imagery to begin with.
#
# Inputs: 4_100m/1_Nairobi_indicator_grid100m_gsvi_32737.gpkg (1_indicator_build.py)
#         4_100m/2_Nairobi_indicator_validation_cells.csv     (2_validation.py)

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
CELLS_CSV <- file.path(DATA_DIR, "2_Nairobi_indicator_validation_cells.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "4_100m")
CRS_EA <- 32737

for (f in c(GRID_GPKG, CELLS_CSV)) {
  if (!file.exists(f)) stop("Missing ", f, " — run 4_100m/1_indicator_build.py and 2_validation.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

DIRECT <- "Direct observation"
INTERPOLATED <- "Interpolated support"
UNSUPPORTED <- "Unsupported, platform-coded low"

grid <- st_read(GRID_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
boundary <- st_read(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)
cells <- read.csv(CELLS_CSV, stringsAsFactors = FALSE)

# Validated cells become points at their centroid so they read as locations
# rather than disappearing into the 100 m surface underneath.
val <- grid |>
  inner_join(cells, by = "cell_id") |>
  mutate(
    agreement = factor(
      if_else(crowd_waste == indicator_waste, "Agree", "Disagree"),
      levels = c("Agree", "Disagree")
    )
  )
val_pts <- st_as_sf(st_drop_geometry(val), geometry = st_centroid(st_geometry(val)))

n_val <- nrow(val_pts)
n_agree <- sum(val_pts$agreement == "Agree")
AGREE_COLOURS <- c(Agree = "#5F6F5A", Disagree = "#B03A2E")

represented <- grid |> filter(indicator_provenance != UNSUPPORTED)
ratio_cap <- as.numeric(quantile(represented$final_waste_ratio, 0.99, na.rm = TRUE))

point_layers <- function(p) {
  p +
    geom_sf(data = val_pts, aes(colour = agreement), size = 0.42, alpha = 0.85, stroke = 0) +
    scale_colour_manual(name = "Crowd vs indicator", values = AGREE_COLOURS, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 2.4)))
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

# --- A. over the indicator surface -------------------------------------------
p_a <- make_base_map(
  boundary,
  title = "A. Validation points over the indicator",
  subtitle = sprintf(
    "%s validated cells | %.1f%% agree with the crowd on waste present / absent",
    comma(n_val), 100 * n_agree / n_val
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid, fill = ROAD_BASELINE_COLOUR, colour = NA, linewidth = 0) +
  geom_sf(data = represented, aes(fill = final_waste_ratio), colour = NA, linewidth = 0) +
  scale_fill_gradientn(
    name = "Waste /\nimage ratio",
    colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR, WASTE_DARK_COLOUR),
    limits = c(0, ratio_cap), oob = squish, labels = label_number(accuracy = 0.001),
    guide = guide_colorbar(barwidth = unit(0.42, "cm"), barheight = unit(2.2, "cm"),
                           frame.colour = "grey78", frame.linewidth = 0.3)
  )
p_a <- point_layers(p_a)

# --- B. over indicator provenance --------------------------------------------
PROV_LEVELS <- c(DIRECT, INTERPOLATED, UNSUPPORTED)
PROV_LABELS <- c("Directly observed", "Interpolated", "Unsupported (coded low)")
PROV_COLOURS <- setNames(c(WASTE_DARK_COLOUR, GSVI_COLOUR, CHAPTER_SEQ_LOW), PROV_LEVELS)

grid_prov <- grid |>
  mutate(provenance = factor(indicator_provenance, levels = PROV_LEVELS))
prov_n <- table(grid_prov$provenance)
n_cells <- nrow(grid_prov)

p_b <- make_base_map(
  boundary,
  title = "B. Validation points over indicator provenance",
  subtitle = sprintf(
    "Observed %.1f%% | interpolated %.1f%% | unsupported %.1f%% of %s cells",
    100 * prov_n[[DIRECT]] / n_cells, 100 * prov_n[[INTERPOLATED]] / n_cells,
    100 * prov_n[[UNSUPPORTED]] / n_cells, comma(n_cells)
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid_prov, aes(fill = provenance), colour = NA, linewidth = 0) +
  scale_fill_manual(name = "Provenance", values = PROV_COLOURS, labels = PROV_LABELS, drop = FALSE)
p_b <- point_layers(p_b)

# Agreement by provenance, recomputed here so the caption cannot drift.
by_prov <- val_pts |>
  st_drop_geometry() |>
  group_by(provenance) |>
  summarise(n = n(), agree = mean(agreement == "Agree"), .groups = "drop")
prov_caption <- paste(
  sprintf("%s %.0f%% agreement (n = %s)", by_prov$provenance, 100 * by_prov$agree, comma(by_prov$n)),
  collapse = " | "
)

fig <- (panel_theme(p_a) | panel_theme(p_b)) +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = "Where the local validation sits on the 100 m indicator",
    subtitle = sprintf("Nairobi | IDEAMaps crowd validation | %s", prov_caption),
    caption = paste0(
      "Each point is one validated 100 m cell, placed at its centroid and coloured by whether the crowd and the indicator ",
      "agree that waste is present.\nPanel B shows the same points against the evidence base: red points on the tan ",
      "interpolated surface are disagreements in cells that never had imagery of their own. ",
      "Validation coverage is clustered in a few neighbourhoods rather than spread across the city."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR,
                                   margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

out <- file.path(FIG_DIR, "3_Nairobi_indicator_validation_map_grid100m_gsvi.png")
ggsave(out, fig, width = 12.5, height = 6.4, dpi = 400, bg = "white")
message("Wrote ", out)
message("Done.")

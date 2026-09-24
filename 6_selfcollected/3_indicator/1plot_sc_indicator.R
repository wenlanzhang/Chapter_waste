#!/usr/bin/env Rscript
# Step 6.3 — what self-collected imagery does to the 100 m indicator.
#   1_SC_indicator_effect.png
#     (a) map of the cells whose published class changed, up or down
#     (b) the full 3x3 class transition matrix — every cell of the grid, with
#         the off-diagonal (the 670 that moved) called out
#     (c) those same 670 split by how they moved: received imagery, or shifted
#         through the spatial fill
#
# Panels (b) and (c) describe the same 670 cells. (b) says which classes they
# moved between and reconciles to the net change per class; (c) says how they
# got there. The contrast with the subtitle is the point of the figure: direct
# coverage barely moves, yet the published classes move a great deal.
#
# Inputs (6_selfcollected/3_indicator/, from 1_sc_indicator.py):
#   1_Nairobi_sc_indicator_grid100m_32737.gpkg
#   1_sc_indicator_provenance.csv

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "3_indicator")
PREP_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "3_indicator")

CELLS_GPKG <- file.path(DATA_DIR, "1_Nairobi_sc_indicator_grid100m_32737.gpkg")
PROVENANCE_CSV <- file.path(DATA_DIR, "1_sc_indicator_provenance.csv")
OUT_PATH <- file.path(FIG_DIR, "1_SC_indicator_effect.png")

UP_COLOUR <- "#cb181d"
DOWN_COLOUR <- "#4575b4"
UNCHANGED_COLOUR <- "#EDE7E0"
CLASS_LEVELS <- c("Low", "Medium", "High")

for (f in c(CELLS_GPKG, PROVENANCE_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 6_selfcollected/3_indicator/1_sc_indicator.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cells <- st_read(CELLS_GPKG, quiet = TRUE)
prov <- read.csv(PROVENANCE_CSV, stringsAsFactors = FALSE, check.names = FALSE)
boundary <- st_read(file.path(PREP_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE)
slums <- st_read(file.path(PREP_DIR, "Nairobi_slum_polygon_32737.gpkg"), quiet = TRUE) |> st_union()

flat <- st_drop_geometry(cells)
changed <- cells |> filter(class_change != 0)
n_changed <- nrow(changed)
n_up <- sum(changed$class_change > 0)
n_down <- sum(changed$class_change < 0)
n_with_sc <- sum(changed$received_sc == 1)

direct_share <- prov[prov$Provenance == "Direct share of represented surface", ]

class_lab <- function(x) factor(c("0" = "Low", "1" = "Medium", "2" = "High")[as.character(x)],
                               levels = CLASS_LEVELS)

# --- (a) map of changed cells ------------------------------------------------
changed_pts <- st_centroid(changed) |>
  mutate(
    direction = if_else(class_change > 0, "Moved up a class", "Moved down a class"),
    direction = factor(direction, levels = c("Moved up a class", "Moved down a class"))
  )

p_map <- ggplot() +
  geom_sf(data = boundary, fill = "white", colour = "grey55", linewidth = 0.4) +
  geom_sf(data = slums, fill = SLUM_FILL, colour = SLUM_EDGE, linewidth = 0.12, alpha = 0.38) +
  geom_sf(data = changed_pts, aes(colour = direction), size = 1.25, alpha = 0.9) +
  scale_colour_manual(
    name = NULL,
    values = c("Moved up a class" = UP_COLOUR, "Moved down a class" = DOWN_COLOUR),
    labels = c(sprintf("Moved up a class (%s)", comma(n_up)),
               sprintf("Moved down a class (%s)", comma(n_down)))
  ) +
  guides(colour = guide_legend(override.aes = list(size = 2.6))) +
  coord_sf(datum = NA, expand = FALSE) +
  labs(
    title = "(a) Where the changed cells are",
    subtitle = sprintf(
      "All %s cells that changed class | green = mapped settlements",
      comma(n_changed)
    )
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    legend.position = "bottom",
    legend.text = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
    legend.key = element_blank()
  )

# --- (b) the full class transition matrix ------------------------------------
# Every one of the 69,943 cells appears once. The diagonal is unchanged; the
# six off-diagonal entries are the changed cells and sum to n_changed.
trans <- flat |>
  mutate(from = class_lab(result_gsvi), to = class_lab(result_gsc)) |>
  count(from, to, name = "n") |>
  complete(from, to, fill = list(n = 0)) |>
  mutate(
    moved = as.integer(to) - as.integer(from),
    kind = case_when(moved > 0 ~ "up", moved < 0 ~ "down", TRUE ~ "same"),
    label = comma(n)
  )

stopifnot(sum(trans$n[trans$kind != "same"]) == n_changed)

net <- flat |>
  summarise(
    Low = sum(result_gsc == 0) - sum(result_gsvi == 0),
    Medium = sum(result_gsc == 1) - sum(result_gsvi == 1),
    High = sum(result_gsc == 2) - sum(result_gsvi == 2)
  ) |>
  pivot_longer(everything(), names_to = "to", values_to = "net") |>
  mutate(to = factor(to, levels = CLASS_LEVELS))

trans <- trans |> mutate(from_rev = factor(as.character(from), levels = rev(CLASS_LEVELS)))

p_trans <- ggplot(trans, aes(to, from_rev)) +
  geom_tile(aes(fill = kind), colour = "white", linewidth = 1.1) +
  geom_text(aes(label = label, fontface = if_else(kind == "same", "plain", "bold")),
            size = 3.4,
            colour = if_else(trans$kind == "same", "#8C8078", "white")) +
  scale_fill_manual(
    name = NULL,
    values = c(same = UNCHANGED_COLOUR, up = UP_COLOUR, down = DOWN_COLOUR),
    breaks = c("up", "down", "same"),
    labels = c(sprintf("Moved up (%s cells)", comma(n_up)),
               sprintf("Moved down (%s cells)", comma(n_down)),
               "Unchanged")
  ) +
  scale_x_discrete(position = "top", expand = expansion(0)) +
  scale_y_discrete(expand = expansion(0)) +
  labs(
    title = "(b) Which classes they moved between",
    subtitle = sprintf(
      "All %s cells | off-diagonal = the %s that changed | net: Low %s, Medium %s, High %s",
      comma(nrow(flat)), comma(n_changed),
      sprintf("%+d", net$net[net$to == "Low"]),
      sprintf("%+d", net$net[net$to == "Medium"]),
      sprintf("%+d", net$net[net$to == "High"])
    ),
    x = "Class with GSVI + SC", y = "Class with GSVI"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 9, colour = CHAPTER_AXIS_COLOUR),
    panel.grid = element_blank(),
    legend.position = "bottom",
    legend.text = element_text(size = 8.4)
  )

# --- (c) how those same cells got there ---------------------------------------
route <- tibble(
  route = c("Received self-collected imagery", "Changed through the spatial fill"),
  n = c(n_with_sc, n_changed - n_with_sc)
) |>
  mutate(
    route = factor(route, levels = c("Changed through the spatial fill", "Received self-collected imagery")),
    label = sprintf("%s (%.1f%%)", comma(n), 100 * n / n_changed)
  )

p_route <- ggplot(route, aes(x = n, y = "route", fill = route)) +
  geom_col(width = 0.38, colour = "white", linewidth = 0.35) +
  geom_text(aes(label = label), position = position_stack(vjust = 0.5),
            size = 3.1, fontface = "bold", colour = "white") +
  scale_fill_manual(name = NULL, values = c(
    "Received self-collected imagery" = "#6B4226",
    "Changed through the spatial fill" = "#C9A27F"
  ), breaks = c("Received self-collected imagery", "Changed through the spatial fill")) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02)), labels = comma) +
  labs(
    title = sprintf("(c) How those same %s cells got there", comma(n_changed)),
    subtitle = "Nine in ten never received an image — their class moved through interpolation",
    x = "100 m cells", y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title.x = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text.x = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    axis.text.y = element_blank(),
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    legend.text = element_text(size = 8.4)
  )

fig <- (p_map | (p_trans / p_route + plot_layout(heights = c(2.1, 1)))) +
  plot_layout(widths = c(1, 1.05)) +
  plot_annotation(
    title = "Adding self-collected imagery to the 100 m indicator",
    subtitle = sprintf(
      "Direct evidence carries %s of the represented surface before and %s after (%s) | 2,979 extra images, 149 extra waste detections",
      direct_share$GSVI, direct_share$`GSVI + SC`, direct_share$Change
    ),
    caption = paste0(
      "Same IDEAMaps pipeline, same grid and same fixed Jenks break points on both arms; only the imagery differs. ",
      "Panels (b) and (c) describe the same ", comma(n_changed), " cells.\n",
      "More imagery does not close the interpolation gap — but it does move the published classes, and mostly in cells that were never observed."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 13, height = 6.8, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

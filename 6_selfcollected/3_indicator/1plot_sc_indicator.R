#!/usr/bin/env Rscript
# Step 6.3 — what self-collected imagery does to the 100 m indicator.
#   1_SC_indicator_effect.png
#     (a) map of the cells whose published class changed, up or down
#     (b) class counts before and after, with the change decomposed into cells
#         that received imagery vs cells that moved through the spatial fill
#
# The contrast is the point: direct coverage barely moves (+127 cells, +0.2 pp
# of the represented surface), yet the published classes move a great deal, and
# nine in ten of the cells that move never received an image.
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
CLASS_COLOURS <- c(Low = "#E8DFD5", Medium = "#C9A27F", High = "#6B4226")

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
    labels = c(
      sprintf("Moved up a class (%s cells)", comma(n_up)),
      sprintf("Moved down a class (%s cells)", comma(n_down))
    )
  ) +
  guides(colour = guide_legend(override.aes = list(size = 2.6))) +
  coord_sf(datum = NA, expand = FALSE) +
  labs(
    title = "(a) Cells whose published class changed",
    subtitle = sprintf(
      "%s of %s cells (%.1f%%) | green = mapped settlements",
      comma(n_changed), comma(nrow(cells)), 100 * n_changed / nrow(cells)
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

# --- (b) class counts before and after ---------------------------------------
class_lab <- c("0" = "Low", "1" = "Medium", "2" = "High")
counts <- bind_rows(
  tibble(arm = "GSVI", class = class_lab[as.character(flat$result_gsvi)]),
  tibble(arm = "GSVI + SC", class = class_lab[as.character(flat$result_gsc)])
) |>
  count(arm, class) |>
  mutate(
    arm = factor(arm, levels = c("GSVI", "GSVI + SC")),
    class = factor(class, levels = c("Low", "Medium", "High"))
  )

# Low dominates by two orders of magnitude, so plot Medium and High only and say so.
counts_mh <- counts |> filter(class != "Low")

p_bars <- ggplot(counts_mh, aes(class, n, fill = arm)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.6) +
  geom_text(
    aes(label = comma(n)),
    position = position_dodge(width = 0.7),
    vjust = -0.45, size = 3, fontface = "bold", colour = CHAPTER_AXIS_COLOUR
  ) +
  scale_fill_manual(name = NULL, values = c("GSVI" = "#BDB3A8", "GSVI + SC" = "#6B4226")) +
  scale_y_continuous(
    limits = c(0, max(counts_mh$n) * 1.16),
    expand = expansion(mult = c(0, 0.02)), labels = comma
  ) +
  labs(
    title = "(b) Published classes, before and after",
    subtitle = sprintf(
      "Low class omitted (%s → %s cells) | High grows %+.0f%%",
      comma(counts$n[counts$arm == "GSVI" & counts$class == "Low"]),
      comma(counts$n[counts$arm == "GSVI + SC" & counts$class == "Low"]),
      100 * (counts$n[counts$arm == "GSVI + SC" & counts$class == "High"] /
               counts$n[counts$arm == "GSVI" & counts$class == "High"] - 1)
    ),
    x = NULL, y = "100 m cells"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 9, colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_blank(),
    legend.position = "bottom"
  )

# --- (c) how the changed cells got there -------------------------------------
route <- tibble(
  route = c("Received self-collected imagery", "Changed through the spatial fill"),
  n = c(n_with_sc, n_changed - n_with_sc)
) |>
  mutate(
    route = factor(route, levels = c("Changed through the spatial fill", "Received self-collected imagery")),
    label = sprintf("%s\n(%.1f%%)", comma(n), 100 * n / n_changed)
  )

p_route <- ggplot(route, aes(x = n, y = "Cells changing class", fill = route)) +
  geom_col(width = 0.42, colour = "white", linewidth = 0.35) +
  geom_text(aes(label = label), position = position_stack(vjust = 0.5),
            size = 3.1, fontface = "bold", colour = "white", lineheight = 0.92) +
  scale_fill_manual(name = NULL, values = c(
    "Received self-collected imagery" = "#6B4226",
    "Changed through the spatial fill" = "#C9A27F"
  ), breaks = c("Received self-collected imagery", "Changed through the spatial fill")) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02)), labels = comma) +
  labs(
    title = "(c) How those cells changed",
    subtitle = "Nine in ten never received an image — the class moved through interpolation",
    x = "100 m cells", y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title.x = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text.x = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    axis.text.y = element_blank(),
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    legend.text = element_text(size = 8.6)
  )

fig <- (p_map | (p_bars / p_route + plot_layout(heights = c(1.6, 1)))) +
  plot_layout(widths = c(1, 1)) +
  plot_annotation(
    title = "Adding self-collected imagery to the 100 m indicator",
    subtitle = sprintf(
      "Direct evidence carries %s of the represented surface before and %s after (%s) | 2,979 extra images, 149 extra waste detections",
      direct_share$GSVI, direct_share$`GSVI + SC`, direct_share$Change
    ),
    caption = paste0(
      "Same IDEAMaps pipeline, same grid and same fixed Jenks break points on both arms; only the imagery differs.\n",
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

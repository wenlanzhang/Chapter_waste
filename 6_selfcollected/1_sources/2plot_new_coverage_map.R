#!/usr/bin/env Rscript
# Step 6.1 — what self-collected imagery adds to the 100 m observation frame.
#   2_SC_new_coverage_100m.png
#     (a) map: cells holding self-collected imagery, split by whether GSVI had
#         already reached them; newly covered cells drawn large enough to see
#     (b) where those new cells sit, against the city as a whole
#
# The count is the point of panel (a): most self-collected imagery was gathered
# inside the frame GSVI already covered, so the marginal spatial gain is small.
# Panel (b) is why it still matters — the gain is not spread evenly.
#
# Inputs (6_selfcollected/1_sources/, from 1_sc_coverage.py):
#   1_Nairobi_sc_coverage_grid100m_32737.gpkg
#   1_Nairobi_sc_coverage_summary.csv

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

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "1_sources")
PREP_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "1_sources")

CELLS_GPKG <- file.path(DATA_DIR, "1_Nairobi_sc_coverage_grid100m_32737.gpkg")
SUMMARY_CSV <- file.path(DATA_DIR, "1_Nairobi_sc_coverage_summary.csv")
OUT_PATH <- file.path(FIG_DIR, "2_SC_new_coverage_100m.png")

NEW_COLOUR <- "#cb181d"
EXISTING_COLOUR <- "#C9A27F"
GSVI_FRAME_COLOUR <- "#EDE4DA"

for (f in c(CELLS_GPKG, SUMMARY_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 6_selfcollected/1_sources/1_sc_coverage.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cells <- st_read(CELLS_GPKG, quiet = TRUE)
s <- read.csv(SUMMARY_CSV, stringsAsFactors = FALSE)[1, ]
boundary <- st_read(file.path(PREP_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE)
slums <- st_read(file.path(PREP_DIR, "Nairobi_slum_polygon_32737.gpkg"), quiet = TRUE) |> st_union()

far_m <- s$far_m

# --- (a) map ------------------------------------------------------------------
gsvi_frame <- cells |> filter(observed_gsvi == 1)
sc_cells <- cells |>
  filter(n_images_sc > 0) |>
  mutate(
    status = if_else(newly_observed == 1, "Newly covered", "Already covered by GSVI"),
    status = factor(status, levels = c("Already covered by GSVI", "Newly covered"))
  )
sc_pts <- st_centroid(sc_cells)

status_labels <- c(
  "Already covered by GSVI" = sprintf(
    "Already covered by GSVI (%s cells)",
    comma(sum(sc_cells$status == "Already covered by GSVI"))
  ),
  "Newly covered" = sprintf(
    "Newly covered (%s cells)", comma(sum(sc_cells$status == "Newly covered"))
  )
)

p_map <- ggplot() +
  geom_sf(data = boundary, fill = "white", colour = "grey55", linewidth = 0.4) +
  geom_sf(data = gsvi_frame, fill = GSVI_FRAME_COLOUR, colour = NA) +
  geom_sf(data = slums, fill = SLUM_FILL, colour = SLUM_EDGE, linewidth = 0.12, alpha = 0.38) +
  geom_sf(
    data = filter(sc_pts, status == "Already covered by GSVI"),
    aes(colour = status), size = 0.65, alpha = 0.75
  ) +
  geom_sf(
    data = filter(sc_pts, status == "Newly covered"),
    aes(colour = status), size = 1.9, alpha = 0.95
  ) +
  scale_colour_manual(name = NULL, values = c(
    "Already covered by GSVI" = EXISTING_COLOUR,
    "Newly covered" = NEW_COLOUR
  ), labels = status_labels) +
  guides(colour = guide_legend(override.aes = list(size = c(2.2, 2.8)))) +
  coord_sf(datum = NA, expand = FALSE) +
  labs(
    title = "(a) Cells holding self-collected imagery",
    subtitle = sprintf(
      "Beige = the %s cells GSVI already observed | green = mapped settlements",
      comma(s$n_cells_observed_gsvi)
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

# --- (b) where the new cells are ---------------------------------------------
new_cells <- st_drop_geometry(cells) |> filter(newly_observed == 1)
all_cells <- st_drop_geometry(cells)

pct <- function(x) 100 * mean(x)
measures <- tibble(
  measure = c(
    "Inside a mapped\nsettlement",
    "Within 500 m of\na settlement",
    sprintf("Was >%s m from\nany GSVI observation", comma(far_m))
  ),
  `Newly covered cells` = c(
    pct(new_cells$in_settlement == 1),
    pct(new_cells$dist_settlement_m <= 500),
    pct(new_cells$dist_nearest_obs_gsvi_m > far_m)
  ),
  `All cells` = c(
    pct(all_cells$in_settlement == 1),
    pct(all_cells$dist_settlement_m <= 500),
    pct(all_cells$dist_nearest_obs_gsvi_m > far_m)
  )
) |>
  pivot_longer(-measure, names_to = "group", values_to = "pct") |>
  mutate(
    measure = factor(measure, levels = rev(unique(measure))),
    group = factor(group, levels = c("Newly covered cells", "All cells"))
  )

p_bars <- ggplot(measures, aes(pct, measure, fill = group)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.62) +
  geom_text(
    aes(label = sprintf("%.1f%%", pct)),
    position = position_dodge(width = 0.72),
    hjust = -0.12, size = 2.9, fontface = "bold", colour = CHAPTER_AXIS_COLOUR
  ) +
  scale_fill_manual(name = NULL, values = c(
    "Newly covered cells" = NEW_COLOUR, "All cells" = "#BDB3A8"
  )) +
  scale_x_continuous(
    limits = c(0, max(measures$pct) * 1.22),
    expand = expansion(mult = c(0, 0.02)), labels = label_percent(scale = 1)
  ) +
  labs(
    title = "(b) Where the newly covered cells are",
    subtitle = sprintf(
      "%s new cells vs all %s urban cells | median distance to a settlement %s m vs %s m",
      comma(nrow(new_cells)), comma(nrow(all_cells)),
      comma(round(s$median_dist_settlement_new_m)), comma(round(s$median_dist_settlement_all_m))
    ),
    x = "Share of cells", y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank(),
    panel.grid.major.y = element_blank(),
    legend.position = "bottom"
  )

fig <- (p_map | p_bars) +
  plot_layout(widths = c(1, 1)) +
  plot_annotation(
    title = "What self-collected imagery adds to the 100 m observation frame",
    subtitle = sprintf(
      "Direct coverage %s%% → %s%% of urban cells (%s → %s) | %s cells hold self-collected imagery, %s of them previously unobserved",
      format(round(s$pct_cells_observed_gsvi, 1), nsmall = 1),
      format(round(s$pct_cells_observed_gsc, 1), nsmall = 1),
      comma(s$n_cells_observed_gsvi), comma(s$n_cells_observed_gsc),
      comma(s$n_cells_with_sc), comma(s$n_cells_newly_observed)
    ),
    caption = paste0(
      "Self-collected imagery carries no panoid, so each image is its own observation location. ",
      "A cell is directly observed when it contains at least one image.\n",
      "Most self-collected images fall inside cells GSVI had already reached; the cells they add are closer to mapped settlements than the city average."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 12.5, height = 6.4, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

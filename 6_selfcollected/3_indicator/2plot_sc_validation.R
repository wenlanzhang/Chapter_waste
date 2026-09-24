#!/usr/bin/env Rscript
# Step 6.3b — is the surface with self-collected imagery any better?
#   2_SC_validation_comparison.png
#     one panel, two arrows per subset: agreement with the IDEAMaps crowd labels
#     before and after adding self-collected imagery, for the binary and the
#     three-class reading. Arrow direction is the answer; colour is the measure.
#
# The question is a yes/no, so the figure is built to be read as one. Everything
# else — precision, recall, kappa, the confusion matrices — stays in
# table_6_3_validation_comparison.csv and 2_sc_validation_detail.csv.
#
# Rows are ordered so the argument reads top to bottom: citywide nothing
# happens, then the cells field collection actually reached, then the two routes
# a changed cell can take. The last two rows point opposite ways, and that is
# the finding.
#
# Hue carries direction; opacity carries how much weight the row can bear.
# Sample sizes here run from 2,286 down to 14, so the largest effect in the
# figure sits on the thinnest evidence — the faded arrow says so without a
# footnote.
#
# Inputs (6_selfcollected/3_indicator/, from 2_sc_validation.py):
#   2_sc_validation_detail.csv

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "3_indicator")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "3_indicator")

DETAIL_CSV <- file.path(DATA_DIR, "2_sc_validation_detail.csv")
OUT_PATH <- file.path(FIG_DIR, "2_SC_validation_comparison.png")

BEFORE <- "#BDB3A8"
# Colour is the measure, not the direction — an arrow already carries direction.
BINARY_COL <- "#6B4226"
THREE_COL <- "#496142"
MEASURES <- c("Binary", "Three-class")

# Opacity = how much weight a row can bear. Deliberately not row order: the
# subsets run 2,286 / 133 / 14 / 100, so the eye would otherwise give the
# 14-cell row the same standing as the 2,286-cell one.
STRENGTH_LEVELS <- c("1,000+ cells", "100–999 cells", "under 100 cells")
STRENGTH_ALPHA <- c("1,000+ cells" = 1.0, "100–999 cells" = 0.62, "under 100 cells" = 0.34)

if (!file.exists(DETAIL_CSV)) {
  stop("Missing ", DETAIL_CSV, " — run 6_selfcollected/3_indicator/2_sc_validation.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

detail <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)
n_of <- function(s) detail$n[detail$subset == s & detail$arm == "GSVI"][1]

SUBSETS <- c("All validated cells", "Cells holding SC imagery",
             "Changed, received imagery", "Changed through the spatial fill")
SHORT <- c(
  "All validated cells" = "Every validated cell",
  "Cells holding SC imagery" = "Cells field collection reached",
  "Changed, received imagery" = "Changed cells — with imagery",
  "Changed through the spatial fill" = "Changed cells — interpolated only"
)
row_label <- function(x) sprintf("%s\n(n = %s)", SHORT[[x]], comma(n_of(x)))
LEVELS <- rev(vapply(SUBSETS, row_label, character(1)))

arrows <- detail |>
  filter(subset %in% SUBSETS) |>
  select(subset, arm, Binary = accuracy, `Three-class` = severity_accuracy) |>
  pivot_longer(c(Binary, `Three-class`), names_to = "measure", values_to = "value") |>
  pivot_wider(names_from = arm, values_from = value) |>
  mutate(
    before = 100 * GSVI,
    after = 100 * `GSVI + SC`,
    delta = after - before,
    measure = factor(measure, levels = MEASURES),
    label = factor(vapply(subset, row_label, character(1)), levels = LEVELS),
    n_cells = vapply(subset, n_of, numeric(1)),
    strength = factor(
      case_when(n_cells >= 1000 ~ STRENGTH_LEVELS[1],
                n_cells >= 100 ~ STRENGTH_LEVELS[2],
                TRUE ~ STRENGTH_LEVELS[3]),
      levels = STRENGTH_LEVELS
    ),
    # Two arrows share a row, so nudge them apart.
    y = as.numeric(label) + if_else(measure == "Binary", 0.17, -0.17)
  )

fig <- ggplot(arrows) +
  geom_segment(aes(x = before, xend = after, y = y, yend = y,
                   colour = measure, alpha = strength),
               linewidth = 1.4,
               arrow = arrow(length = unit(0.2, "cm"), type = "closed")) +
  geom_point(aes(x = before, y = y, alpha = strength), colour = BEFORE, size = 3,
             show.legend = FALSE) +
  geom_point(aes(x = before, y = y), colour = "white", size = 1.3) +
  geom_text(aes(x = pmin(before, after) - 2.5, y = y, label = sprintf("%.0f", before),
                alpha = strength),
            hjust = 1, size = 2.8, colour = "grey45", show.legend = FALSE) +
  geom_text(aes(x = pmax(before, after) + 2.5, y = y,
                label = sprintf("%.0f  (%+.0f pp)", after, delta),
                colour = measure, alpha = strength),
            hjust = 0, size = 2.8, fontface = "bold", show.legend = FALSE) +
  scale_colour_manual(name = NULL, values = setNames(c(BINARY_COL, THREE_COL), MEASURES),
                      labels = c("Binary agreement (waste / no waste)",
                                 "Three-class agreement (Low / Medium / High)")) +
  scale_alpha_manual(name = "Cells behind the row", values = STRENGTH_ALPHA, drop = FALSE) +
  guides(
    colour = guide_legend(order = 1, override.aes = list(alpha = 1)),
    alpha = guide_legend(order = 2, override.aes = list(colour = "#4D2D18", linewidth = 1.4))
  ) +
  scale_x_continuous(limits = c(-16, 126), breaks = seq(0, 100, 25),
                     labels = label_percent(scale = 1)) +
  scale_y_continuous(breaks = seq_along(LEVELS), labels = LEVELS,
                     limits = c(0.4, length(LEVELS) + 0.6), expand = expansion(0)) +
  labs(
    title = "Does self-collected imagery make the 100 m indicator more accurate?",
    subtitle = paste0(
      "Agreement with the IDEAMaps crowd validation | grey dot = GSVI, arrowhead = GSVI + SC | faded = fewer cells behind the row\n",
      "Only where field collection actually reached a cell does the indicator get better — and the largest effect rests on the fewest cells."
    ),
    x = "Agreement with the crowd labels", y = NULL,
    caption = paste0(
      "2,286 crowd-validated 100 m cells. A changed cell is one whose published class differs between the\n",
      "arms; it either received an image or moved through the spatial fill.\n",
      "Changed cells with imagery behind them: three-class agreement 0% → 86%, McNemar p = 0.039.\n",
      "Changed cells moved by interpolation alone: 52% → 20%, p = 0.864.\n",
      "Opacity tracks sample size, not row order: the 14-cell row carries the biggest arrow and the least\n",
      "weight, and its κ is undefined because its crowd labels are constant. This concerns a 1% increase in\n",
      "imagery — directional evidence, not a powered test. Precision, recall, κ and the confusion matrices\n",
      "are in table_6_3_validation_comparison.csv."
    )
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 13.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 9, colour = CHAPTER_SUBTITLE_COLOUR,
                                 lineheight = 1.25, margin = margin(b = 10)),
    plot.caption = element_text(size = 7.8, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                lineheight = 1.3, margin = margin(t = 10)),
    axis.title.x = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR, margin = margin(t = 6)),
    axis.text.y = element_text(size = 9, colour = CHAPTER_AXIS_COLOUR, lineheight = 0.95, hjust = 0),
    axis.text.x = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank(),
    panel.grid.major.y = element_blank(),
    legend.position = "bottom",
    legend.box = "vertical",
    legend.spacing.y = unit(0.02, "cm"),
    legend.title = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
    legend.text = element_text(size = 8.6)
  )

ggsave(OUT_PATH, fig, width = 10, height = 6.6, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

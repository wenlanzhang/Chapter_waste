#!/usr/bin/env Rscript
# Step 6.3b — is the surface with self-collected imagery any better?
#   2_SC_validation_comparison.png
#     (a) agreement with the IDEAMaps crowd labels, by subset and arm
#     (b) the decisive split: among the cells that changed class, those that
#         received imagery against those that moved through the spatial fill
#     (c) McNemar on the same split — which arm the crowd sides with
#
# 6.3 showed the surface moves. This figure says which direction it moved in,
# and the answer depends entirely on whether the movement had evidence behind it.
#
# Inputs (6_selfcollected/3_indicator/, from 2_sc_validation.py):
#   2_sc_validation_detail.csv
#   thesis_table/table_6_3_validation_comparison.csv

suppressPackageStartupMessages({
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
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "3_indicator")

DETAIL_CSV <- file.path(DATA_DIR, "2_sc_validation_detail.csv")
OUT_PATH <- file.path(FIG_DIR, "2_SC_validation_comparison.png")

ARM_COLOURS <- c("GSVI" = "#BDB3A8", "GSVI + SC" = "#6B4226")
ARM_LEVELS <- c("GSVI", "GSVI + SC")
BETTER <- "#6B4226"
WORSE <- "#496142"

if (!file.exists(DETAIL_CSV)) {
  stop("Missing ", DETAIL_CSV, " — run 6_selfcollected/3_indicator/2_sc_validation.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

detail <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE) |>
  mutate(arm = factor(arm, levels = ARM_LEVELS))

n_of <- function(s) detail$n[detail$subset == s & detail$arm == "GSVI"][1]

SUBSETS <- c("All validated cells", "Cells holding SC imagery",
             "Changed, received imagery", "Changed through the spatial fill")
SHORT <- c(
  "All validated cells" = "All validated",
  "Cells holding SC imagery" = "Holds SC imagery",
  "Changed, received imagery" = "Changed:\nwith imagery",
  "Changed through the spatial fill" = "Changed:\nby spatial fill"
)
subset_label <- function(s) {
  vapply(s, function(x) sprintf("%s\n(n = %s)", SHORT[[x]], comma(n_of(x))), character(1))
}

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      legend.position = "bottom"
    )
}

# --- (a) binary + 3-class accuracy by subset ---------------------------------
acc <- detail |>
  filter(subset %in% SUBSETS) |>
  select(subset, arm, Binary = accuracy, `3-class` = severity_accuracy) |>
  pivot_longer(c(Binary, `3-class`), names_to = "measure", values_to = "value") |>
  mutate(
    subset = factor(subset_label(subset), levels = sapply(SUBSETS, subset_label)),
    measure = factor(measure, levels = c("Binary", "3-class"))
  )

p_acc <- ggplot(acc, aes(subset, 100 * value, fill = arm)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.62) +
  geom_text(aes(label = sprintf("%.0f", 100 * value)),
            position = position_dodge(width = 0.72), vjust = -0.45,
            size = 2.6, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  facet_wrap(~measure, ncol = 1, scales = "free_y") +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, 112), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(a) Agreement with the crowd labels",
    subtitle = "Accuracy against IDEAMaps validation clicks, by subset",
    x = NULL, y = "Agreement (%)"
  ) +
  base_theme() +
  theme(
    strip.text = element_text(face = "bold", size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    axis.text.x = element_text(size = 7.8, lineheight = 0.9)
  )

# --- (b) the decisive split, as a change in agreement ------------------------
split <- detail |>
  filter(subset %in% c("Changed, received imagery", "Changed through the spatial fill")) |>
  select(subset, arm, Binary = accuracy, `3-class` = severity_accuracy) |>
  pivot_longer(c(Binary, `3-class`), names_to = "measure", values_to = "value") |>
  pivot_wider(names_from = arm, values_from = value) |>
  mutate(
    delta = 100 * (`GSVI + SC` - GSVI),
    route = if_else(grepl("received", subset), "Received imagery", "Moved through the spatial fill"),
    route = factor(route, levels = c("Received imagery", "Moved through the spatial fill")),
    measure = factor(measure, levels = c("Binary", "3-class")),
    direction = if_else(delta >= 0, "Agreement improves", "Agreement worsens")
  )

p_split <- ggplot(split, aes(measure, delta, fill = direction)) +
  geom_hline(yintercept = 0, colour = "grey45", linewidth = 0.4) +
  geom_col(width = 0.55) +
  geom_text(aes(label = sprintf("%+.0f pp", delta),
                vjust = if_else(delta >= 0, -0.45, 1.35)),
            size = 2.9, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  facet_wrap(~route, nrow = 1) +
  scale_fill_manual(name = NULL, values = c("Agreement improves" = BETTER,
                                            "Agreement worsens" = WORSE)) +
  scale_y_continuous(limits = c(min(split$delta) * 1.35, max(split$delta) * 1.25)) +
  labs(
    title = "(b) Among the cells that changed class, did the change help?",
    subtitle = sprintf(
      "%s cells changed with imagery behind them, %s changed through interpolation alone",
      comma(n_of("Changed, received imagery")),
      comma(n_of("Changed through the spatial fill"))
    ),
    x = NULL, y = "Change in agreement (pp)"
  ) +
  base_theme() +
  theme(strip.text = element_text(face = "bold", size = 9, colour = CHAPTER_AXIS_COLOUR))

# --- (c) recall vs precision, the mechanism ----------------------------------
mech <- detail |>
  filter(subset %in% c("Changed, received imagery", "Changed through the spatial fill")) |>
  select(subset, arm, Precision = precision, Recall = recall) |>
  pivot_longer(c(Precision, Recall), names_to = "measure", values_to = "value") |>
  mutate(
    route = if_else(grepl("received", subset), "Received imagery", "Moved through the spatial fill"),
    route = factor(route, levels = c("Received imagery", "Moved through the spatial fill")),
    measure = factor(measure, levels = c("Precision", "Recall"))
  )

p_mech <- ggplot(mech, aes(measure, 100 * value, fill = arm)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.58) +
  geom_text(aes(label = sprintf("%.0f", 100 * value)),
            position = position_dodge(width = 0.7), vjust = -0.45,
            size = 2.7, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  facet_wrap(~route, nrow = 1) +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, 118), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(c) Why — the interpolated cells are over-called",
    subtitle = "Recall rises to 100% in both routes, but only the imagery route keeps its precision",
    x = NULL, y = "Binary metric (%)"
  ) +
  base_theme() +
  theme(strip.text = element_text(face = "bold", size = 9, colour = CHAPTER_AXIS_COLOUR))

fig <- (p_acc | (p_split / p_mech)) +
  plot_layout(widths = c(1, 1.25)) +
  plot_annotation(
    title = "Does self-collected imagery make the 100 m indicator more accurate?",
    subtitle = sprintf(
      "Both arms scored against %s IDEAMaps crowd-validated cells | %s of them hold self-collected imagery, %s changed published class",
      comma(n_of("All validated cells")), comma(n_of("Cells holding SC imagery")),
      comma(n_of("Changed, received imagery") + n_of("Changed through the spatial fill"))
    ),
    caption = paste0(
      "Where field collection reached a validated cell the change is almost always right (3-class agreement 0% → 86%, McNemar p = 0.039). ",
      "Where the class moved through interpolation alone it is not (3-class 52% → 20%, p = 0.864).\n",
      "Citywide the two arms are indistinguishable (binary 73.2% → 73.4%), because the cells with evidence behind them are too few to move the total.\n",
      "Subset sizes are small: this is directional evidence about a 1% increase in imagery, not a powered test of field collection in general."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 13.5, height = 7, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

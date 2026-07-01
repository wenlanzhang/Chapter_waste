#!/usr/bin/env Rscript
# Mitigation validation — binary metrics: GSVI vs G+Self (Nairobi grid)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(patchwork)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
GRID_DIR <- file.path(DATA_ROOT, "3_100m")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")
TABLE_DIR <- file.path(GRID_DIR, "thesis_table")

COMPARISON_CSV <- file.path(TABLE_DIR, "Nairobi_validation_mitigation_comparison.csv")
SUMMARY_CSV <- file.path(TABLE_DIR, "Nairobi_validation_mitigation_summary.csv")

GSVI_COLOUR <- "#C9A27F"
GSC_COLOUR <- "#6B4226"
ARM_LEVELS <- c("GSVI", "G+Self")
ARM_COLOURS <- c("GSVI" = GSVI_COLOUR, "G+Self" = GSC_COLOUR)
ARM_LABELS <- c(
  "GSVI" = "GSVI (Google only)",
  "G+Self" = "G+Self (Google + self-collected)"
)
METRIC_KEYS <- c(
  "binary_accuracy",
  "binary_precision",
  "binary_recall",
  "binary_f1"
)
METRIC_LEVELS <- c("Accuracy", "Precision", "Recall", "F1")
DODGE_WIDTH <- 0.72

prepare_panel_data <- function(df) {
  df |>
    mutate(
      arm = case_when(
        grepl("^GSVI", predictor) ~ "GSVI",
        grepl("^G\\+Self", predictor) ~ "G+Self",
        TRUE ~ predictor
      ),
      arm = factor(arm, levels = ARM_LEVELS)
    )
}

build_combined_panel <- function(df, panel_tag, subset_label) {
  n_cells <- unique(df$n_cells)
  n_label <- if (length(n_cells) == 1) comma(n_cells) else paste(comma(n_cells), collapse = ", ")

  plot_df <- prepare_panel_data(df) |>
    select(arm, all_of(METRIC_KEYS)) |>
    pivot_longer(
      cols = all_of(METRIC_KEYS),
      names_to = "metric_key",
      values_to = "score"
    ) |>
    mutate(
      score_pct = score * 100,
      metric = factor(metric_key, levels = METRIC_KEYS, labels = METRIC_LEVELS)
    )

  ggplot(plot_df, aes(x = metric, y = score_pct, fill = arm)) +
    geom_col(
      position = position_dodge(width = DODGE_WIDTH),
      width = 0.62,
      colour = "white",
      linewidth = 0.5
    ) +
    geom_text(
      aes(label = sprintf("%.1f%%", score_pct)),
      position = position_dodge(width = DODGE_WIDTH),
      vjust = -0.4,
      size = 3.0,
      fontface = "bold",
      colour = "#3d2b1f",
      show.legend = FALSE
    ) +
    scale_fill_manual(
      values = ARM_COLOURS,
      breaks = ARM_LEVELS,
      labels = ARM_LABELS
    ) +
    scale_y_continuous(
      limits = c(0, 100),
      breaks = seq(0, 100, 25),
      expand = expansion(mult = c(0, 0.12))
    ) +
    labs(
      title = sprintf("%s %s (n = %s)", panel_tag, subset_label, n_label),
      x = NULL,
      y = "Score (%)",
      fill = "Pipeline arm"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 10.5, face = "bold", hjust = 0, colour = "#2f2f2f"),
      axis.text.x = element_text(size = 9.5, colour = "#4D2D18"),
      axis.text.y = element_text(size = 8.5),
      axis.title.y = element_text(size = 9.5, colour = "#4D2D18"),
      panel.grid.major.x = element_blank(),
      legend.position = "none",
      plot.margin = margin(8, 12, 6, 8)
    )
}

message("Reading tables...")
comparison <- read.csv(COMPARISON_CSV, stringsAsFactors = FALSE)
summary_note <- read.csv(SUMMARY_CSV, stringsAsFactors = FALSE)

all_cells <- comparison |> filter(subset == "All validated cells")
self_cells <- comparison |> filter(subset == "Self-collected SVI overlap")

n_changed_note <- summary_note$Note[summary_note$Topic == "Cells where G+Self differs from GSVI"]
if (length(n_changed_note) == 0) {
  n_changed_note <- summary_note$Note[
    summary_note$Topic == "Cells where G+Self differs from submitted GSVI"
  ]
}

p_all <- build_combined_panel(all_cells, "(A)", "All validated cells")
p_self <- build_combined_panel(self_cells, "(B)", "Self-collected overlap")

panel <- p_all / p_self +
  plot_layout(guides = "collect") &
  theme(
    legend.position = "bottom",
    legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
    legend.text = element_text(size = 9, colour = "#4D2D18"),
    legend.margin = margin(t = 4)
  )

panel <- panel +
  plot_annotation(
    title = "Crowd Validation: Binary Waste Classification (GSVI vs G+Self)",
    subtitle = paste0(
      "Nairobi 100 m grid; IDEAMaps pipeline with fixed submission Jenks break points. ",
      "Each pair of bars compares the same metric under two pipeline arms (fill colour)."
    ),
    caption = paste0(
      "Binary task: waste present vs absent. Light tan = Google Street View only; ",
      "dark brown = Google plus Faith/ZWL self-collected imagery. ",
      n_changed_note, "."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8))
    )
  )

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
out_path <- file.path(FIG_DIR, "Validation_mitigation_accuracy.png")
ggsave(out_path, plot = panel, width = 9, height = 9.5, dpi = 600, bg = "white")
message("Wrote ", out_path)
message("Done.")

#!/usr/bin/env Rscript
# IDEAMaps validation — confusion matrices (3-class severity + binary waste)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
GRID_DIR <- file.path(DATA_ROOT, "3_100m")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")
TABLE_DIR <- file.path(GRID_DIR, "thesis_table")

SEVERITY_CSV <- file.path(TABLE_DIR, "Nairobi_validation_confusion_severity.csv")
BINARY_CSV <- file.path(TABLE_DIR, "Nairobi_validation_confusion_binary.csv")
SUMMARY_CSV <- file.path(TABLE_DIR, "Nairobi_validation_summary.csv")

SEVERITY_LEVELS <- c("0", "1", "2")
SEVERITY_LABELS <- c(
  "0" = "No waste (0)",
  "1" = "Medium (1)",
  "2" = "High (2)"
)
BINARY_LEVELS <- c("0", "1")
BINARY_LABELS <- c("0" = "No waste", "1" = "Waste present")

CHOCOLATE_PALETTE <- c("#fafafa", "#E5C8A9", "#C9A27F", "#8B5E3C", "#6B4226")
FILL_LABEL <- "Count"

read_confusion <- function(path, levels, labels) {
  df <- read.csv(path, stringsAsFactors = FALSE)
  label_vec <- labels[levels]
  df |>
    mutate(
      truth = factor(as.character(truth), levels = levels, labels = label_vec),
      pred = factor(as.character(pred), levels = levels, labels = label_vec),
      cell_label = sprintf(
        "%s\n(%.1f%% row)",
        format(n, big.mark = ",", trim = TRUE),
        pct_of_truth_row
      )
    )
}

build_confusion_panel <- function(cm, title, show_legend = FALSE) {
  truth_levels <- levels(cm$truth)
  pred_levels <- levels(cm$pred)

  p <- ggplot(cm, aes(x = pred, y = truth, fill = n)) +
    geom_tile(colour = "white", linewidth = 1.0) +
    geom_text(aes(label = cell_label), size = 3.5, fontface = "bold", colour = "#2f2f2f") +
    scale_x_discrete(limits = pred_levels) +
    scale_y_discrete(limits = truth_levels) +
    scale_fill_gradientn(
      colours = CHOCOLATE_PALETTE,
      name = FILL_LABEL,
      trans = "sqrt"
    ) +
    labs(
      title = title,
      x = "Model prediction",
      y = "Validation (ground truth)"
    ) +
    map_theme() +
    theme(
      plot.subtitle = element_blank(),
      panel.grid = element_blank(),
      axis.text.x = element_text(size = 9),
      axis.text.y = element_text(size = 9),
      legend.position = if (show_legend) "right" else "none"
    )

  p
}

format_summary_caption <- function(summary_path) {
  s <- read.csv(summary_path, stringsAsFactors = FALSE)
  get_val <- function(metric) {
    row <- s[s$Metric == metric, , drop = FALSE]
    if (nrow(row) == 0) return("NA")
    row$Value[1]
  }
  paste0(
    "Crowd validation vs model, Nairobi; max severity per 100 m cell; ",
    get_val("Validated grid cells"), " cells (",
    get_val("Cells with 2+ validation clicks"), " multi-click).\n",
    "3-class accuracy: ", get_val("3-class accuracy"),
    " | Binary: ", get_val("Binary accuracy (waste present)"),
    " | Precision: ", get_val("Binary precision"),
    " | Recall: ", get_val("Binary recall"),
    " | F1: ", get_val("Binary F1")
  )
}

annotation_theme <- theme(
  plot.title = element_text(face = "bold", size = 15, hjust = 0.5, colour = "#2f2f2f"),
  plot.subtitle = element_blank(),
  plot.caption = element_text(size = 8.5, colour = "grey45", hjust = 0.5, margin = margin(t = 8))
)

message("Reading confusion tables...")
severity_cm <- read_confusion(SEVERITY_CSV, SEVERITY_LEVELS, SEVERITY_LABELS)
binary_cm <- read_confusion(BINARY_CSV, BINARY_LEVELS, BINARY_LABELS)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

panel_severity <- build_confusion_panel(
  severity_cm,
  title = "(A) Severity confusion matrix",
  show_legend = FALSE
)

panel_binary <- build_confusion_panel(
  binary_cm,
  title = "(B) Binary waste confusion matrix",
  show_legend = TRUE
)

combined <- panel_severity + panel_binary +
  plot_layout(widths = c(1.15, 1), guides = "collect") +
  plot_annotation(
    title = "IDEAMaps Model Validation on 100 m Grid Cells",
    caption = format_summary_caption(SUMMARY_CSV),
    theme = annotation_theme
  ) &
  theme(legend.position = "right")

out_path <- file.path(FIG_DIR, "Validation_confusion_matrix.png")
ggsave(out_path, combined, width = 14, height = 6.4, dpi = 600, bg = "white")
message("Wrote ", out_path)
message("Done.")

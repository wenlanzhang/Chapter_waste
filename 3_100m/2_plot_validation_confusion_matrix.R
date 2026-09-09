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
VALIDATION_TABLE_DIR <- file.path(GRID_DIR, "validation")

SEVERITY_CSV <- file.path(VALIDATION_TABLE_DIR, "Nairobi_validation_confusion_severity.csv")
BINARY_CSV <- file.path(VALIDATION_TABLE_DIR, "Nairobi_validation_confusion_binary.csv")
SUMMARY_CSV <- file.path(VALIDATION_TABLE_DIR, "Nairobi_validation_summary.csv")

SEVERITY_LEVELS <- c("0", "1", "2")
SEVERITY_LABELS <- c(
  "0" = "Low (0)",
  "1" = "Medium (1)",
  "2" = "High (2)"
)
BINARY_LEVELS <- c("0", "1")
BINARY_LABELS <- c("0" = "Low", "1" = "Waste present")

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
      ),
      text_colour = chocolate_label_colour(n, trans = "sqrt")
    )
}

get_confusion_n <- function(cm) {
  format(sum(cm$n), big.mark = ",", trim = TRUE)
}

format_title_with_n <- function(title, n_cells) {
  sprintf("%s (n = %s)", title, n_cells)
}

build_confusion_panel <- function(cm, title, show_legend = FALSE, caption = NULL) {
  truth_levels <- levels(cm$truth)
  pred_levels <- levels(cm$pred)

  p <- ggplot(cm, aes(x = pred, y = truth, fill = n)) +
    geom_tile(colour = "white", linewidth = 1.0) +
    geom_text(aes(label = cell_label, colour = text_colour), size = 3.5, fontface = "bold") +
    scale_colour_identity() +
    scale_x_discrete(limits = pred_levels) +
    scale_y_discrete(limits = truth_levels) +
    scale_fill_gradientn(
      colours = CHOCOLATE_PALETTE,
      name = FILL_LABEL,
      trans = "sqrt"
    ) +
    labs(
      title = title,
      caption = caption,
      x = "Indicator category",
      y = "Crowd-assessed category"
    ) +
    map_theme() +
    theme(
      plot.subtitle = element_blank(),
      panel.grid = element_blank(),
      axis.text.x = element_text(size = 9),
      axis.text.y = element_text(size = 9, angle = 90, hjust = 1, vjust = 0.5),
      legend.position = if (show_legend) "right" else "none"
    )

  p
}

save_confusion_figure <- function(plot_obj, filename, width, height) {
  out_path <- file.path(FIG_DIR, filename)
  ggsave(out_path, plot_obj, width = width, height = height, dpi = 600, bg = "white")
  message("Wrote ", out_path)
}

format_summary_caption <- function(summary_path, include_3class = TRUE) {
  s <- read.csv(summary_path, stringsAsFactors = FALSE)
  get_val <- function(metric) {
    row <- s[s$Metric == metric, , drop = FALSE]
    if (nrow(row) == 0) return("NA")
    row$Value[1]
  }
  metrics_line <- if (include_3class) {
    paste0(
      "3-class accuracy: ", get_val("3-class accuracy"),
      " | Binary: ", get_val("Binary accuracy (waste present)"),
      " | Precision: ", get_val("Binary precision"),
      " | Recall: ", get_val("Binary recall"),
      " | F1: ", get_val("Binary F1")
    )
  } else {
    paste0(
      "Binary: ", get_val("Binary accuracy (waste present)"),
      " | Precision: ", get_val("Binary precision"),
      " | Recall: ", get_val("Binary recall"),
      " | F1: ", get_val("Binary F1")
    )
  }
  paste0(
    "Crowd validation vs model, Nairobi; max severity per 100 m cell; ",
    get_val("Validated grid cells"), " cells (",
    get_val("Cells with 2+ validation clicks"), " multi-click).\n",
    metrics_line
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
n_cells <- get_confusion_n(severity_cm)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

summary_caption <- format_summary_caption(SUMMARY_CSV)

panel_severity <- build_confusion_panel(
  severity_cm,
  title = format_title_with_n("(A) Severity confusion matrix", n_cells),
  show_legend = FALSE
)

panel_binary <- build_confusion_panel(
  binary_cm,
  title = format_title_with_n("(B) Binary waste confusion matrix", n_cells),
  show_legend = TRUE
)

severity_standalone <- build_confusion_panel(
  severity_cm,
  title = format_title_with_n("Severity confusion matrix", n_cells),
  show_legend = TRUE,
  caption = summary_caption
) +
  theme(
    plot.caption = element_text(size = 8.5, colour = "grey45", hjust = 0.5, margin = margin(t = 8))
  )

binary_caption <- format_summary_caption(SUMMARY_CSV, include_3class = FALSE)

binary_standalone <- build_confusion_panel(
  binary_cm,
  title = format_title_with_n("Binary waste indicator validation", n_cells),
  show_legend = FALSE,
  caption = binary_caption
) +
  theme(
    plot.caption = element_text(size = 8.5, colour = "grey45", hjust = 0.5, margin = margin(t = 8))
  )

save_confusion_figure(
  severity_standalone,
  "Validation_confusion_matrix_severity.png",
  width = 7.5,
  height = 6.8
)
save_confusion_figure(
  binary_standalone,
  "Validation_confusion_matrix_binary.png",
  width = 6.2,
  height = 6.8
)

combined <- panel_severity + panel_binary +
  plot_layout(widths = c(1.15, 1), guides = "collect") +
  plot_annotation(
    title = format_title_with_n(
      "IDEAMaps Model Validation on 100 m Grid Cells",
      n_cells
    ),
    caption = summary_caption,
    theme = annotation_theme
  ) &
  theme(legend.position = "right")

save_confusion_figure(
  combined,
  "Validation_confusion_matrix.png",
  width = 14,
  height = 6.4
)
message("Done.")

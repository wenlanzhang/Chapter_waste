#!/usr/bin/env Rscript
# Step 3 figure 1 — independent GSVI held-out, headline scenario:
#   1_Heldout_yolo_qwen_panel.png  both stages — metric bars + two confusion matrices
#   1_Heldout_qwen_only_panel.png  the YOLO + Qwen cascade alone, for presenting the
#                                  final result without the baseline beside it
# Left of each: image-level Accuracy / Precision / Recall / F1 with Wilson 95% CI.
# Input: thesis_table/table_2_yolo_qwen_heldout_detail.csv (1_heldout_metrics.py)

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
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))

STEP3_DIR <- file.path(chapter_data_root, "3_waste_identification")
THESIS_DIR <- file.path(STEP3_DIR, "thesis_table")
DETAIL_CSV <- file.path(THESIS_DIR, "table_2_yolo_qwen_heldout_detail.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_waste_identification")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

CLASS_LEVELS <- c("Background", "Waste")

if (!file.exists(DETAIL_CSV)) {
  stop("Missing ", DETAIL_CSV, " — run 3_waste_identification/1_heldout_metrics.py first")
}

# --- Combined panel: metric bars (+ Wilson CI) | YOLO CM | YOLO→Qwen CM ---
STAGE_COLOURS <- c(
  "YOLO Only" = "#C9A27F",
  "YOLO + Qwen" = "#5F6F5A"
)
QWEN_CM_PALETTE <- c("#fafafa", "#D5D8CF", "#A8B0A0", "#7A8774", "#5F6F5A")

stage_display <- function(stage) {
  if (grepl("Qwen", stage, ignore.case = TRUE)) "YOLO + Qwen" else "YOLO Only"
}

parse_pct <- function(x) {
  as.numeric(gsub("%", "", x, fixed = TRUE)) / 100
}

parse_ci_pair <- function(x) {
  # "74.2–85.7%" or "74.2-85.7%"
  s <- gsub("%", "", x, fixed = TRUE)
  s <- gsub("\u2013", "-", s, fixed = TRUE)
  parts <- strsplit(s, "-", fixed = TRUE)
  vapply(parts, function(p) {
    if (length(p) < 2) return(c(NA_real_, NA_real_))
    c(as.numeric(p[[1]]) / 100, as.numeric(p[[2]]) / 100)
  }, numeric(2))
}

# Prefer numeric detail CIs; fall back to parsing the display CI table.
if (file.exists(DETAIL_CSV)) {
  d <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)
  bar_df <- tidyr::pivot_longer(
    d,
    cols = c(accuracy_pct, precision_pct, recall_pct, f1_pct),
    names_to = "metric_key",
    values_to = "score_pct"
  ) |>
    mutate(
      metric = factor(
        metric_key,
        levels = c("accuracy_pct", "precision_pct", "recall_pct", "f1_pct"),
        labels = c("Accuracy", "Precision", "Recall", "F1 Score")
      ),
      model = factor(vapply(stage, stage_display, character(1)), levels = names(STAGE_COLOURS)),
      score = score_pct / 100,
      ci_low = case_when(
        metric_key == "accuracy_pct" ~ accuracy_ci95_low,
        metric_key == "precision_pct" ~ precision_ci95_low,
        metric_key == "recall_pct" ~ recall_ci95_low,
        TRUE ~ f1_ci95_low
      ),
      ci_high = case_when(
        metric_key == "accuracy_pct" ~ accuracy_ci95_high,
        metric_key == "precision_pct" ~ precision_ci95_high,
        metric_key == "recall_pct" ~ recall_ci95_high,
        TRUE ~ f1_ci95_high
      )
    )
} else if (file.exists(CI_CSV)) {
  ci_raw <- read.csv(CI_CSV, check.names = FALSE, stringsAsFactors = FALSE)
  # Columns: stage, Accuracy, 95% CI, Precision, 95% CI, ...
  stage_col <- names(ci_raw)[1]
  metrics <- c("Accuracy", "Precision", "Recall", "F1")
  rows <- list()
  for (i in seq_len(nrow(ci_raw))) {
    model <- stage_display(ci_raw[[stage_col]][i])
    # After first col: Acc, CI, Prec, CI, Rec, CI, F1, CI
    for (j in seq_along(metrics)) {
      val_col <- 1 + (j - 1) * 2 + 1
      ci_col <- val_col + 1
      bounds <- parse_ci_pair(ci_raw[[ci_col]][i])
      rows[[length(rows) + 1]] <- data.frame(
        model = model,
        metric = if (metrics[j] == "F1") "F1 Score" else metrics[j],
        score = parse_pct(ci_raw[[val_col]][i]),
        ci_low = bounds[1],
        ci_high = bounds[2],
        stringsAsFactors = FALSE
      )
    }
  }
  bar_df <- dplyr::bind_rows(rows) |>
    mutate(
      model = factor(model, levels = names(STAGE_COLOURS)),
      metric = factor(metric, levels = c("Accuracy", "Precision", "Recall", "F1 Score"))
    )
} else {
  stop("Need ", DETAIL_CSV, " or ", CI_CSV)
}

p_bars <- ggplot(bar_df, aes(x = metric, y = score, fill = model)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.68, colour = NA) +
  geom_errorbar(
    aes(ymin = ci_low, ymax = ci_high),
    position = position_dodge(width = 0.72),
    width = 0.18,
    linewidth = 0.45,
    colour = "#3a3a3a"
  ) +
  geom_text(
    aes(label = sprintf("%.2f", score), y = pmin(ci_high, 1) + 0.035),
    position = position_dodge(width = 0.72),
    size = 3.0,
    fontface = "bold",
    colour = "#2f2f2f"
  ) +
  scale_fill_manual(values = STAGE_COLOURS, name = NULL) +
  scale_y_continuous(
    limits = c(0, 1.12),
    breaks = seq(0, 1, 0.2),
    expand = c(0, 0)
  ) +
  labs(x = NULL, y = "Score", title = NULL) +
  map_theme() +
  theme(
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "grey88", linewidth = 0.35, linetype = "dotted"),
    legend.position = "none",
    axis.text.x = element_text(size = 10, face = "bold", colour = "#2f2f2f"),
    axis.text.y = element_text(size = 9),
    axis.title.y = element_text(size = 11, face = "bold")
  )

build_cm_simple <- function(tp, fp, tn, fn, title, palette) {
  fill_max <- max(as.integer(c(tp, fp, tn, fn)), na.rm = TRUE)
  cm <- data.frame(
    truth = factor(c("Waste", "Waste", "Background", "Background"), levels = CLASS_LEVELS),
    pred = factor(c("Waste", "Background", "Waste", "Background"), levels = CLASS_LEVELS),
    n = c(as.integer(tp), as.integer(fn), as.integer(fp), as.integer(tn)),
    stringsAsFactors = FALSE
  ) |>
    mutate(
      text_colour = chocolate_label_colour(n, limits = c(0, fill_max), trans = "sqrt")
    )

  ggplot(cm, aes(x = pred, y = truth, fill = n)) +
    geom_tile(colour = "white", linewidth = 1.1) +
    geom_text(aes(label = n, colour = text_colour), size = 5.2, fontface = "bold") +
    scale_colour_identity() +
    scale_x_discrete(limits = CLASS_LEVELS) +
    scale_y_discrete(limits = rev(CLASS_LEVELS)) +
    scale_fill_gradientn(
      colours = palette,
      name = NULL,
      limits = c(0, fill_max),
      guide = "none"
    ) +
    labs(title = title, x = "Predicted", y = NULL) +
    map_theme() +
    theme(
      panel.grid = element_blank(),
      plot.title = element_text(size = 12, face = "bold", hjust = 0.5),
      axis.text.x = element_text(size = 10),
      # Category labels rotated 90° anti-clockwise (bottom → top)
      axis.text.y = element_text(size = 10, angle = 90, hjust = 0.5, vjust = 0.5),
      # Leave room for a shared rotated "True" label beside both CMs
      axis.title.y = element_blank(),
      axis.title.x = element_text(size = 11, face = "bold"),
      legend.position = "none",
      plot.margin = margin(4, 6, 4, 4)
    )
}

d_cm <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)
yolo_row <- d_cm[!grepl("Qwen", d_cm$stage, ignore.case = TRUE), ][1, ]
qwen_row <- d_cm[grepl("Qwen", d_cm$stage, ignore.case = TRUE), ][1, ]

p_cm_yolo <- build_cm_simple(
  yolo_row$tp, yolo_row$fp, yolo_row$tn, yolo_row$fn,
  "YOLO", CHOCOLATE_PALETTE
)
p_cm_qwen <- build_cm_simple(
  qwen_row$tp, qwen_row$fp, qwen_row$tn, qwen_row$fn,
  "YOLO + Qwen", QWEN_CM_PALETTE
)

# Legend centred above the two confusion matrices (not under the bars)
p_legend_row <- ggplot() +
  # Centred pair above the two CM panels (xlim 0–10 → mid ≈ 5)
  annotate("rect", xmin = 2.85, xmax = 3.15, ymin = 0.30, ymax = 0.70,
           fill = STAGE_COLOURS[["YOLO Only"]], colour = NA) +
  annotate("text", x = 3.28, y = 0.5, label = "YOLO Only",
           hjust = 0, vjust = 0.5, size = 3.8, colour = "#2f2f2f") +
  annotate("rect", xmin = 5.15, xmax = 5.45, ymin = 0.30, ymax = 0.70,
           fill = STAGE_COLOURS[["YOLO + Qwen"]], colour = NA) +
  annotate("text", x = 5.58, y = 0.5, label = "YOLO + Qwen",
           hjust = 0, vjust = 0.5, size = 3.8, colour = "#2f2f2f") +
  coord_cartesian(xlim = c(0, 10), ylim = c(0, 1), expand = FALSE, clip = "off") +
  theme_void() +
  theme(plot.margin = margin(0, 2, 0, 2))

# Shared "True" y-label rotated 90° anti-clockwise (reads bottom → top)
p_true_label <- ggplot() +
  annotate(
    "text",
    x = 0.5,
    y = 0.5,
    label = "True",
    angle = 90,
    hjust = 0.5,
    vjust = 0.5,
    size = 4.1,
    fontface = "bold",
    colour = CHAPTER_AXIS_COLOUR
  ) +
  coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE) +
  theme_void() +
  theme(plot.margin = margin(0, 0, 0, 0))

cm_pair <- p_true_label | p_cm_yolo | p_cm_qwen
cm_pair <- cm_pair + plot_layout(widths = c(0.08, 1, 1))

cm_block <- p_legend_row / cm_pair +
  plot_layout(heights = c(0.11, 1))

panel_fig <- (p_bars | cm_block) +
  plot_layout(widths = c(1.3, 2.15)) +
  plot_annotation(
    title = "Independent GSVI held-out — YOLO vs YOLO + Qwen",
    subtitle = paste0(
      sprintf(
        "Image-level binary metrics with Wilson binomial 95%% CI (n = %d). ",
        as.integer(yolo_row$tp + yolo_row$fp + yolo_row$tn + yolo_row$fn)
      ),
      "YOLO + Qwen keeps a YOLO positive only when Qwen2-VL also answers Yes; ",
      sub("^.*?: ", "", qwen_row$note)
    ),
    caption = "Left: Accuracy / Precision / Recall / F1. Right: confusion matrices (True × Predicted).",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 8.8, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 6)),
      plot.caption = element_text(size = 8, hjust = 0, colour = "#7A6A5C")
    )
  )

out_panel <- file.path(FIG_DIR, "1_Heldout_yolo_qwen_panel.png")
ggsave(out_panel, panel_fig, width = 12.8, height = 5.5, dpi = 600, bg = "white")
message("Wrote ", out_panel)

# --- cascade only: the same headline result without the YOLO baseline -------
qwen_bar_df <- bar_df |> filter(model == "YOLO + Qwen")

p_bars_qwen <- ggplot(qwen_bar_df, aes(x = metric, y = score)) +
  geom_col(width = 0.58, fill = STAGE_COLOURS[["YOLO + Qwen"]], colour = NA) +
  geom_errorbar(
    aes(ymin = ci_low, ymax = ci_high),
    width = 0.15, linewidth = 0.45, colour = "#3a3a3a"
  ) +
  geom_text(
    aes(label = sprintf("%.2f", score), y = pmin(ci_high, 1) + 0.035),
    size = 3.2, fontface = "bold", colour = "#2f2f2f"
  ) +
  scale_y_continuous(limits = c(0, 1.12), breaks = seq(0, 1, 0.2), expand = c(0, 0)) +
  labs(x = NULL, y = "Score", title = NULL) +
  map_theme() +
  theme(
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "grey88", linewidth = 0.35, linetype = "dotted"),
    legend.position = "none",
    axis.text.x = element_text(size = 10, face = "bold", colour = "#2f2f2f"),
    axis.text.y = element_text(size = 9),
    axis.title.y = element_text(size = 11, face = "bold")
  )

p_cm_qwen_solo <- build_cm_simple(
  qwen_row$tp, qwen_row$fp, qwen_row$tn, qwen_row$fn,
  "Confusion matrix", QWEN_CM_PALETTE
)

qwen_fig <- (p_bars_qwen | (p_true_label | p_cm_qwen_solo) + plot_layout(widths = c(0.08, 1))) +
  plot_layout(widths = c(1.25, 1)) +
  plot_annotation(
    title = "Independent GSVI held-out — YOLO + Qwen",
    subtitle = paste0(
      sprintf(
        "Image-level binary metrics with Wilson binomial 95%% CI (n = %d)\n",
        as.integer(qwen_row$tp + qwen_row$fp + qwen_row$tn + qwen_row$fn)
      ),
      "A YOLO positive is kept only when Qwen2-VL also answers Yes; ",
      # note reads "...: <run> (Yes=.., No=.. of N YOLO+). Source: <file>" —
      # keep the run and its vote counts, drop the trailing source path
      sub("\\. Source:.*$", "", sub("^.*?: ", "", qwen_row$note))
    ),
    caption = "Left: Accuracy / Precision / Recall / F1. Right: confusion matrix (True × Predicted).",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 8.8, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 6)),
      plot.caption = element_text(size = 8, hjust = 0, colour = "#7A6A5C")
    )
  )

out_qwen <- file.path(FIG_DIR, "1_Heldout_qwen_only_panel.png")
ggsave(out_qwen, qwen_fig, width = 9.2, height = 5.5, dpi = 600, bg = "white")
message("Wrote ", out_qwen)
message("Done.")

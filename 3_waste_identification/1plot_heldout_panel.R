#!/usr/bin/env Rscript
# Step 3 figure 1 — independent GSVI held-out, headline scenario:
#   1_Heldout_yolo_qwen_panel.png  both stages — metric bars + two confusion matrices
#   1_Heldout_yolo_qwen_panel_manuscript.png  the same panel without title / subtitle / caption
#   1_Heldout_qwen_only_panel.png  the YOLO + Qwen cascade alone, for presenting the
#                                  final result without the baseline beside it
# Left of each: image-level Accuracy / Precision / Recall / F1 with 95% percentile CIs
# from the class-stratified, paired panorama bootstrap in 1_heldout_metrics.py.
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

# --- Combined panel: metric bars (+ bootstrap CI) | YOLO CM | YOLO→Qwen CM ---
d <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)
is_pipe <- grepl("Qwen", d$stage, ignore.case = TRUE)
n_runs <- d$n_runs[is_pipe][1]
n_images <- d$n_images[1]
n_panoramas <- d$n_panoramas[1]
NUMBER_WORDS <- c("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
runs_word <- if (n_runs <= length(NUMBER_WORDS)) NUMBER_WORDS[n_runs] else as.character(n_runs)

YOLO_LABEL <- "YOLO11x"
PIPE_LABEL <- sprintf("YOLO11x\u2013Qwen2-VL (mean of %s runs)", runs_word)
PIPE_CM_TITLE <- sprintf("YOLO11x\u2013Qwen2-VL: mean of %s runs", runs_word)
STAGE_COLOURS <- setNames(c("#C9A27F", "#5F6F5A"), c(YOLO_LABEL, PIPE_LABEL))
QWEN_CM_PALETTE <- c("#fafafa", "#D5D8CF", "#A8B0A0", "#7A8774", "#5F6F5A")

METRIC_KEYS <- c("accuracy", "precision", "recall", "f1")
METRIC_LABELS <- c("Accuracy", "Precision", "Recall", "F1")

# Bar height = the unrounded estimate (for the cascade, the mean of the per-run
# metrics); error bar = the bootstrap percentile limits as written, not a
# symmetric +/- width.
bar_df <- dplyr::bind_rows(lapply(METRIC_KEYS, function(k) {
  data.frame(
    model = ifelse(grepl("Qwen", d$stage, ignore.case = TRUE), PIPE_LABEL, YOLO_LABEL),
    metric = METRIC_LABELS[match(k, METRIC_KEYS)],
    score = d[[k]],
    ci_low = d[[paste0(k, "_ci95_low")]],
    ci_high = d[[paste0(k, "_ci95_high")]],
    stringsAsFactors = FALSE
  )
})) |>
  mutate(
    model = factor(model, levels = names(STAGE_COLOURS)),
    metric = factor(metric, levels = METRIC_LABELS)
  )
stopifnot(all(bar_df$ci_low <= bar_df$score & bar_df$score <= bar_df$ci_high))

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
    aes(label = sprintf("%.1f", 100 * score), y = pmin(ci_high, 1) + 0.035),
    position = position_dodge(width = 0.72),
    size = 3.0,
    fontface = "bold",
    colour = "#2f2f2f"
  ) +
  scale_fill_manual(values = STAGE_COLOURS, name = NULL) +
  scale_y_continuous(
    limits = c(0, 1.12),
    breaks = seq(0, 1, 0.2),
    labels = function(x) 100 * x,
    expand = c(0, 0)
  ) +
  labs(x = NULL, y = "Score (%)", title = NULL, tag = "(a)") +
  map_theme() +
  theme(
    panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour = "grey88", linewidth = 0.35, linetype = "dotted"),
    legend.position = "none",
    axis.text.x = element_text(size = 10, face = "bold", colour = "#2f2f2f"),
    axis.text.y = element_text(size = 9),
    axis.title.y = element_text(size = 11, face = "bold"),
    plot.tag = element_text(size = 13, face = "bold", colour = "#2f2f2f")
  )

build_cm_simple <- function(tp, fp, tn, fn, title, palette) {
  # Counts can be fractional: the YOLO + Qwen matrix is the mean over Qwen replicates.
  fill_max <- max(c(tp, fp, tn, fn), na.rm = TRUE)
  cm <- data.frame(
    truth = factor(c("Waste", "Waste", "Background", "Background"), levels = CLASS_LEVELS),
    pred = factor(c("Waste", "Background", "Waste", "Background"), levels = CLASS_LEVELS),
    n = as.numeric(c(tp, fn, fp, tn)),
    stringsAsFactors = FALSE
  ) |>
    mutate(
      label = ifelse(abs(n - round(n)) < 1e-9, sprintf("%d", as.integer(round(n))), sprintf("%.1f", n)),
      text_colour = chocolate_label_colour(n, limits = c(0, fill_max), trans = "sqrt")
    )

  ggplot(cm, aes(x = pred, y = truth, fill = n)) +
    geom_tile(colour = "white", linewidth = 1.1) +
    geom_text(aes(label = label, colour = text_colour), size = 5.2, fontface = "bold") +
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
      plot.title = element_text(size = 11, face = "bold", hjust = 0.5),
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
  YOLO_LABEL, CHOCOLATE_PALETTE
)
p_cm_qwen <- build_cm_simple(
  qwen_row$tp, qwen_row$fp, qwen_row$tn, qwen_row$fn,
  PIPE_CM_TITLE, QWEN_CM_PALETTE
)

# Legend centred above the two confusion matrices (not under the bars)
p_legend_row <- ggplot() +
  # Centred pair above the two CM panels (xlim 0–10 → mid ≈ 5)
  annotate("rect", xmin = 1.55, xmax = 1.80, ymin = 0.30, ymax = 0.70,
           fill = STAGE_COLOURS[[YOLO_LABEL]], colour = NA) +
  annotate("text", x = 1.92, y = 0.5, label = YOLO_LABEL,
           hjust = 0, vjust = 0.5, size = 3.8, colour = "#2f2f2f") +
  annotate("rect", xmin = 3.65, xmax = 3.90, ymin = 0.30, ymax = 0.70,
           fill = STAGE_COLOURS[[PIPE_LABEL]], colour = NA) +
  annotate("text", x = 4.02, y = 0.5, label = PIPE_LABEL,
           hjust = 0, vjust = 0.5, size = 3.8, colour = "#2f2f2f") +
  coord_cartesian(xlim = c(0, 10), ylim = c(0, 1), expand = FALSE, clip = "off") +
  labs(tag = "(b)") +
  theme_void() +
  theme(
    plot.margin = margin(0, 2, 0, 2),
    plot.tag = element_text(size = 13, face = "bold", colour = "#2f2f2f")
  )

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
    title = "Independent GSVI held-out — YOLO11x vs YOLO11x\u2013Qwen2-VL",
    subtitle = paste0(
      sprintf(
        "Image-level metrics; error bars are 95%% percentile CIs from a class-stratified, paired panorama bootstrap (B = 10,000; %d images from %d panoramas). ",
        n_images, n_panoramas
      ),
      "\nThe pipeline keeps a YOLO positive only when Qwen2-VL also answers Yes; ",
      sub("\\. Source:.*$", "", sub("^.*?: ", "", qwen_row$note))
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

# Same panel without title, subtitle or caption, for the manuscript (the
# description goes in the figure legend there).
panel_bare <- (p_bars | cm_block) + plot_layout(widths = c(1.3, 2.15))
out_bare <- file.path(FIG_DIR, "1_Heldout_yolo_qwen_panel_manuscript.png")
ggsave(out_bare, panel_bare, width = 12.8, height = 4.8, dpi = 600, bg = "white")
message("Wrote ", out_bare)

# --- cascade only: the same headline result without the YOLO baseline -------
qwen_bar_df <- bar_df |> filter(model == PIPE_LABEL)

p_bars_qwen <- ggplot(qwen_bar_df, aes(x = metric, y = score)) +
  geom_col(width = 0.58, fill = STAGE_COLOURS[[PIPE_LABEL]], colour = NA) +
  geom_errorbar(
    aes(ymin = ci_low, ymax = ci_high),
    width = 0.15, linewidth = 0.45, colour = "#3a3a3a"
  ) +
  geom_text(
    aes(label = sprintf("%.1f", 100 * score), y = pmin(ci_high, 1) + 0.035),
    size = 3.2, fontface = "bold", colour = "#2f2f2f"
  ) +
  scale_y_continuous(limits = c(0, 1.12), breaks = seq(0, 1, 0.2), labels = function(x) 100 * x, expand = c(0, 0)) +
  labs(x = NULL, y = "Score (%)", title = NULL) +
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
  sprintf("Confusion matrix: mean of %s runs", runs_word), QWEN_CM_PALETTE
)

qwen_fig <- (p_bars_qwen | (p_true_label | p_cm_qwen_solo) + plot_layout(widths = c(0.08, 1))) +
  plot_layout(widths = c(1.25, 1)) +
  plot_annotation(
    title = "Independent GSVI held-out — YOLO11x\u2013Qwen2-VL",
    subtitle = paste0(
      sprintf(
        "Image-level metrics; error bars are 95%% percentile CIs from a class-stratified, paired panorama bootstrap (B = 10,000; %d images from %d panoramas). ",
        n_images, n_panoramas
      ),
      "\n",
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

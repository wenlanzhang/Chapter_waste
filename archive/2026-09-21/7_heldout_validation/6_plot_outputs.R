#!/usr/bin/env Rscript
# Step 7 figures: SC-mix sensitivity charts + YOLO vs YOLO→Qwen confusion matrices

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

DATA_ROOT <- chapter_data_root
STEP7_DIR <- file.path(DATA_ROOT, "7_heldout_validation")
VALIDATION_DIR <- file.path(STEP7_DIR, "Validation")
if (!dir.exists(VALIDATION_DIR)) {
  VALIDATION_DIR <- file.path(DATA_ROOT, "6_sensitivity_archive", "Validation")
}
THESIS_DIR <- file.path(STEP7_DIR, "thesis_table")
DETAIL_CSV <- file.path(THESIS_DIR, "yolo_vs_qwen_heldout_detail.csv")
CI_CSV <- file.path(THESIS_DIR, "yolo_vs_qwen_heldout_ci_table.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "7_heldout_validation")

SC_HELDOUT_CSV <- file.path(VALIDATION_DIR, "heldout_val_summary.csv")
if (!file.exists(SC_HELDOUT_CSV)) {
  SC_HELDOUT_CSV <- file.path(VALIDATION_DIR, "del", "heldout_val_summary.csv")
}
GSVI_HELDOUT_CSV <- file.path(VALIDATION_DIR, "heldout_GSVI_p100_val_summary.csv")
if (!file.exists(GSVI_HELDOUT_CSV)) {
  GSVI_HELDOUT_CSV <- file.path(VALIDATION_DIR, "heldout_GSVI_val_summary.csv")
}

SCENARIO_ORDER <- c("sc_0pct", "sc_25pct", "sc_50pct", "sc_75pct", "sc_100pct")
SCENARIO_LABELS <- c(
  "sc_0pct" = "0% SC-slot",
  "sc_25pct" = "25% SC-slot",
  "sc_50pct" = "50% SC-slot",
  "sc_75pct" = "75% SC-slot",
  "sc_100pct" = "100% SC-slot / baseline"
)
SCENARIO_PCT <- c(
  "sc_0pct" = 0,
  "sc_25pct" = 25,
  "sc_50pct" = 50,
  "sc_75pct" = 75,
  "sc_100pct" = 100
)
SCENARIO_COLOURS <- c(
  "sc_0pct" = "#D4CCC2",
  "sc_25pct" = "#C9A27F",
  "sc_50pct" = "#A67C52",
  "sc_75pct" = "#8B5A3C",
  "sc_100pct" = "#6B4226"
)

BINARY_METRIC_KEYS <- c("accuracy", "precision", "recall", "f1")
BINARY_METRIC_LABELS <- c(
  "accuracy" = "Accuracy",
  "precision" = "Precision",
  "recall" = "Recall",
  "f1" = "F1"
)
BINARY_METRIC_COLOURS <- c(
  "Accuracy" = "#4D2D18",
  "Precision" = "#6B4226",
  "Recall" = "#C9A27F",
  "F1" = "#8B5A3C"
)

MAP_METRIC_COLS <- c("mAP50", "mAP50.95")
MAP_METRIC_LABELS <- c("mAP50" = "mAP@0.50", "mAP50.95" = "mAP@0.50:0.95")
MAP_METRIC_COLOURS <- c("mAP@0.50" = "#6B4226", "mAP@0.50:0.95" = "#C9A27F")

TEST_SET_LABELS <- c(
  "Self-collected held-out" = "Self-collected imagery (n = %s)",
  "GSVI held-out" = "Google Street View imagery (n = %s)"
)

prepare_summary <- function(path, test_set) {
  read.csv(path, stringsAsFactors = FALSE) |>
    filter(scenario %in% SCENARIO_ORDER) |>
    mutate(
      test_set = test_set,
      scenario = factor(scenario, levels = SCENARIO_ORDER),
      sc_pct = SCENARIO_PCT[as.character(scenario)],
      scenario_label = SCENARIO_LABELS[as.character(scenario)],
      n_images = as.integer(n_images),
      n_waste = as.integer(n_waste_labels),
      n_background = as.integer(n_background)
    )
}

build_binary_line_panel <- function(df, panel_tag, test_set_label) {
  n_images <- unique(df$n_images)
  n_waste <- unique(df$n_waste)
  n_background <- unique(df$n_background)

  plot_df <- df |>
    select(scenario, sc_pct, all_of(BINARY_METRIC_KEYS)) |>
    pivot_longer(
      cols = all_of(BINARY_METRIC_KEYS),
      names_to = "metric_key",
      values_to = "score"
    ) |>
    mutate(
      score_pct = score * 100,
      metric = factor(
        metric_key,
        levels = BINARY_METRIC_KEYS,
        labels = BINARY_METRIC_LABELS[BINARY_METRIC_KEYS]
      )
    )

  ggplot(plot_df, aes(x = sc_pct, y = score_pct, colour = metric, group = metric)) +
    geom_line(linewidth = 0.9) +
    geom_point(size = 2.6) +
    geom_text(
      aes(label = sprintf("%.0f", score_pct)),
      size = 2.6,
      fontface = "bold",
      vjust = -0.85,
      show.legend = FALSE
    ) +
    scale_x_continuous(
      breaks = c(0, 25, 50, 75, 100),
      labels = c("0%", "25%", "50%", "75%", "100%"),
      limits = c(-2, 102),
      expand = expansion(mult = c(0.02, 0.02))
    ) +
    scale_y_continuous(
      limits = c(60, 100),
      breaks = seq(60, 100, 10),
      expand = expansion(mult = c(0.02, 0.08))
    ) +
    scale_colour_manual(
      values = BINARY_METRIC_COLOURS,
      name = "Binary metric"
    ) +
    labs(
      title = sprintf(
        "%s %s",
        panel_tag,
        sprintf(test_set_label, comma(n_images))
      ),
      subtitle = sprintf(
        "%s waste + %s background images; val confidence = %s",
        comma(n_waste),
        comma(n_background),
        {
          vc <- unique(df$val_conf)
          if (length(vc) == 1 && is.finite(vc)) format(vc, trim = TRUE) else "—"
        }
      ),
      x = "SC-slot retention in YOLO training set",
      y = "Score (%)"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 10.5, face = "bold", hjust = 0, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 8.5, hjust = 0, colour = "#6B5B4F", margin = margin(b = 6)),
      axis.text.x = element_text(size = 9, colour = "#4D2D18"),
      axis.text.y = element_text(size = 8.5),
      axis.title = element_text(size = 9.5, colour = "#4D2D18"),
      panel.grid.major.x = element_line(colour = "grey92", linewidth = 0.25),
      legend.position = "none",
      plot.margin = margin(8, 12, 6, 8)
    )
}

build_map_line_panel <- function(df, panel_tag, test_set_label) {
  n_images <- unique(df$n_images)

  plot_df <- df |>
    select(sc_pct, all_of(MAP_METRIC_COLS)) |>
    pivot_longer(
      cols = all_of(MAP_METRIC_COLS),
      names_to = "metric_key",
      values_to = "score"
    ) |>
    mutate(
      score_pct = score * 100,
      metric = factor(
        metric_key,
        levels = MAP_METRIC_COLS,
        labels = MAP_METRIC_LABELS[MAP_METRIC_COLS]
      )
    )

  y_max <- max(60, ceiling(max(plot_df$score_pct, na.rm = TRUE) / 5) * 5 + 5)

  ggplot(plot_df, aes(x = sc_pct, y = score_pct, colour = metric, group = metric)) +
    geom_line(linewidth = 0.9) +
    geom_point(size = 2.6) +
    geom_text(
      aes(label = sprintf("%.1f", score_pct)),
      size = 2.6,
      fontface = "bold",
      vjust = -0.85,
      show.legend = FALSE
    ) +
    scale_x_continuous(
      breaks = c(0, 25, 50, 75, 100),
      labels = c("0%", "25%", "50%", "75%", "100%"),
      limits = c(-2, 102),
      expand = expansion(mult = c(0.02, 0.02))
    ) +
    scale_y_continuous(
      limits = c(0, y_max),
      breaks = pretty_breaks(n = 5),
      expand = expansion(mult = c(0.02, 0.10))
    ) +
    scale_colour_manual(
      values = MAP_METRIC_COLOURS,
      name = "Detection metric"
    ) +
    labs(
      title = sprintf(
        "%s %s",
        panel_tag,
        sprintf(test_set_label, comma(n_images))
      ),
      x = "SC-slot retention in YOLO training set",
      y = "Score (%)"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 10.5, face = "bold", hjust = 0, colour = "#2f2f2f"),
      axis.text.x = element_text(size = 9, colour = "#4D2D18"),
      axis.text.y = element_text(size = 8.5),
      axis.title = element_text(size = 9.5, colour = "#4D2D18"),
      panel.grid.major.x = element_line(colour = "grey92", linewidth = 0.25),
      legend.position = "none",
      plot.margin = margin(8, 12, 6, 8)
    )
}

build_f1_comparison_panel <- function(sc_df, gsvi_df) {
  combined <- bind_rows(
    sc_df |> transmute(sc_pct, f1, test_set = "Self-collected held-out"),
    gsvi_df |> transmute(sc_pct, f1, test_set = "GSVI held-out")
  ) |>
    mutate(
      f1_pct = f1 * 100,
      test_set = factor(
        test_set,
        levels = c("Self-collected held-out", "GSVI held-out")
      )
    )

  ggplot(combined, aes(x = sc_pct, y = f1_pct, colour = test_set, group = test_set)) +
    geom_line(linewidth = 1.0) +
    geom_point(size = 3.0) +
    geom_text(
      aes(label = sprintf("%.1f", f1_pct)),
      size = 3.0,
      fontface = "bold",
      vjust = -0.9,
      show.legend = FALSE
    ) +
    scale_x_continuous(
      breaks = c(0, 25, 50, 75, 100),
      labels = c("0%", "25%", "50%", "75%", "100%"),
      limits = c(-2, 102),
      expand = expansion(mult = c(0.02, 0.02))
    ) +
    scale_y_continuous(
      limits = c(78, 92),
      breaks = seq(78, 92, 2),
      expand = expansion(mult = c(0.02, 0.08))
    ) +
    scale_colour_manual(
      values = c(
        "Self-collected held-out" = "#6B4226",
        "GSVI held-out" = "#C9A27F"
      ),
      name = "Held-out test set"
    ) +
    labs(
      title = "F1 score vs SC-slot retention",
      subtitle = "Same five YOLO models evaluated on two external held-out image sets",
      x = "SC-slot retention in YOLO training set",
      y = "F1 score (%)"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 12, face = "bold", hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 8)),
      axis.text = element_text(colour = "#4D2D18"),
      axis.title = element_text(colour = "#4D2D18"),
      legend.position = "bottom",
      legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
      legend.text = element_text(size = 9, colour = "#4D2D18"),
      legend.margin = margin(t = 4)
    )
}

build_binary_bar_panel <- function(df, panel_tag, test_set_label) {
  n_images <- unique(df$n_images)

  plot_df <- df |>
    select(scenario, all_of(BINARY_METRIC_KEYS)) |>
    pivot_longer(
      cols = all_of(BINARY_METRIC_KEYS),
      names_to = "metric_key",
      values_to = "score"
    ) |>
    mutate(
      score_pct = score * 100,
      metric = factor(
        metric_key,
        levels = BINARY_METRIC_KEYS,
        labels = BINARY_METRIC_LABELS[BINARY_METRIC_KEYS]
      ),
      scenario = factor(scenario, levels = SCENARIO_ORDER)
    )

  ggplot(plot_df, aes(x = metric, y = score_pct, fill = scenario)) +
    geom_col(
      position = position_dodge(width = 0.78),
      width = 0.68,
      colour = "white",
      linewidth = 0.45
    ) +
    scale_fill_manual(
      values = SCENARIO_COLOURS,
      labels = SCENARIO_LABELS[SCENARIO_ORDER],
      name = "SC-slot retention"
    ) +
    scale_y_continuous(
      limits = c(0, 100),
      breaks = seq(0, 100, 25),
      expand = expansion(mult = c(0, 0.10))
    ) +
    labs(
      title = sprintf(
        "%s %s",
        panel_tag,
        sprintf(test_set_label, comma(n_images))
      ),
      x = NULL,
      y = "Score (%)"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 10.5, face = "bold", hjust = 0, colour = "#2f2f2f"),
      axis.text.x = element_text(size = 9, colour = "#4D2D18"),
      axis.text.y = element_text(size = 8.5),
      panel.grid.major.x = element_blank(),
      legend.position = "none",
      plot.margin = margin(8, 12, 6, 8)
    )
}

message("Reading validation summaries...")
sc_heldout <- prepare_summary(SC_HELDOUT_CSV, "Self-collected held-out")
gsvi_heldout <- prepare_summary(GSVI_HELDOUT_CSV, "GSVI held-out")

p_sc_binary <- build_binary_line_panel(
  sc_heldout,
  "(A)",
  TEST_SET_LABELS[["Self-collected held-out"]]
)
p_gsvi_binary <- build_binary_line_panel(
  gsvi_heldout,
  "(B)",
  TEST_SET_LABELS[["GSVI held-out"]]
)

binary_panel <- (p_sc_binary / p_gsvi_binary) +
  plot_layout(guides = "collect") &
  theme(
    legend.position = "bottom",
    legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
    legend.text = element_text(size = 9, colour = "#4D2D18"),
    legend.margin = margin(t = 4)
  )

binary_panel <- binary_panel +
  plot_annotation(
    title = "Held-out validation: binary waste detection vs SC-slot retention",
    subtitle = paste0(
      "Five models trained on 695 images (fixed GSVI core + 85 SC slots at 0/25/50/75/100% retention); ",
      "baseline = 610 GSVI + 85 SC. Image-level TP/FP/TN/FN on external held-out sets."
    ),
    caption = paste0(
      "x-axis = retention of the original 85 SC training slots (not % of all training images). ",
      "100% SC-slot retention = baseline used in the main analysis. ",
      "Held-out sets are panoid-disjoint from all training scenarios."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8))
    )
  )

p_sc_map <- build_map_line_panel(
  sc_heldout,
  "(A)",
  TEST_SET_LABELS[["Self-collected held-out"]]
)
p_gsvi_map <- build_map_line_panel(
  gsvi_heldout,
  "(B)",
  TEST_SET_LABELS[["GSVI held-out"]]
)

map_panel <- (p_sc_map / p_gsvi_map) +
  plot_layout(guides = "collect") &
  theme(
    legend.position = "bottom",
    legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
    legend.text = element_text(size = 9, colour = "#4D2D18"),
    legend.margin = margin(t = 4)
  )

map_panel <- map_panel +
  plot_annotation(
    title = "Held-out validation: YOLO box detection (mAP) vs SC-slot retention",
    subtitle = "Mean average precision on held-out waste bounding boxes (COCO-style mAP@0.50 and mAP@0.50:0.95).",
    caption = "Same five scenario models and held-out sets as the binary metrics figure. Box-level mAP is separate from image-level binary metrics.",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8))
    )
  )

p_f1 <- build_f1_comparison_panel(sc_heldout, gsvi_heldout)

p_sc_bars <- build_binary_bar_panel(
  sc_heldout,
  "(A)",
  TEST_SET_LABELS[["Self-collected held-out"]]
)
p_gsvi_bars <- build_binary_bar_panel(
  gsvi_heldout,
  "(B)",
  TEST_SET_LABELS[["GSVI held-out"]]
)

bar_panel <- (p_sc_bars / p_gsvi_bars) +
  plot_layout(guides = "collect") &
  theme(
    legend.position = "bottom",
    legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
    legend.text = element_text(size = 9, colour = "#4D2D18"),
    legend.margin = margin(t = 4)
  )

bar_panel <- bar_panel +
  plot_annotation(
    title = "Held-out validation: binary metrics by SC-slot retention",
    subtitle = "Grouped bars compare all four binary metrics under each SC-slot retention scenario.",
    caption = "Fill colour runs from light (0% SC-slot retention) to dark brown (100% SC-slot retention / baseline).",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8))
    )
  )

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

out_binary <- file.path(FIG_DIR, "Heldout_validation_binary_metrics.png")
ggsave(out_binary, plot = binary_panel, width = 9, height = 9.5, dpi = 600, bg = "white")
message("Wrote ", out_binary)

out_map <- file.path(FIG_DIR, "Heldout_validation_map_metrics.png")
ggsave(out_map, plot = map_panel, width = 9, height = 9, dpi = 600, bg = "white")
message("Wrote ", out_map)

out_f1 <- file.path(FIG_DIR, "Heldout_validation_f1_comparison.png")
ggsave(out_f1, plot = p_f1, width = 8, height = 5.5, dpi = 600, bg = "white")
message("Wrote ", out_f1)

out_bars <- file.path(FIG_DIR, "Heldout_validation_binary_bars.png")
ggsave(out_bars, plot = bar_panel, width = 9, height = 9.5, dpi = 600, bg = "white")
message("Wrote ", out_bars)

# --- YOLO vs YOLO→Qwen confusion matrices ---
CLASS_LEVELS <- c("Background", "Waste")

stage_label <- function(stage) {
  if (grepl("Qwen", stage, ignore.case = TRUE)) {
    return("YOLO → Qwen")
  }
  "YOLO"
}

counts_to_confusion <- function(tp, fp, tn, fn) {
  data.frame(
    truth = factor(c("Waste", "Waste", "Background", "Background"), levels = CLASS_LEVELS),
    pred = factor(c("Waste", "Background", "Waste", "Background"), levels = CLASS_LEVELS),
    n = c(as.integer(tp), as.integer(fn), as.integer(fp), as.integer(tn)),
    stringsAsFactors = FALSE
  ) |>
    group_by(truth) |>
    mutate(
      row_n = sum(n),
      pct_of_truth_row = if_else(row_n > 0, 100 * n / row_n, 0),
      cell_label = sprintf("%s\n(%.1f%% row)", format(n, big.mark = ",", trim = TRUE), pct_of_truth_row),
      text_colour = chocolate_label_colour(n, trans = "sqrt")
    ) |>
    ungroup()
}

build_confusion_panel <- function(cm, title, metrics_caption, fill_max, show_legend = FALSE) {
  ggplot(cm, aes(x = pred, y = truth, fill = n)) +
    geom_tile(colour = "white", linewidth = 1.0) +
    geom_text(aes(label = cell_label, colour = text_colour), size = 3.6, fontface = "bold") +
    scale_colour_identity() +
    scale_x_discrete(limits = CLASS_LEVELS) +
    scale_y_discrete(limits = rev(CLASS_LEVELS)) +
    scale_fill_gradientn(
      colours = CHOCOLATE_PALETTE,
      name = "Count",
      trans = "sqrt",
      limits = c(0, fill_max)
    ) +
    labs(
      title = title,
      caption = metrics_caption,
      x = "Predicted",
      y = "True"
    ) +
    map_theme() +
    theme(
      plot.subtitle = element_blank(),
      panel.grid = element_blank(),
      axis.text.x = element_text(size = 10),
      axis.text.y = element_text(size = 10),
      plot.caption = element_text(size = 8.5, hjust = 0.5, margin = margin(t = 6)),
      legend.position = if (show_legend) "right" else "none"
    )
}

if (!file.exists(DETAIL_CSV)) {
  stop("Missing ", DETAIL_CSV, " — run 5_build_outputs.py first")
}

raw <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)
need <- c("stage", "tp", "fp", "tn", "fn", "accuracy_pct", "precision_pct", "recall_pct", "f1_pct")
missing <- setdiff(need, names(raw))
if (length(missing)) {
  stop("Detail CSV missing columns: ", paste(missing, collapse = ", "))
}

cms <- lapply(seq_len(nrow(raw)), function(i) {
  counts_to_confusion(raw$tp[i], raw$fp[i], raw$tn[i], raw$fn[i])
})
fill_max <- max(vapply(cms, function(cm) max(cm$n), numeric(1)))

panels <- lapply(seq_len(nrow(raw)), function(i) {
  row <- raw[i, ]
  cm <- cms[[i]]
  n_tot <- sum(cm$n)
  title <- sprintf("%s (n = %s)", stage_label(row$stage), format(n_tot, big.mark = ","))
  metrics_caption <- sprintf(
    "Acc %.1f%% | P %.1f%% | R %.1f%% | F1 %.1f%%",
    row$accuracy_pct, row$precision_pct, row$recall_pct, row$f1_pct
  )
  build_confusion_panel(
    cm,
    title = title,
    metrics_caption = metrics_caption,
    fill_max = fill_max,
    show_legend = (i == nrow(raw))
  )
})

confusion_fig <- wrap_plots(panels, nrow = 1, guides = "collect") +
  plot_annotation(
    title = "Independent GSVI held-out — binary confusion matrices",
    subtitle = "Baseline training (sc_100pct); image-level waste present vs background"
  )

out_confusion <- file.path(FIG_DIR, "Heldout_yolo_qwen_confusion_matrix.png")
ggsave(out_confusion, confusion_fig, width = 10.5, height = 5.2, dpi = 600, bg = "white")
message("Wrote ", out_confusion)

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
      "Image-level binary metrics with Wilson binomial 95% CI (n = 180). ",
      "YOLO + Qwen uses the best of three independent full YOLO-positive Qwen runs (highest F1)."
    ),
    caption = "Left: Accuracy / Precision / Recall / F1. Right: confusion matrices (True × Predicted).",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 8.8, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 6)),
      plot.caption = element_text(size = 8, hjust = 0, colour = "#7A6A5C")
    )
  )

out_panel <- file.path(FIG_DIR, "Heldout_yolo_qwen_panel.png")
ggsave(out_panel, panel_fig, width = 12.8, height = 5.5, dpi = 600, bg = "white")
message("Wrote ", out_panel)

# --- Replicate stability figure ---
# Metrics: YOLO | Run 1 | Run 2 | Run 3 | 3-run majority
# Bottom: Yes/No and agreement for full YOLO+ re-runs (stability only)
STAB_CSV <- file.path(THESIS_DIR, "yolo_qwen_yolo_pos_replicates.csv")
if (!file.exists(STAB_CSV)) {
  message("Skip stability figure: missing ", STAB_CSV)
} else {
  stab_raw <- read.csv(STAB_CSV, stringsAsFactors = FALSE)

  setting_levels <- c(
    "YOLO only",
    "Qwen run 1",
    "Qwen run 2",
    "Qwen run 3",
    "3-run majority"
  )

  stab_plot <- stab_raw |>
    filter(role %in% c("baseline", "majority_summary", "replicate")) |>
    mutate(
      short = case_when(
        grepl("YOLO only", setting, ignore.case = TRUE) ~ "YOLO only",
        grepl("majority", setting, ignore.case = TRUE) ~ "3-run majority",
        grepl("Qwen2_1", setting) ~ "Qwen run 1",
        grepl("Qwen2_2", setting) ~ "Qwen run 2",
        grepl("Qwen2_3", setting) ~ "Qwen run 3",
        TRUE ~ setting
      ),
      protocol = case_when(
        role == "baseline" ~ "baseline",
        grepl("majority", role, ignore.case = TRUE) ~ "majority_summary",
        TRUE ~ "replicate"
      )
    ) |>
    transmute(
      short,
      accuracy_pct,
      precision_pct,
      recall_pct,
      f1_pct,
      qwen_yes_among_yolo,
      qwen_no_among_yolo,
      n_yolo_pos,
      protocol
    )

  stab_plot <- stab_plot |>
    mutate(short = factor(short, levels = setting_levels)) |>
    filter(!is.na(short)) |>
    arrange(short)

  maj_row <- stab_plot |> filter(short == "3-run majority")
  maj_row <- if (nrow(maj_row)) maj_row[1, ] else NULL

  METRIC_COLOURS_STAB <- c(
    "Accuracy" = "#8B6B4A",
    "Precision" = "#6B4226",
    "Recall" = "#C9A27F",
    "F1" = "#5F6F5A"
  )

  met_long <- stab_plot |>
    select(short, accuracy_pct, precision_pct, recall_pct, f1_pct, protocol) |>
    pivot_longer(
      cols = c(accuracy_pct, precision_pct, recall_pct, f1_pct),
      names_to = "metric_key",
      values_to = "score_pct"
    ) |>
    mutate(
      metric = factor(
        metric_key,
        levels = c("accuracy_pct", "precision_pct", "recall_pct", "f1_pct"),
        labels = c("Accuracy", "Precision", "Recall", "F1")
      )
    )

  # Soft highlight / light frame on 3-run majority (summary column)
  maj_x <- which(setting_levels == "3-run majority")
  highlight_maj <- length(maj_x) == 1 && "3-run majority" %in% levels(met_long$short) &&
    any(met_long$short == "3-run majority", na.rm = TRUE)

  p_stab_metrics <- ggplot(met_long, aes(x = short, y = score_pct, fill = metric)) +
    {
      if (highlight_maj) {
        list(
          annotate(
            "rect",
            xmin = maj_x - 0.48,
            xmax = maj_x + 0.48,
            ymin = -Inf,
            ymax = Inf,
            fill = "#5F6F5A",
            alpha = 0.10
          ),
          annotate(
            "rect",
            xmin = maj_x - 0.48,
            xmax = maj_x + 0.48,
            ymin = -Inf,
            ymax = Inf,
            fill = NA,
            colour = "#5F6F5A",
            linewidth = 0.45,
            alpha = 0.35
          )
        )
      }
    } +
    geom_col(position = position_dodge(width = 0.78), width = 0.72, colour = NA) +
    geom_text(
      aes(label = sprintf("%.0f", score_pct)),
      position = position_dodge(width = 0.78),
      vjust = -0.35,
      size = 2.35,
      colour = CHAPTER_AXIS_COLOUR
    ) +
    scale_fill_manual(values = METRIC_COLOURS_STAB, name = NULL) +
    scale_x_discrete(
      labels = c(
        "YOLO only" = "YOLO\nonly",
        "Qwen run 1" = "Run 1",
        "Qwen run 2" = "Run 2",
        "Qwen run 3" = "Run 3",
        "3-run majority" = "3-run\nmajority"
      )
    ) +
    scale_y_continuous(
      limits = c(0, 112),
      breaks = seq(0, 100, 20),
      expand = c(0, 0),
      labels = function(x) paste0(x, "%")
    ) +
    labs(
      x = NULL,
      y = "Score",
      title = "Image-level metrics: YOLO vs repeated inferences"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 11, face = "bold", hjust = 0, margin = margin(b = 6)),
      plot.subtitle = element_blank(),
      legend.position = "top",
      legend.justification = "left",
      legend.margin = margin(b = 2),
      axis.text.x = element_text(size = 8.2, colour = CHAPTER_AXIS_COLOUR, lineheight = 0.9),
      panel.grid.major.x = element_blank(),
      panel.grid.minor = element_blank()
    )

  # Yes/No among YOLO+ (full-positive audits only; not FP-only main)
  yn_long <- stab_plot |>
    filter(short %in% c("3-run majority", "Qwen run 1", "Qwen run 2", "Qwen run 3")) |>
    tidyr::pivot_longer(
      cols = c(qwen_yes_among_yolo, qwen_no_among_yolo),
      names_to = "vote",
      values_to = "n"
    ) |>
    mutate(
      vote = factor(
        ifelse(vote == "qwen_yes_among_yolo", "Yes", "No"),
        levels = c("Yes", "No")
      ),
      n = as.numeric(n),
      pct = 100 * n / as.numeric(n_yolo_pos),
      short = factor(
        as.character(short),
        levels = c("3-run majority", "Qwen run 1", "Qwen run 2", "Qwen run 3")
      )
    )

  VOTE_FILLS <- c("Yes" = "#5F6F5A", "No" = "#E4D8CC")

  p_stab_votes <- ggplot(yn_long, aes(x = short, y = n, fill = vote)) +
    geom_col(width = 0.62, colour = "white", linewidth = 0.4) +
    geom_text(
      aes(
        label = ifelse(
          pct >= 12,
          sprintf("%s\n%d", as.character(vote), as.integer(n)),
          ""
        ),
        colour = ifelse(vote == "Yes", "white", CHAPTER_AXIS_COLOUR)
      ),
      position = position_stack(vjust = 0.5),
      size = 2.7,
      lineheight = 0.9,
      show.legend = FALSE
    ) +
    scale_colour_identity() +
    scale_fill_manual(values = VOTE_FILLS, name = NULL) +
    scale_x_discrete(
      labels = c(
        "3-run majority" = "3-run\nmajority",
        "Qwen run 1" = "Run 1",
        "Qwen run 2" = "Run 2",
        "Qwen run 3" = "Run 3"
      )
    ) +
    scale_y_continuous(expand = expansion(mult = c(0, 0.04))) +
    labs(
      x = NULL,
      y = "Images (of 115 YOLO+)",
      title = "Yes / No on all YOLO positives"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 11, face = "bold", hjust = 0, margin = margin(b = 6)),
      plot.subtitle = element_blank(),
      legend.position = "top",
      legend.justification = "left",
      panel.grid.major.x = element_blank(),
      axis.text.x = element_text(size = 9)
    )

  sum_row <- stab_raw |> filter(role == "summary")
  n_pos <- if (nrow(sum_row)) as.integer(sum_row$n_yolo_pos[1]) else 115L
  note <- if (nrow(sum_row)) as.character(sum_row$note[1]) else ""
  unan <- suppressWarnings(as.integer(sub(".*Unanimous Yes/No on ([0-9]+)/.*", "\\1", note)))
  if (!is.finite(unan)) unan <- NA_integer_
  disagree <- if (is.finite(unan)) n_pos - unan else NA_integer_

  pair_labels <- numeric(0)
  for (pat in c(
    "Qwen2_1_vs_Qwen2_2 agree=([0-9.]+)%",
    "Qwen2_1_vs_Qwen2_3 agree=([0-9.]+)%",
    "Qwen2_2_vs_Qwen2_3 agree=([0-9.]+)%"
  )) {
    m <- regmatches(note, regexec(pat, note))[[1]]
    if (length(m) >= 2) pair_labels <- c(pair_labels, as.numeric(m[[2]]))
  }
  pair_df <- data.frame(
    pair = c("Run 1 vs 2", "Run 1 vs 3", "Run 2 vs 3"),
    agree_pct = if (length(pair_labels) == 3) pair_labels else rep(NA_real_, 3),
    stringsAsFactors = FALSE
  )
  pair_df$pair <- factor(pair_df$pair, levels = pair_df$pair)

  agree_df <- data.frame(
    status = factor(
      c("Unanimous\n(3/3 same)", "At least one\ndisagree"),
      levels = c("Unanimous\n(3/3 same)", "At least one\ndisagree")
    ),
    n = c(unan, disagree),
    stringsAsFactors = FALSE
  ) |>
    filter(is.finite(n)) |>
    mutate(
      pct = 100 * n / n_pos,
      ymax = cumsum(pct),
      ymin = lag(ymax, default = 0),
      label_y = (ymin + ymax) / 2
    )

  p_stab_donut <- ggplot(agree_df, aes(ymax = ymax, ymin = ymin, xmax = 4, xmin = 2.2, fill = status)) +
    geom_rect(colour = "white", linewidth = 1.1) +
    coord_polar(theta = "y") +
    xlim(c(0.6, 4.4)) +
    scale_fill_manual(
      values = c(
        "Unanimous\n(3/3 same)" = "#5F6F5A",
        "At least one\ndisagree" = "#E4D8CC"
      ),
      name = NULL
    ) +
    annotate(
      "text",
      x = 0.6,
      y = 0,
      label = if (is.finite(unan)) {
        sprintf("%d\nof %d\nunanimous", unan, n_pos)
      } else {
        "Agreement"
      },
      size = 3.4,
      colour = CHAPTER_AXIS_COLOUR,
      fontface = "bold",
      lineheight = 0.95
    ) +
    labs(title = "Re-run decision agreement") +
    theme_void() +
    theme(
      plot.title = element_text(
        size = 11, face = "bold", hjust = 0.5, colour = CHAPTER_AXIS_COLOUR,
        margin = margin(b = 4)
      ),
      legend.position = "bottom",
      legend.text = element_text(size = 8, colour = CHAPTER_AXIS_COLOUR),
      plot.margin = margin(4, 4, 4, 4)
    )

  p_stab_pairs <- ggplot(pair_df, aes(x = pair, y = agree_pct)) +
    geom_col(width = 0.55, fill = "#8B9B82", colour = NA) +
    geom_text(
      aes(label = sprintf("%.1f%%", agree_pct)),
      vjust = -0.4,
      size = 3.1,
      colour = CHAPTER_AXIS_COLOUR,
      fontface = "bold"
    ) +
    scale_y_continuous(
      limits = c(0, 110),
      breaks = seq(0, 100, 25),
      expand = c(0, 0),
      labels = function(x) paste0(x, "%")
    ) +
    labs(
      x = NULL,
      y = "Pairwise Yes/No match",
      title = "Pairwise re-run agreement"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 11, face = "bold", hjust = 0, margin = margin(b = 6)),
      plot.subtitle = element_blank(),
      panel.grid.major.x = element_blank(),
      axis.text.x = element_text(size = 8.5)
    )

  cap_parts <- character(0)
  if (!is.null(maj_row) && nrow(as.data.frame(maj_row)) >= 1) {
    mj <- as.data.frame(maj_row)[1, ]
    cap_parts <- c(cap_parts, sprintf(
      "3-run majority (all YOLO+): Acc %.1f%% · P %.1f%% · R %.1f%% · F1 %.1f%%",
      mj$accuracy_pct, mj$precision_pct, mj$recall_pct, mj$f1_pct
    ))
  }
  caption_text <- paste0(
    if (length(cap_parts)) paste0(paste(cap_parts, collapse = "  |  "), "  |  ") else "",
    "Bottom panels: three independent full YOLO+ re-runs (stability only)."
  )

  top_row <- p_stab_metrics
  bottom_row <- p_stab_votes | p_stab_donut | p_stab_pairs
  bottom_row <- bottom_row + plot_layout(widths = c(1.15, 0.95, 1.05))

  stab_fig <- top_row / bottom_row +
    plot_layout(heights = c(1.15, 1)) +
    plot_annotation(
      title = "Repeated-inference stability of Qwen2-VL on held-out YOLO detections",
      subtitle = paste0(
        "Stability analysis: three independent Qwen2-VL calls on all 115 YOLO-positive images; ",
        "the three-run majority is shown as a summary."
      ),
      caption = caption_text,
      theme = theme(
        plot.title = element_text(face = "bold", size = 13.5, hjust = 0.5, colour = "#2f2f2f"),
        plot.subtitle = element_text(size = 8.8, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 8)),
        plot.caption = element_text(size = 7.6, hjust = 0, colour = "#7A6A5C", margin = margin(t = 8))
      )
    )

  out_stab <- file.path(FIG_DIR, "Heldout_qwen_replicate_stability.png")
  ggsave(out_stab, stab_fig, width = 12.8, height = 8.2, dpi = 600, bg = "white")
  message("Wrote ", out_stab)
}


message("Done.")

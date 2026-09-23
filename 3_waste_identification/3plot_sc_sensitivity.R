#!/usr/bin/env Rscript
# Step 3 figure 3 — YOLO + Qwen on the independent GSVI held-out set,
# across every self-collected share of the YOLO training set present in the table.
#   3_Heldout_validation_binary_metrics.png  lines: each metric vs SC share
#   3_Heldout_validation_binary_bars.png     grouped bars: metric x SC share
# Input: thesis_table/table_4_sc_sensitivity_detail.csv (1_heldout_metrics.py)
#
# Replaces the older two-panel Heldout_validation_binary_* charts: the
# self-collected held-out panel is dropped, and only the YOLO -> Qwen cascade
# is shown (not the bare YOLO stage). Scenario set, labels, fills and the
# replicate note are all read off the input table.

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))

STEP3_DIR <- file.path(chapter_data_root, "3_waste_identification")
THESIS_DIR <- file.path(STEP3_DIR, "thesis_table")
DETAIL_CSV <- file.path(THESIS_DIR, "table_4_sc_sensitivity_detail.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_waste_identification")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(DETAIL_CSV)) {
  stop("Missing ", DETAIL_CSV, " — run 3_waste_identification/1_heldout_metrics.py first")
}

STAGE <- "YOLO → Qwen"

# Scenarios, their labels and their fills are all derived from the data, so a
# new SC share appears in the figure without touching this script.
scenario_levels <- function(df) {
  df |>
    distinct(scenario, sc_share_pct) |>
    arrange(sc_share_pct) |>
    pull(scenario) |>
    as.character()
}
share_labels <- function(df, levels_in) {
  shares <- df |>
    distinct(scenario, sc_share_pct) |>
    filter(as.character(scenario) %in% levels_in)
  setNames(sprintf("%g%%", shares$sc_share_pct[order(shares$sc_share_pct)]), levels_in)
}
share_colours <- function(levels_in) {
  setNames(colorRampPalette(c("#D4CCC2", "#6B4226"))(length(levels_in)), levels_in)
}
# "sc_100pct uses the best of 3 replicates, the rest 1" — read off qwen_status
# rather than restated by hand, so it cannot drift from what was actually run.
replicate_note <- function(df) {
  reps <- df |>
    distinct(scenario, qwen_status) |>
    mutate(n_rep = suppressWarnings(as.integer(sub("^([0-9]+).*$", "\\1", qwen_status))))
  multi <- reps |> filter(!is.na(n_rep), n_rep > 1)
  if (nrow(multi) == 0) {
    return("Every scenario uses a single Qwen pass.")
  }
  sprintf(
    "%s use%s the best of %s Qwen replicates; the remaining %d use a single Qwen pass.",
    paste(multi$scenario, collapse = ", "),
    if (nrow(multi) == 1) "s" else "",
    paste(unique(multi$n_rep), collapse = "/"),
    nrow(reps) - nrow(multi)
  )
}

METRIC_KEYS <- c("accuracy_pct", "precision_pct", "recall_pct", "f1_pct")
METRIC_LABELS <- c(
  "accuracy_pct" = "Accuracy",
  "precision_pct" = "Precision",
  "recall_pct" = "Recall",
  "f1_pct" = "F1"
)
METRIC_COLOURS <- c(
  "Accuracy" = "#4D2D18",
  "Precision" = "#6B4226",
  "Recall" = "#C9A27F",
  "F1" = "#8B5A3C"
)

# ---------------------------------------------------------------------------
detail <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)

SCENARIO_ORDER <- scenario_levels(detail)
SCENARIO_LABELS <- share_labels(detail, SCENARIO_ORDER)
SCENARIO_COLOURS <- share_colours(SCENARIO_ORDER)

cascade <- detail |>
  filter(stage == STAGE) |>
  mutate(scenario = factor(scenario, levels = SCENARIO_ORDER))

missing <- setdiff(SCENARIO_ORDER, as.character(cascade$scenario))
if (length(missing)) {
  stop(
    "No '", STAGE, "' row for: ", paste(missing, collapse = ", "),
    ". Run 3_waste_identification/2_qwen_review.py to label those scenarios first."
  )
}

n_images <- unique(cascade$tp + cascade$fp + cascade$tn + cascade$fn)
n_waste <- unique(cascade$tp + cascade$fn)
n_background <- unique(cascade$fp + cascade$tn)
stopifnot(length(n_images) == 1)

plot_df <- cascade |>
  select(scenario, sc_share_pct, all_of(METRIC_KEYS)) |>
  pivot_longer(all_of(METRIC_KEYS), names_to = "metric_key", values_to = "score_pct") |>
  mutate(
    metric = factor(metric_key, levels = METRIC_KEYS, labels = METRIC_LABELS[METRIC_KEYS])
  )

# Metrics that round to the same value at the same x would print on top of each
# other (at 0% SC all four are 91.1), so label each distinct value once.
label_df <- plot_df |>
  mutate(lab = sprintf("%.0f", score_pct)) |>
  group_by(sc_share_pct, lab) |>
  summarise(score_pct = mean(score_pct), .groups = "drop")

SHARES <- sort(unique(cascade$sc_share_pct))
SUBTITLE <- sprintf(
  "Independent GSVI held-out set: %s images (%s waste + %s background) | YOLO positives kept only when Qwen2-VL also answers Yes",
  comma(n_images), comma(n_waste), comma(n_background)
)
CAPTION <- paste0(
  sprintf(
    "%d retrained YOLO detectors differing only in the self-collected share of their training set, all scored on the same held-out images.\n",
    length(SCENARIO_ORDER)
  ),
  replicate_note(cascade)
)

base_theme <- function() {
  map_theme() +
    theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8)),
      axis.text = element_text(colour = "#4D2D18"),
      axis.title = element_text(size = 9.5, colour = "#4D2D18"),
      legend.position = "bottom",
      legend.justification = "center",
      legend.box.background = element_blank(),
      legend.background = element_blank(),
      legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
      legend.text = element_text(size = 9, colour = "#4D2D18"),
      legend.margin = margin(t = 4)
    )
}

# --- (1) lines: metric vs SC share -----------------------------------------
p_lines <- ggplot(plot_df, aes(x = sc_share_pct, y = score_pct, colour = metric, group = metric)) +
  geom_line(linewidth = 0.9) +
  geom_point(size = 2.6) +
  geom_text(
    data = label_df, aes(x = sc_share_pct, y = score_pct, label = lab),
    inherit.aes = FALSE, size = 2.6, fontface = "bold",
    vjust = -1.0, colour = "#4D2D18"
  ) +
  scale_x_continuous(
    breaks = SHARES,
    labels = sprintf("%g%%", SHARES),
    limits = range(SHARES) + c(-2, 2),
    expand = expansion(mult = c(0.02, 0.02))
  ) +
  scale_y_continuous(
    limits = c(88, 98),
    breaks = seq(88, 98, 2),
    expand = expansion(mult = c(0.04, 0.10))
  ) +
  scale_colour_manual(values = METRIC_COLOURS, name = "Binary metric") +
  labs(
    title = "YOLO + Qwen: binary waste detection vs self-collected training share",
    subtitle = SUBTITLE,
    caption = CAPTION,
    x = "Self-collected share of the YOLO training set",
    y = "Score (%)"
  ) +
  base_theme() +
  theme(panel.grid.major.x = element_line(colour = "grey92", linewidth = 0.25))

out_lines <- file.path(FIG_DIR, "3_Heldout_validation_binary_metrics.png")
ggsave(out_lines, plot = p_lines, width = 9, height = 5.6, dpi = 600, bg = "white")
message("Wrote ", out_lines)

# --- (2) grouped bars: metric x SC share -----------------------------------
p_bars <- ggplot(plot_df, aes(x = metric, y = score_pct, fill = scenario)) +
  geom_col(position = position_dodge(width = 0.78), width = 0.68, colour = "white", linewidth = 0.45) +
  geom_text(
    aes(label = sprintf("%.0f", score_pct)),
    position = position_dodge(width = 0.78),
    vjust = -0.5, size = 2.5, fontface = "bold", colour = "#4D2D18"
  ) +
  scale_fill_manual(
    values = SCENARIO_COLOURS,
    labels = SCENARIO_LABELS[SCENARIO_ORDER],
    name = "Self-collected share"
  ) +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 25),
    expand = expansion(mult = c(0, 0.10))
  ) +
  labs(
    title = "YOLO + Qwen: binary metrics by self-collected training share",
    subtitle = SUBTITLE,
    caption = paste0(CAPTION, " Fill runs from light (0% SC) to dark brown (100% SC / baseline)."),
    x = NULL,
    y = "Score (%)"
  ) +
  base_theme() +
  theme(panel.grid.major.x = element_blank())

out_bars <- file.path(FIG_DIR, "3_Heldout_validation_binary_bars.png")
ggsave(out_bars, plot = p_bars, width = 9, height = 5.6, dpi = 600, bg = "white")
message("Wrote ", out_bars)

message("Done.")

#!/usr/bin/env Rscript
# Step 3 figure 4 — YOLO only vs YOLO + Qwen, by self-collected training share.
#   4_Heldout_validation_stage_metrics.png  lines: one facet per metric, one line per stage
#   4_Heldout_validation_stage_bars.png     grouped bars: stage pairs within each SC share
# Input: thesis_table/table_4_sc_sensitivity_detail.csv (1_heldout_metrics.py)
#
# Companion to 3plot_sc_sensitivity.R, which shows the cascade alone. Here both
# stages appear together so the size of the VLM gain can be read off at every
# training mix.

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

# Same stage palette as figure 1 (1plot_heldout_panel.R).
STAGE_ORDER <- c("YOLO only", "YOLO + Qwen")
STAGE_COLOURS <- c("YOLO only" = "#C9A27F", "YOLO + Qwen" = "#5F6F5A")

METRIC_KEYS <- c("accuracy_pct", "precision_pct", "recall_pct", "f1_pct")
METRIC_LABELS <- c(
  "accuracy_pct" = "Accuracy",
  "precision_pct" = "Precision",
  "recall_pct" = "Recall",
  "f1_pct" = "F1"
)

# ---------------------------------------------------------------------------
detail <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)

SCENARIO_ORDER <- scenario_levels(detail)
SCENARIO_LABELS <- share_labels(detail, SCENARIO_ORDER)

both <- detail |>
  mutate(
    stage_label = factor(
      ifelse(grepl("Qwen", stage, fixed = TRUE), "YOLO + Qwen", "YOLO only"),
      levels = STAGE_ORDER
    ),
    scenario = factor(scenario, levels = SCENARIO_ORDER)
  )

incomplete <- both |>
  count(scenario, .drop = FALSE) |>
  filter(n < 2)
if (nrow(incomplete)) {
  stop(
    "Both stages needed; only one for: ", paste(incomplete$scenario, collapse = ", "),
    ". Run 3_waste_identification/2_qwen_review.py to label those scenarios first."
  )
}

n_images <- unique(both$tp + both$fp + both$tn + both$fn)
n_waste <- unique(both$tp + both$fn)
n_background <- unique(both$fp + both$tn)
stopifnot(length(n_images) == 1)

plot_df <- both |>
  select(scenario, sc_share_pct, stage_label, all_of(METRIC_KEYS)) |>
  pivot_longer(all_of(METRIC_KEYS), names_to = "metric_key", values_to = "score_pct") |>
  mutate(metric = factor(metric_key, levels = METRIC_KEYS, labels = METRIC_LABELS[METRIC_KEYS]))

# Gain from the VLM pass, for the arrows / labels between the two stages.
gain_df <- plot_df |>
  select(scenario, sc_share_pct, metric, stage_label, score_pct) |>
  pivot_wider(names_from = stage_label, values_from = score_pct) |>
  mutate(gain = `YOLO + Qwen` - `YOLO only`)

SHARES <- sort(unique(both$sc_share_pct))
SUBTITLE <- sprintf(
  "Independent GSVI held-out set: %s images (%s waste + %s background) | %d retrained detectors, scored before and after the Qwen2-VL pass",
  comma(n_images), comma(n_waste), comma(n_background), length(SCENARIO_ORDER)
)
CAPTION <- paste0(
  "YOLO + Qwen keeps a YOLO positive only when Qwen2-VL also answers Yes, so it can only remove positives: precision rises, recall falls.\n",
  replicate_note(both)
)

base_theme <- function() {
  map_theme() +
    theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
      plot.caption = element_text(size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8)),
      axis.text = element_text(colour = "#4D2D18"),
      axis.title = element_text(size = 9.5, colour = "#4D2D18"),
      strip.text = element_text(size = 10, face = "bold", colour = "#4D2D18"),
      legend.position = "bottom",
      legend.justification = "center",
      legend.background = element_blank(),
      legend.box.background = element_blank(),
      legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
      legend.text = element_text(size = 9, colour = "#4D2D18"),
      legend.margin = margin(t = 4)
    )
}

# --- (1) lines: one facet per metric, both stages ---------------------------
p_lines <- ggplot(plot_df, aes(x = sc_share_pct, y = score_pct, colour = stage_label, group = stage_label)) +
  geom_segment(
    data = gain_df,
    aes(x = sc_share_pct, xend = sc_share_pct, y = `YOLO only`, yend = `YOLO + Qwen`),
    inherit.aes = FALSE, colour = "grey72", linewidth = 0.35, linetype = "22"
  ) +
  geom_line(linewidth = 0.9) +
  geom_point(size = 2.4) +
  geom_text(
    aes(label = sprintf("%.0f", score_pct)),
    size = 2.4, fontface = "bold", vjust = -1.1, show.legend = FALSE
  ) +
  facet_wrap(~metric, nrow = 1) +
  scale_x_continuous(
    breaks = SHARES,
    labels = sprintf("%g", SHARES),
    limits = range(SHARES) + c(-6, 6),
    expand = expansion(mult = c(0.02, 0.02))
  ) +
  scale_y_continuous(
    limits = c(65, 100),
    breaks = seq(70, 100, 10),
    expand = expansion(mult = c(0.03, 0.10))
  ) +
  scale_colour_manual(values = STAGE_COLOURS, name = "Stage") +
  labs(
    title = "YOLO only vs YOLO + Qwen, by self-collected training share",
    subtitle = SUBTITLE,
    caption = CAPTION,
    x = "Self-collected share of the YOLO training set (%)",
    y = "Score (%)"
  ) +
  base_theme() +
  theme(panel.grid.major.x = element_line(colour = "grey92", linewidth = 0.25))

out_lines <- file.path(FIG_DIR, "4_Heldout_validation_stage_metrics.png")
ggsave(out_lines, plot = p_lines, width = 11, height = 5.4, dpi = 600, bg = "white")
message("Wrote ", out_lines)

# --- (2) grouped bars: stage pairs within each SC share ---------------------
bar_df <- plot_df |>
  mutate(scenario_label = factor(
    SCENARIO_LABELS[as.character(scenario)],
    levels = SCENARIO_LABELS[SCENARIO_ORDER]
  ))

p_bars <- ggplot(bar_df, aes(x = scenario_label, y = score_pct, fill = stage_label)) +
  geom_col(position = position_dodge(width = 0.76), width = 0.66, colour = "white", linewidth = 0.4) +
  geom_text(
    aes(label = sprintf("%.0f", score_pct)),
    position = position_dodge(width = 0.76),
    vjust = -0.45, size = 2.3, fontface = "bold", colour = "#4D2D18"
  ) +
  facet_wrap(~metric, nrow = 1) +
  scale_fill_manual(values = STAGE_COLOURS, name = "Stage") +
  scale_y_continuous(
    limits = c(0, 100),
    breaks = seq(0, 100, 25),
    expand = expansion(mult = c(0, 0.12))
  ) +
  labs(
    title = "YOLO only vs YOLO + Qwen, by self-collected training share",
    subtitle = SUBTITLE,
    caption = CAPTION,
    x = "Self-collected share of the YOLO training set (%)",
    y = "Score (%)"
  ) +
  base_theme() +
  theme(
    panel.grid.major.x = element_blank(),
    axis.text.x = element_text(size = 8)
  )

out_bars <- file.path(FIG_DIR, "4_Heldout_validation_stage_bars.png")
ggsave(out_bars, plot = p_bars, width = 11, height = 5.4, dpi = 600, bg = "white")
message("Wrote ", out_bars)

# Console summary of the VLM gain, so the figure can be sanity-checked.
message("\nVLM gain (percentage points), YOLO + Qwen minus YOLO only:")
print(
  gain_df |>
    select(scenario, metric, gain) |>
    pivot_wider(names_from = metric, values_from = gain) |>
    as.data.frame(),
  row.names = FALSE, digits = 3
)

message("Done.")

#!/usr/bin/env Rscript
# Step 3 figure 2 — repeated-inference stability of Qwen2-VL on YOLO positives
#   Top: metrics for YOLO only, each of three Qwen runs, and the 3-run majority
#   Bottom: Yes/No votes, unanimity donut, pairwise agreement
# Input: thesis_table/table_3_qwen_replicates.csv (1_heldout_metrics.py)

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
STAB_CSV <- file.path(THESIS_DIR, "table_3_qwen_replicates.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_waste_identification")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(STAB_CSV)) {
  stop("Missing ", STAB_CSV, " — run 3_waste_identification/1_heldout_metrics.py first")
}

# Metrics: YOLO | Run 1 | Run 2 | Run 3 | 3-run majority
# Bottom: Yes/No votes, unanimity, pairwise agreement (full YOLO+ re-runs)
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

out_stab <- file.path(FIG_DIR, "2_Heldout_qwen_replicate_stability.png")
ggsave(out_stab, stab_fig, width = 12.8, height = 8.2, dpi = 600, bg = "white")
message("Wrote ", out_stab)
message("Done.")

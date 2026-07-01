#!/usr/bin/env Rscript
# Self-collected overlap (n = 133) — binary vs 3-class, GSVI vs G+Self

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(cowplot)
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

BINARY_KEYS <- c("binary_accuracy", "binary_precision", "binary_recall", "binary_f1")
SEVERITY_KEYS <- c("severity_accuracy", "severity_precision", "severity_recall", "severity_f1")
METRIC_LEVELS <- c("Accuracy", "Precision", "Recall", "F1")

ARM_LEVELS <- c("GSVI", "G+Self")
BAR_WIDTH <- 0.11
PAIR_GAP <- 0.08
BRACKET_Y <- -5
BRACKET_LABEL_Y <- -9

# Lightness = task (binary light, 3-class dark); hue = arm (brown GSVI, green G+Self)
LIGHT_GSVI <- "#C9A27F"
LIGHT_GSC <- "#A8B8A3"
DARK_GSVI <- "#6B4226"
DARK_GSC <- "#496142"

SERIES_LEVELS <- c(
  "Binary, GSVI",
  "Binary, G+Self",
  "3-class, GSVI",
  "3-class, G+Self"
)
SERIES_COLOURS <- c(LIGHT_GSVI, LIGHT_GSC, DARK_GSVI, DARK_GSC)
names(SERIES_COLOURS) <- SERIES_LEVELS
SERIES_LABELS <- c(
  "Binary, GSVI" = "Binary, GSVI (Google only)",
  "Binary, G+Self" = "Binary, G+Self (Google + self-collected)",
  "3-class, GSVI" = "3-class, GSVI (Google only)",
  "3-class, G+Self" = "3-class, G+Self (Google + self-collected)"
)

assign_bar_x <- function(metric_num, task, arm) {
  is_binary <- task == "Binary"
  is_gsvi <- arm == "GSVI"
  offset <- ifelse(
    is_binary,
    ifelse(is_gsvi, -0.20 - PAIR_GAP / 2, -0.07 - PAIR_GAP / 2),
    ifelse(is_gsvi, 0.07 + PAIR_GAP / 2, 0.20 + PAIR_GAP / 2)
  )
  metric_num + offset
}

prepare_overlap_plot_data <- function(df) {
  arms <- df |>
    mutate(
      arm = case_when(
        grepl("^GSVI", predictor) ~ "GSVI",
        grepl("^G\\+Self", predictor) ~ "G+Self",
        TRUE ~ predictor
      ),
      arm = factor(arm, levels = ARM_LEVELS)
    )

  binary_long <- arms |>
    select(arm, all_of(BINARY_KEYS)) |>
    pivot_longer(-arm, names_to = "metric_key", values_to = "score") |>
    mutate(task = "Binary")

  severity_long <- arms |>
    select(arm, all_of(SEVERITY_KEYS)) |>
    pivot_longer(-arm, names_to = "metric_key", values_to = "score") |>
    mutate(task = "3-class")

  bind_rows(binary_long, severity_long) |>
    mutate(
      score_pct = score * 100,
      metric = factor(
        metric_key,
        levels = c(BINARY_KEYS, SEVERITY_KEYS),
        labels = rep(METRIC_LEVELS, 2)
      ),
      metric_num = as.numeric(metric),
      bar_x = assign_bar_x(metric_num, task, as.character(arm)),
      series = factor(
        paste(task, as.character(arm), sep = ", "),
        levels = SERIES_LEVELS
      )
    )
}

build_chart <- function(plot_df) {
  bracket_df <- plot_df |>
    group_by(metric, metric_num) |>
    summarise(
      binary_xmin = min(bar_x[task == "Binary"]) - BAR_WIDTH * 0.75,
      binary_xmax = max(bar_x[task == "Binary"]) + BAR_WIDTH * 0.75,
      sev_xmin = min(bar_x[task == "3-class"]) - BAR_WIDTH * 0.75,
      sev_xmax = max(bar_x[task == "3-class"]) + BAR_WIDTH * 0.75,
      binary_x = mean(bar_x[task == "Binary"]),
      sev_x = mean(bar_x[task == "3-class"]),
      .groups = "drop"
    )

  bg_binary <- bracket_df |>
    mutate(group = "Binary") |>
    transmute(metric_num, xmin = binary_xmin, xmax = binary_xmax, group)
  bg_sev <- bracket_df |>
    mutate(group = "3-class") |>
    transmute(metric_num, xmin = sev_xmin, xmax = sev_xmax, group)
  bg_df <- bind_rows(bg_binary, bg_sev) |>
    mutate(bg_fill = if_else(group == "Binary", LIGHT_GSVI, DARK_GSVI))

  ggplot() +
    geom_rect(
      data = bg_df,
      aes(xmin = xmin, xmax = xmax, ymin = 0, ymax = 100),
      fill = alpha(bg_df$bg_fill, 0.06),
      colour = NA
    ) +
    scale_fill_manual(
      values = SERIES_COLOURS,
      labels = SERIES_LABELS,
      name = NULL
    ) +
    geom_col(
      data = plot_df,
      aes(x = bar_x, y = score_pct, fill = series),
      width = BAR_WIDTH,
      colour = "white",
      linewidth = 0.45
    ) +
    geom_text(
      data = plot_df,
      aes(x = bar_x, y = score_pct, label = sprintf("%.1f%%", score_pct)),
      vjust = -0.35,
      size = 2.7,
      fontface = "bold",
      colour = "#3d2b1f"
    ) +
    geom_segment(
      data = bracket_df,
      aes(
        x = binary_x - 0.12,
        xend = binary_x + 0.12,
        y = BRACKET_Y,
        yend = BRACKET_Y
      ),
      linewidth = 0.35,
      colour = "#9A8578"
    ) +
    geom_segment(
      data = bracket_df,
      aes(
        x = sev_x - 0.12,
        xend = sev_x + 0.12,
        y = BRACKET_Y,
        yend = BRACKET_Y
      ),
      linewidth = 0.35,
      colour = "#9A8578"
    ) +
    geom_text(
      data = bracket_df,
      aes(x = binary_x, y = BRACKET_LABEL_Y, label = "Binary"),
      size = 3.0,
      colour = "#6B5B4F"
    ) +
    geom_text(
      data = bracket_df,
      aes(x = sev_x, y = BRACKET_LABEL_Y, label = "3-class"),
      size = 3.0,
      colour = "#6B5B4F"
    ) +
    guides(fill = guide_legend(nrow = 1)) +
    coord_cartesian(ylim = c(0, 100), clip = "off") +
    scale_x_continuous(
      breaks = unique(plot_df$metric_num),
      labels = METRIC_LEVELS,
      expand = expansion(mult = c(0.08, 0.08))
    ) +
    scale_y_continuous(
      breaks = seq(0, 100, 25),
      expand = expansion(mult = c(0, 0.05))
    ) +
    labs(x = NULL, y = "Score (%)") +
    map_theme() +
    theme(
      legend.position = "top",
      legend.justification = "center",
      legend.direction = "horizontal",
      legend.background = element_blank(),
      legend.box.background = element_blank(),
      legend.box.margin = margin(0, 0, 0, 0),
      legend.text = element_text(size = 8, colour = "#4D2D18"),
      legend.key.size = unit(0.38, "cm"),
      legend.key.width = unit(0.38, "cm"),
      legend.spacing.x = unit(0.15, "cm"),
      legend.margin = margin(t = 0, r = 0, b = 2, l = 0),
      axis.text.x = element_text(size = 10, colour = "#4D2D18", margin = margin(t = 18)),
      axis.text.y = element_text(size = 8.5),
      axis.title.y = element_text(size = 9.5, colour = "#4D2D18"),
      panel.grid.major.x = element_blank(),
      plot.margin = margin(t = 0, r = 12, b = 28, l = 8)
    )
}

message("Reading tables...")
comparison <- read.csv(COMPARISON_CSV, stringsAsFactors = FALSE)
overlap <- comparison |> filter(subset == "Self-collected SVI overlap")

if (nrow(overlap) != 2) {
  stop("Expected two rows for self-collected overlap subset.", call. = FALSE)
}

n_cells <- unique(overlap$n_cells)
plot_df <- prepare_overlap_plot_data(overlap)

p_chart <- build_chart(plot_df)

title_grob <- ggdraw() +
  draw_label(
    sprintf(
      "Mitigation: crowd validation at self-collected SVI overlap (n = %s)",
      comma(n_cells)
    ),
    fontface = "bold",
    size = 12.5,
    colour = "#2f2f2f",
    x = 0.5,
    hjust = 0.5,
    y = 0.35
  )

caption_text <- paste0(
  "Binary: waste present vs absent. ",
  "3-class: low, middle, high chance of seeing visible waste piles."
)

caption_grob <- ggdraw() +
  draw_label(
    caption_text,
    size = 8.5,
    colour = "#7A6A5C",
    x = 0,
    hjust = 0,
    y = 1,
    lineheight = 1.2
  )


panel <- plot_grid(
  title_grob,
  p_chart,
  caption_grob,
  ncol = 1,
  rel_heights = c(0.055, 1, 0.09),
  align = "v",
  axis = "l"
)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
out_path <- file.path(FIG_DIR, "Validation_mitigation_self_overlap.png")
ggsave(out_path, plot = panel, width = 12, height = 5.8, dpi = 600, bg = "white")
message("Wrote ", out_path)
message("Done.")

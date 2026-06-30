#!/usr/bin/env Rscript
# Stacked bar — self-collected waste split: inside vs outside existing GSVI hotspots

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
MITIGATION_DIR <- file.path(DATA_ROOT, "3_cluster_mitigation")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_cluster_mitigation")

NEW_OBS_TABLE <- file.path(MITIGATION_DIR, "thesis_table", "Nairobi_mitigation_new_observations_table.csv")
OUT_PATH <- file.path(FIG_DIR, "Mitigation_new_obs_stacked_bar.png")

INSIDE_COLOUR <- "#C9A27F"
NEW_HOTSPOT_COLOUR <- "#6B4226"
AXIS_COLOUR <- "#4D2D18"

parse_count <- function(value) {
  as.integer(sub("^([0-9,]+).*", "\\1", value))
}

parse_percent <- function(value) {
  pct <- sub(".*\\(([0-9.]+)%\\).*", "\\1", value)
  as.numeric(pct)
}

load_new_obs_split <- function(path) {
  tbl <- read.csv(path, stringsAsFactors = FALSE)

  inside_row <- tbl[tbl$Metric == "New observations inside existing hotspots", , drop = FALSE]
  new_row <- tbl[tbl$Metric == "New observations forming new hotspots", , drop = FALSE]
  total_row <- tbl[tbl$Metric == "New observations added", , drop = FALSE]

  inside_n <- parse_count(inside_row$Value)
  new_n <- parse_count(new_row$Value)
  total_n <- parse_count(total_row$Value)

  tibble(
    segment = c(
      "Inside existing hotspots",
      "Forming new hotspots"
    ),
    n = c(inside_n, new_n),
    pct = c(parse_percent(inside_row$Value), parse_percent(new_row$Value)),
    total_n = total_n
  ) |>
    mutate(
      segment = factor(
        segment,
        levels = c("Forming new hotspots", "Inside existing hotspots")
      ),
      label = sprintf("%s\n(%s%%)", comma(n), format(round(pct, 1), nsmall = 1))
    )
}

build_stacked_bar <- function(plot_df, total_n) {
  ggplot(plot_df, aes(x = n, y = "Self-collected SVI identified waste", fill = segment)) +
    geom_col(
      width = 0.52,
      linewidth = 0.35,
      colour = "white"
    ) +
    geom_text(
      aes(label = label),
      position = position_stack(vjust = 0.5),
      size = 4.1,
      fontface = "bold",
      colour = "white",
      lineheight = 0.92
    ) +
    scale_fill_manual(
      name = NULL,
      values = c(
        "Inside existing hotspots" = INSIDE_COLOUR,
        "Forming new hotspots" = NEW_HOTSPOT_COLOUR
      ),
      breaks = c("Inside existing hotspots", "Forming new hotspots")
    ) +
    scale_x_continuous(
      expand = expansion(mult = c(0, 0.02)),
      breaks = pretty_breaks(n = 4)
    ) +
    labs(
      title = "Self-collected waste added to GSVI detections",
      subtitle = sprintf(
        "New observations added (n = %s) split by overlap with existing GSVI hotspot hulls",
        comma(total_n)
      ),
      x = "Number of observations",
      y = NULL
    ) +
    theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      plot.title = element_text(
        face = "bold",
        size = 14,
        hjust = 0.5,
        colour = "#2f2f2f",
        margin = margin(b = 4)
      ),
      plot.subtitle = element_text(
        size = 10.5,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 10)
      ),
      axis.title.x = element_text(colour = AXIS_COLOUR, size = 11, margin = margin(t = 8)),
      axis.text = element_text(colour = AXIS_COLOUR, size = 10),
      axis.text.y = element_text(
        face = "bold",
        size = 11,
        colour = "#2f2f2f",
        angle = 90,
        hjust = 0.5,
        vjust = 0.5
      ),
      panel.grid.major.y = element_blank(),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_line(colour = "grey90", linewidth = 0.3),
      legend.position = "bottom",
      legend.text = element_text(size = 10, colour = "#2f2f2f"),
      legend.key.height = unit(0.45, "cm"),
      legend.key.width = unit(0.7, "cm"),
      plot.margin = margin(12, 16, 12, 20)
    )
}

if (!file.exists(NEW_OBS_TABLE)) {
  stop(
    "Missing ", NEW_OBS_TABLE,
    "\nRun: python 3_cluster_mitigation/4_mitigation_comparison.py"
  )
}

plot_df <- load_new_obs_split(NEW_OBS_TABLE)
total_n <- plot_df$total_n[1]

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

p <- build_stacked_bar(plot_df, total_n)
ggsave(OUT_PATH, plot = p, width = 9, height = 4.5, dpi = 600, bg = "white")
message("Wrote ", OUT_PATH)

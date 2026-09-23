#!/usr/bin/env Rscript
# Stacked bar: HDBSCAN cluster composition by distance to urban-poor boundary
# Ported from del/SVI_distance_use.ipynb (cell ~95); panoid-level clusters.

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(readr)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
DATA_ROOT <- chapter_data_root
CLUSTER_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "HDBSCAN")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "HDBSCAN")

# Stack bottom → top (flipped vs original notebook; outside at bottom, inside on top)
DISTANCE_LEVELS <- c(
  ">500m outside",
  "250-500m buffer",
  "0-250m buffer",
  "Within Urban Poor"
)
DIST_COLOURS <- c(
  ">500m outside" = "#fbf5ee",
  "250-500m buffer" = "#e4c8b0",
  "0-250m buffer" = "#ad8260",
  "Within Urban Poor" = "#7b5032"
)
# Legend: nearest settlement first (top of bar / darkest)
LEGEND_ORDER <- rev(DISTANCE_LEVELS)
AXIS_COLOUR <- "#4D2D18"

SPECS <- list(
  list(
    tag = "gsvi",
    prop_csv = "Nairobi_hdbscan_cluster_distance_composition_gsvi.csv",
    title = "Cluster Composition by Distance to Urban Poor Boundary",
    subtitle = "GSVI waste-positive panoids (share of panoids per HDBSCAN cluster)"
  )
)

load_prop_long <- function(path) {
  prop <- read_csv(path, show_col_types = FALSE)
  stopifnot("HDB_cluster" %in% names(prop))
  missing_cols <- setdiff(DISTANCE_LEVELS, names(prop))
  for (col in missing_cols) {
    prop[[col]] <- 0
  }
  # Preserve sort from Python (Within Urban Poor descending)
  prop <- prop |>
    mutate(
      HDB_cluster = factor(HDB_cluster, levels = HDB_cluster)
    )
  prop |>
    pivot_longer(
      cols = all_of(DISTANCE_LEVELS),
      names_to = "distance_category",
      values_to = "proportion"
    ) |>
    mutate(
      distance_category = factor(distance_category, levels = DISTANCE_LEVELS)
    )
}

build_stacked_bar <- function(plot_df, title, subtitle) {
  ggplot(plot_df, aes(x = HDB_cluster, y = proportion, fill = distance_category)) +
    geom_col(
      width = 0.88,
      colour = alpha("grey60", 0.25),
      linewidth = 0.12,
      position = "stack"
    ) +
    scale_fill_manual(
      name = "Distance Category",
      values = DIST_COLOURS,
      breaks = LEGEND_ORDER
    ) +
    scale_y_continuous(
      labels = percent_format(accuracy = 1),
      limits = c(0, 1),
      expand = expansion(mult = c(0, 0.02)),
      breaks = seq(0, 1, by = 0.2)
    ) +
    labs(
      title = title,
      subtitle = subtitle,
      x = "HDBSCAN Cluster Label",
      y = "Proportion of Points"
    ) +
    guides(
      fill = guide_legend(
        nrow = 1,
        byrow = TRUE,
        title.position = "left",
        title.vjust = 0.55,
        label.position = "right",
        keywidth = unit(0.55, "cm"),
        keyheight = unit(0.4, "cm")
      )
    ) +
    theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      plot.title = element_text(
        face = "bold",
        size = 13.5,
        hjust = 0.5,
        colour = "#2f2f2f",
        margin = margin(b = 3)
      ),
      plot.subtitle = element_text(
        size = 10,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 6)
      ),
      axis.title = element_text(colour = AXIS_COLOUR, size = 11),
      axis.title.x = element_text(margin = margin(t = 8)),
      axis.title.y = element_text(margin = margin(r = 8)),
      axis.text.x = element_text(
        colour = AXIS_COLOUR,
        size = 8,
        angle = 45,
        hjust = 1,
        vjust = 1
      ),
      axis.text.y = element_text(colour = AXIS_COLOUR, size = 10),
      panel.grid.major.x = element_blank(),
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_line(
        colour = "grey85",
        linewidth = 0.35,
        linetype = "dashed"
      ),
      panel.background = element_rect(fill = "white", colour = NA),
      plot.background = element_rect(fill = "white", colour = NA),
      # Single-row boxed legend under subtitle
      legend.position = "top",
      legend.direction = "horizontal",
      legend.justification = "center",
      legend.title = element_text(size = 9.5, face = "bold", colour = "#2f2f2f"),
      legend.text = element_text(size = 9, colour = "#2f2f2f"),
      legend.background = element_rect(
        fill = alpha("white", 0.96),
        colour = "grey78",
        linewidth = 0.35
      ),
      legend.box.background = element_blank(),
      legend.box.margin = margin(2, 6, 2, 6),
      legend.margin = margin(2, 6, 2, 6),
      legend.spacing.x = unit(0.35, "cm"),
      plot.margin = margin(10, 12, 10, 12)
    )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

for (spec in SPECS) {
  prop_path <- file.path(CLUSTER_DIR, spec$prop_csv)
  if (!file.exists(prop_path)) {
    stop(
      "Missing ", prop_path, "\n",
      "Run: python 5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py"
    )
  }
  message("Building composition bar: ", spec$tag)
  plot_df <- load_prop_long(prop_path)
  p <- build_stacked_bar(plot_df, spec$title, spec$subtitle)
  # Near-square canvas (not wide landscape)
  n_bars <- n_distinct(plot_df$HDB_cluster)
  width <- 8.0
  height <- 7.6
  out_path <- file.path(
    FIG_DIR, paste0("Cluster_Composition_By_Distance_", spec$tag, ".png")
  )
  ggsave(out_path, plot = p, width = width, height = height, dpi = 600, bg = "white")
  message("  ", basename(out_path), " (", width, " x ", height, " in)")
}

message("Done.")

#!/usr/bin/env Rscript
# Two-panel cluster-size figure (violin Inside/Outside + size histogram)
# Ported from del/SVI_distance_use.ipynb (~cell 102) and
# del/SVI_PPP_Stats_USE.ipynb (~cells 69–74).

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(readr)
  library(scales)
  library(patchwork)
  library(grid)
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

MIN_CLUSTER_SIZE <- 25L
AXIS_COLOUR <- "#1F120C"  # dark dark brown for axis titles + tick labels
MEAN_LINE_COLOUR <- "#112721"
TITLE_COLOUR <- "#1F120C"

TYPE_ASSOCIATED <- "Associated with urban-poor settlements"
TYPE_OTHER <- "Other clusters"
TYPE_LEVELS <- c(TYPE_ASSOCIATED, TYPE_OTHER)
TYPE_COLOURS <- setNames(
  c("#ac8260", "#ebdbce"),
  TYPE_LEVELS
)
TYPE_AXIS_LABELS <- c(
  "Associated with\nurban-poor settlements",
  "Other clusters"
)

SPECS <- list(
  list(
    tag = "gsvi",
    sizes_csv = "Nairobi_hdbscan_cluster_sizes_gsvi.csv",
    summary_csv = "Nairobi_hdbscan_cluster_size_summary_gsvi.csv",
    subtitle = "GSVI waste-positive panoramas"
  ),
  list(
    tag = "gsvi_selfcollected",
    sizes_csv = "Nairobi_hdbscan_cluster_sizes_gsvi_selfcollected.csv",
    summary_csv = "Nairobi_hdbscan_cluster_size_summary_gsvi_selfcollected.csv",
    subtitle = "GSVI panoramas + self-collected locations"
  )
)

panel_theme <- function() {
  theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      plot.title = element_text(
        face = "bold",
        size = 12.5,
        hjust = 0.5,
        colour = TITLE_COLOUR,
        lineheight = 1.1,
        margin = margin(b = 4)
      ),
      plot.subtitle = element_text(
        size = 8.5,
        hjust = 0.5,
        colour = AXIS_COLOUR,
        lineheight = 1.1,
        margin = margin(b = 8)
      ),
      axis.title = element_text(colour = AXIS_COLOUR, size = 11),
      axis.title.x = element_text(colour = AXIS_COLOUR, margin = margin(t = 8)),
      axis.title.y = element_text(colour = AXIS_COLOUR, margin = margin(r = 8)),
      axis.text = element_text(colour = AXIS_COLOUR, size = 10),
      axis.text.x = element_text(colour = AXIS_COLOUR),
      axis.text.y = element_text(colour = AXIS_COLOUR),
      axis.ticks = element_line(colour = AXIS_COLOUR),
      panel.grid.major.x = element_blank(),
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_line(
        colour = "grey85",
        linewidth = 0.35,
        linetype = "dashed"
      ),
      panel.background = element_rect(fill = "white", colour = NA),
      plot.background = element_rect(fill = "white", colour = NA),
      plot.margin = margin(10, 12, 14, 12)
    )
}

load_sizes <- function(path) {
  read_csv(path, show_col_types = FALSE) |>
    mutate(
      cluster_type = recode(
        as.character(cluster_type),
        "Inside Slums" = TYPE_ASSOCIATED,
        "Outside Slums" = TYPE_OTHER,
        .default = as.character(cluster_type)
      ),
      cluster_type = factor(cluster_type, levels = TYPE_LEVELS)
    )
}

load_summary <- function(path) {
  read_csv(path, show_col_types = FALSE)
}

type_stats <- function(sizes) {
  sizes |>
    group_by(cluster_type) |>
    summarise(
      n = n(),
      mean = mean(n_points),
      q25 = quantile(n_points, 0.25),
      q75 = quantile(n_points, 0.75),
      .groups = "drop"
    ) |>
    complete(cluster_type = factor(TYPE_LEVELS, levels = TYPE_LEVELS)) |>
    mutate(
      n = replace_na(n, 0L),
      mean = replace_na(mean, NA_real_),
      q25 = replace_na(q25, NA_real_),
      q75 = replace_na(q75, NA_real_)
    )
}

violin_summary_label <- function(stats) {
  box_names <- c(
    "Associated with urban-poor settlements" = "Associated",
    "Other clusters" = "Other clusters"
  )
  blocks <- list()
  for (i in seq_len(nrow(stats))) {
    row <- stats[i, ]
    if (is.na(row$mean) || row$n == 0) next
    nm <- as.character(row$cluster_type)
    if (nm %in% names(box_names)) nm <- box_names[[nm]]
    blocks[[length(blocks) + 1L]] <- paste(
      nm,
      sprintf("Mean: %.1f", row$mean),
      sprintf("25\u201375%%: %.0f\u2013%.0f", row$q25, row$q75),
      sep = "\n"
    )
  }
  paste(blocks, collapse = "\n\n")
}

hist_summary_label <- function(summary_df) {
  n_clusters <- summary_df$n_clusters[[1]]
  n_clustered <- summary_df$n_clustered[[1]]
  n_noise <- summary_df$n_noise[[1]]
  n_points <- summary_df$n_points[[1]]
  noise_pct <- 100 * summary_df$noise_ratio[[1]]
  sil <- summary_df$silhouette_score[[1]]
  paste0(
    "Clusters: ", n_clusters, "\n",
    "Clustered panoramas: ", format(n_clustered, big.mark = ","), "\n",
    "Unclustered panoramas: ", format(n_noise, big.mark = ","), "/",
    format(n_points, big.mark = ","),
    sprintf(" (%.1f%%)\n", noise_pct),
    sprintf("Silhouette score: %.3f", sil)
  )
}

build_violin <- function(sizes, stats) {
  mean_df <- stats |>
    filter(n > 0, !is.na(mean)) |>
    mutate(
      x = as.numeric(cluster_type),
      x_start = x - 0.2,
      x_end = x + 0.2,
      label = sprintf("Mean = %.1f", mean)
    )

  n_df <- stats |>
    filter(n > 0) |>
    mutate(
      x = as.numeric(cluster_type),
      y = -0.05 * max(sizes$n_points, na.rm = TRUE),
      label = sprintf("n = %d", n)
    )

  y_max <- max(sizes$n_points, na.rm = TRUE)
  y_pad <- max(12, 0.08 * y_max)

  ggplot(sizes, aes(x = cluster_type, y = n_points, fill = cluster_type)) +
    geom_violin(
      trim = TRUE,
      scale = "width",
      colour = NA,
      alpha = 0.95,
      width = 0.9
    ) +
    geom_boxplot(
      width = 0.12,
      fill = "white",
      colour = "#333333",
      outlier.shape = NA,
      linewidth = 0.45,
      alpha = 0.95
    ) +
    geom_segment(
      data = mean_df,
      aes(x = x_start, xend = x_end, y = mean, yend = mean),
      inherit.aes = FALSE,
      colour = MEAN_LINE_COLOUR,
      linetype = "22",
      linewidth = 0.7
    ) +
    geom_text(
      data = mean_df,
      aes(x = x, y = mean, label = label),
      inherit.aes = FALSE,
      vjust = -0.45,
      size = 3.6,
      colour = MEAN_LINE_COLOUR
    ) +
    geom_text(
      data = n_df,
      aes(x = x, y = y, label = label),
      inherit.aes = FALSE,
      vjust = 1.1,
      size = 3.8,
      colour = AXIS_COLOUR
    ) +
    annotate(
      "label",
      x = Inf,
      y = Inf,
      label = violin_summary_label(stats),
      hjust = 1.05,
      vjust = 1.15,
      size = 3.3,
      lineheight = 1.05,
      label.padding = unit(0.35, "lines"),
      label.r = unit(0.15, "lines"),
      fill = alpha("white", 0.92),
      colour = "#333333",
      linewidth = 0.3
    ) +
    scale_fill_manual(values = TYPE_COLOURS, guide = "none") +
    scale_x_discrete(labels = TYPE_AXIS_LABELS) +
    scale_y_continuous(
      expand = expansion(mult = c(0.08, 0.08)),
      limits = c(-y_pad, NA)
    ) +
    coord_cartesian(clip = "off") +
    labs(
      title = "Distribution of cluster sizes",
      subtitle = paste0(
        "Associated with urban-poor settlements vs other clusters\n",
        "(associated = at least one panorama inside a settlement)"
      ),
      x = "Cluster type",
      y = "Number of waste-positive panoramas in cluster"
    ) +
    panel_theme() +
    theme(axis.text.x = element_text(colour = AXIS_COLOUR, size = 9, lineheight = 1.05))
}

build_histogram <- function(sizes, summary_df) {
  n_pts <- sizes$n_points
  # Target ~20 bins like the notebook; keep integer-friendly width
  binwidth <- max(5, ceiling(diff(range(n_pts)) / 20))
  dens <- density(n_pts, from = 0, to = max(n_pts) * 1.05, n = 512)
  # Scale density to histogram counts
  dens_df <- data.frame(x = dens$x, y = dens$y * length(n_pts) * binwidth)

  ggplot(sizes, aes(x = n_points)) +
    geom_histogram(
      binwidth = binwidth,
      boundary = 0,
      closed = "left",
      fill = "#d4b896",
      colour = "#8B5E3C",
      alpha = 0.85,
      linewidth = 0.25
    ) +
    geom_line(
      data = dens_df,
      aes(x = x, y = y),
      colour = "#8B5E3C",
      linewidth = 0.9,
      inherit.aes = FALSE
    ) +
    geom_vline(
      xintercept = MIN_CLUSTER_SIZE,
      colour = "#c1121f",
      linetype = "22",
      linewidth = 0.7
    ) +
    annotate(
      "label",
      x = Inf,
      y = Inf,
      label = hist_summary_label(summary_df),
      hjust = 1.05,
      vjust = 1.15,
      size = 3.3,
      lineheight = 1.1,
      label.padding = unit(0.35, "lines"),
      label.r = unit(0.15, "lines"),
      fill = alpha("white", 0.92),
      colour = "#333333",
      linewidth = 0.3
    ) +
    scale_x_continuous(expand = expansion(mult = c(0.01, 0.05))) +
    scale_y_continuous(
      expand = expansion(mult = c(0, 0.08)),
      breaks = pretty_breaks()
    ) +
    labs(
      title = "Distribution of HDBSCAN cluster sizes",
      subtitle = "(excluding unclustered panoramas)",
      x = "HDBSCAN cluster size (waste-positive panoramas)",
      y = "Number of HDBSCAN clusters"
    ) +
    panel_theme() +
    theme(panel.grid.major.x = element_line(
      colour = "grey90",
      linewidth = 0.3,
      linetype = "dashed"
    ))
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

for (spec in SPECS) {
  sizes_path <- file.path(CLUSTER_DIR, spec$sizes_csv)
  summary_path <- file.path(CLUSTER_DIR, spec$summary_csv)
  if (!file.exists(sizes_path) || !file.exists(summary_path)) {
    stop(
      "Missing cluster-size tables for ", spec$tag, ".\n",
      "Run: python 5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py"
    )
  }

  message("Building cluster-size panel: ", spec$tag)
  sizes <- load_sizes(sizes_path)
  summary_df <- load_summary(summary_path)
  stats <- type_stats(sizes)

  p_left <- build_violin(sizes, stats)
  p_right <- build_histogram(sizes, summary_df)
  combined <- p_left + p_right + plot_layout(widths = c(1, 1.05))

  out_path <- file.path(
    FIG_DIR, paste0("Cluster_Size_Distribution_", spec$tag, ".png")
  )
  ggsave(
    out_path,
    plot = combined,
    width = 13.2,
    height = 6.2,
    dpi = 600,
    bg = "white"
  )
  message("  ", basename(out_path))
}

message("Done.")

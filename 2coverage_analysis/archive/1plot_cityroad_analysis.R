#!/usr/bin/env Rscript
# Distribution analysis for city->road H3 metrics produced by 1cityroad.py
# Left: ggbetweenstats-style violin + box + jitter + mean/median markers
# Right: hrbrthemes-style histogram
#
# To add metrics later: extend METRIC_CATALOG, then edit DEFAULT_METRIC_COLUMNS
# (or pass --metrics=col_a,col_b).

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
  library(hrbrthemes)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/2coverage_analysis"
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")

GROUP_LABEL <- "H3 cells"

# ---------------------------------------------------------------------------
# Metric catalogue — add new entries here to make them available for plotting
# ---------------------------------------------------------------------------
METRIC_CATALOG <- list(
  road_length_density_km_per_km2 = list(
    title = "Road length density",
    xlab = "Road density (km/km\u00B2)",
    hist_bins = 28,
    color = "#69b3a2"
  ),
  road_coverage_ratio = list(
    title = "Road coverage ratio",
    xlab = "Coverage ratio (0\u20131)",
    hist_bins = 28,
    color = "#404080"
  ),
  road_intersection_density_per_km2 = list(
    title = "Intersection density",
    xlab = "Intersections per km\u00B2",
    hist_bins = 28,
    color = "#E07A5F"
  ),
  road_type_count = list(
    title = "Road type count",
    xlab = "Distinct road types",
    hist_bins = NULL,
    discrete = TRUE,
    color = "#8E6C8A"
  )
)

DEFAULT_METRIC_COLUMNS <- c(
  "road_length_density_km_per_km2",
  "road_coverage_ratio"
)

MEDIAN_COLOR <- "#D1495B"
MEAN_LINE_COLOR <- "#B8860B"
MEAN_POINT_COLOR <- "#1F1F1F"

parse_args <- function() {
  defaults <- list(
    h3_res = 8L,
    road_buffer = 50,
    roads_only = FALSE,
    metrics = DEFAULT_METRIC_COLUMNS
  )
  for (arg in commandArgs(trailingOnly = TRUE)) {
    if (grepl("^--h3-res=", arg)) defaults$h3_res <- as.integer(sub("^--h3-res=", "", arg))
    if (grepl("^--road-buffer-m=", arg)) defaults$road_buffer <- as.numeric(sub("^--road-buffer-m=", "", arg))
    if (identical(arg, "--roads-only")) defaults$roads_only <- TRUE
    if (grepl("^--metrics=", arg)) {
      defaults$metrics <- strsplit(sub("^--metrics=", "", arg), ",", fixed = TRUE)[[1]]
      defaults$metrics <- trimws(defaults$metrics)
      defaults$metrics <- defaults$metrics[nzchar(defaults$metrics)]
    }
  }
  defaults
}

file_tag <- function(h3_res, road_buffer) {
  sprintf("h3_res%d_buf%dm", h3_res, as.integer(road_buffer))
}

resolve_metric_specs <- function(columns) {
  missing <- setdiff(columns, names(METRIC_CATALOG))
  if (length(missing)) {
    stop(
      "Unknown metric column(s): ", paste(missing, collapse = ", "),
      "\nAvailable: ", paste(names(METRIC_CATALOG), collapse = ", ")
    )
  }
  lapply(columns, function(col) {
    spec <- METRIC_CATALOG[[col]]
    c(list(column = col), spec)
  })
}

panel_theme <- function() {
  theme_ipsum(base_size = 11) +
    theme(
      plot.background = element_rect(fill = "white", color = NA),
      panel.background = element_rect(fill = "#FCFCFC", color = NA),
      plot.title = element_text(face = "bold", size = 12.5, hjust = 0, color = "#222222"),
      plot.subtitle = element_text(size = 8.5, hjust = 0, color = "#666666", margin = margin(b = 6)),
      plot.tag = element_text(size = 12, face = "bold", color = "#222222"),
      plot.tag.position = c(0.02, 0.98),
      axis.title = element_text(size = 10, color = "#333333"),
      axis.text = element_text(size = 9, color = "#444444"),
      plot.margin = margin(10, 14, 8, 12)
    )
}

summarise_metric <- function(x) {
  x <- x[is.finite(x)]
  list(
    n = length(x),
    mean = mean(x),
    median = median(x),
    sd = sd(x)
  )
}

format_stat <- function(x, digits = 2) {
  if (abs(x - round(x)) < 1e-9) {
    return(as.character(as.integer(round(x))))
  }
  format(round(x, digits), nsmall = digits, trim = TRUE)
}

stats_caption <- function(stats) {
  sprintf(
    "n = %s  |  median = %s  |  mean = %s  |  sd = %s",
    comma(stats$n),
    format_stat(stats$median),
    format_stat(stats$mean),
    format_stat(stats$sd)
  )
}

# ggbetweenstats-style: violin + boxplot + jitter + mean diamond + median dot
plot_betweenstats_panel <- function(df, spec, stats, row_color, panel_tag) {
  plot_df <- df |>
    mutate(.group = GROUP_LABEL)

  ggplot(plot_df, aes(x = .group, y = .data[[spec$column]], fill = .group)) +
    geom_violin(
      trim = FALSE,
      alpha = 0.55,
      color = NA,
      width = 0.82,
      linewidth = 0
    ) +
    geom_boxplot(
      width = 0.13,
      fill = "white",
      color = "#333333",
      alpha = 0.92,
      outlier.shape = NA,
      linewidth = 0.45
    ) +
    geom_jitter(
      width = 0.08,
      size = 1.35,
      alpha = 0.20,
      color = "#252525"
    ) +
    geom_hline(yintercept = stats$median, color = MEDIAN_COLOR, linewidth = 0.7, linetype = "solid") +
    geom_hline(yintercept = stats$mean, color = MEAN_LINE_COLOR, linewidth = 0.55, linetype = "22") +
    stat_summary(
      fun = mean,
      geom = "point",
      shape = 18,
      size = 3.4,
      color = MEAN_POINT_COLOR
    ) +
    stat_summary(
      fun = median,
      geom = "point",
      shape = 21,
      size = 3.1,
      fill = "white",
      color = MEDIAN_COLOR,
      stroke = 0.75
    ) +
    scale_fill_manual(values = stats::setNames(row_color, GROUP_LABEL), guide = "none") +
    scale_y_continuous(labels = label_number(accuracy = 0.1), expand = expansion(mult = c(0.05, 0.08))) +
    labs(
      title = spec$title,
      subtitle = stats_caption(stats),
      tag = panel_tag,
      x = NULL,
      y = spec$xlab
    ) +
    panel_theme() +
    theme(
      axis.text.x = element_blank(),
      axis.ticks.x = element_blank(),
      panel.grid.major.x = element_blank()
    )
}

# hrbrthemes-style histogram
plot_histogram_panel <- function(df, spec, stats, row_color) {
  plot_df <- df |> mutate(.group = GROUP_LABEL)
  x_vals <- plot_df[[spec$column]]
  x_span <- diff(range(x_vals, na.rm = TRUE))
  if (!is.finite(x_span) || x_span == 0) x_span <- 1
  label_hjust <- if (stats$median >= max(x_vals, na.rm = TRUE) - 0.04 * x_span) 1.05 else -0.02

  hist_layer <- if (isTRUE(spec$discrete)) {
    geom_histogram(
      binwidth = 1,
      boundary = 0,
      closed = "left",
      color = "#e9ecef",
      alpha = 0.6,
      position = "identity"
    )
  } else {
    geom_histogram(
      bins = spec$hist_bins,
      color = "#e9ecef",
      alpha = 0.6,
      position = "identity"
    )
  }

  p <- ggplot(plot_df, aes(x = .data[[spec$column]], fill = .group)) +
    hist_layer +
    geom_vline(xintercept = stats$median, color = MEDIAN_COLOR, linewidth = 0.85, linetype = "solid") +
    geom_vline(xintercept = stats$mean, color = MEAN_LINE_COLOR, linewidth = 0.65, linetype = "22") +
    annotate(
      "label",
      x = stats$median,
      y = Inf,
      label = paste("Median", format_stat(stats$median)),
      vjust = 1.35,
      hjust = label_hjust,
      size = 3,
      fill = alpha("white", 0.95),
      linewidth = 0.25,
      label.padding = unit(0.18, "lines"),
      color = MEDIAN_COLOR,
      fontface = "bold"
    ) +
    annotate(
      "label",
      x = stats$mean,
      y = Inf,
      label = paste("Mean", format_stat(stats$mean)),
      vjust = 3.2,
      hjust = if (stats$mean >= max(x_vals, na.rm = TRUE) - 0.04 * x_span) 1.05 else -0.02,
      size = 3,
      fill = alpha("white", 0.95),
      linewidth = 0.25,
      label.padding = unit(0.18, "lines"),
      color = MEAN_LINE_COLOR,
      fontface = "bold"
    ) +
    scale_fill_manual(values = stats::setNames(row_color, GROUP_LABEL), guide = "none") +
    scale_y_continuous(labels = comma, expand = expansion(mult = c(0, 0.08))) +
    labs(x = spec$xlab, y = "H3 cells") +
    panel_theme() +
    theme(
      plot.title = element_blank(),
      plot.subtitle = element_blank(),
      plot.tag = element_blank()
    )

  if (isTRUE(spec$discrete)) {
    p <- p + scale_x_continuous(breaks = scales::breaks_width(1))
  } else if (spec$column == "road_coverage_ratio") {
    p <- p + scale_x_continuous(expand = expansion(mult = c(0.01, 0.04)))
  } else {
    p <- p + scale_x_continuous(expand = expansion(mult = c(0.02, 0.06)))
  }
  p
}

args <- parse_args()
tag <- file_tag(args$h3_res, args$road_buffer)
csv_path <- file.path(DATA_DIR, paste0("Nairobi_cityroad_grid_", tag, ".csv"))

if (!file.exists(csv_path)) {
  stop("Grid CSV not found: ", csv_path, "\nRun: python 2coverage_analysis/1cityroad.py")
}

grid <- read.csv(csv_path, stringsAsFactors = FALSE)
if (args$roads_only) {
  grid <- grid |> filter(.data$has_road == 1)
}

specs <- resolve_metric_specs(args$metrics)
row_plots <- vector("list", length(specs))

for (i in seq_along(specs)) {
  spec <- specs[[i]]
  if (!spec$column %in% names(grid)) {
    stop("Column not found in grid CSV: ", spec$column)
  }

  df <- grid |> filter(is.finite(.data[[spec$column]]))
  stats <- summarise_metric(df[[spec$column]])

  row_plots[[i]] <- plot_betweenstats_panel(df, spec, stats, spec$color, LETTERS[i]) |
    plot_histogram_panel(df, spec, stats, spec$color)
}

n_metrics <- length(specs)
fig_height <- max(7, 3.6 * n_metrics + 2.4)

col_header <- wrap_plots(
  ggplot() +
    annotate("text", x = 0.5, y = 0.5, label = "Distribution", fontface = "bold", size = 4.5, color = "#333333") +
    theme_void(),
  ggplot() +
    annotate("text", x = 0.5, y = 0.5, label = "Frequency", fontface = "bold", size = 4.5, color = "#333333") +
    theme_void(),
  ncol = 2
)

combined <- wrap_plots(row_plots, ncol = 1) +
  plot_annotation(
    title = "City to road H3 metric distributions",
    subtitle = sprintf(
      "Nairobi | H3 resolution %d | %dm road buffer | %s cells",
      args$h3_res,
      as.integer(args$road_buffer),
      if (args$roads_only) sprintf("%s with roads", comma(nrow(grid))) else sprintf("%s in city", comma(nrow(grid)))
    ),
    caption = paste(
      "Left: violin + boxplot + jitter  |  Right: histogram",
      "\nRed solid = median  |  Gold dashed = mean  |  \u25C6 = mean  |  \u25CB = median"
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 17, hjust = 0.5, color = "#222222", margin = margin(b = 4)),
      plot.subtitle = element_text(size = 10.5, hjust = 0.5, color = "#666666", margin = margin(b = 10)),
      plot.caption = element_text(size = 9, hjust = 0.5, color = "#777777", margin = margin(t = 8))
    )
  ) +
  plot_layout(heights = rep(1, n_metrics))

final <- col_header / combined +
  plot_layout(heights = c(0.045, 1))

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
out_path <- file.path(FIG_DIR, paste0("Nairobi_cityroad_analysis_", tag, ".png"))
ggsave(
  filename = out_path,
  plot = final,
  width = 11,
  height = fig_height,
  dpi = 320,
  bg = "white"
)

message("Wrote ", out_path)
message("Metrics plotted: ", paste(args$metrics, collapse = ", "))

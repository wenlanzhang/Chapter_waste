#!/usr/bin/env Rscript
# Plot city->road H3 metrics produced by cityroad.py

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/2coverage_analysis"
INPUT_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737

parse_args <- function() {
  defaults <- list(h3_res = 8, road_buffer = 50)
  args <- commandArgs(trailingOnly = TRUE)
  for (arg in args) {
    if (grepl("^--h3-res=", arg)) defaults$h3_res <- as.integer(sub("^--h3-res=", "", arg))
    if (grepl("^--road-buffer-m=", arg)) defaults$road_buffer <- as.numeric(sub("^--road-buffer-m=", "", arg))
  }
  defaults
}

file_tag <- function(h3_res, road_buffer) {
  sprintf("h3_res%d_buf%dm", h3_res, as.integer(road_buffer))
}

CORR_COLUMNS <- c(
  "road_length_density_km_per_km2",
  "road_intersection_density_per_km2",
  "road_coverage_ratio",
  "road_type_count"
)

CORR_LABELS <- c(
  road_length_density_km_per_km2 = "Road density",
  road_intersection_density_per_km2 = "Intersection density",
  road_coverage_ratio = "Coverage ratio",
  road_type_count = "Road type count"
)

plot_continuous <- function(grid, boundary, column, title, filename, label = NULL) {
  p <- make_base_map(
    boundary,
    title = title,
    subtitle = sprintf("H3 res %d | road buffer %dm", args$h3_res, as.integer(args$road_buffer))
  ) +
    geom_sf(data = grid, aes(fill = .data[[column]]), color = NA) +
    scale_fill_viridis_c(option = "C", name = label %||% column, labels = label_number(accuracy = 0.01))

  save_map(p, file.path(FIG_DIR, filename))
}

compute_spearman_matrix <- function(grid_df, tag) {
  missing <- setdiff(CORR_COLUMNS, names(grid_df))
  if (length(missing)) {
    stop("Missing columns for correlation matrix: ", paste(missing, collapse = ", "))
  }

  corr_mat <- cor(
    grid_df[, CORR_COLUMNS, drop = FALSE],
    method = "spearman",
    use = "pairwise.complete.obs"
  )

  csv_path <- file.path(DATA_DIR, paste0("Nairobi_cityroad_correlation_spearman_", tag, ".csv"))
  write.csv(corr_mat, csv_path, row.names = TRUE)
  message("  ", basename(csv_path))
  corr_mat
}

plot_spearman_heatmap <- function(corr_mat, tag, n_cells) {
  n <- length(CORR_COLUMNS)
  labels <- CORR_LABELS[CORR_COLUMNS]

  corr_long <- data.frame(
    row_idx = rep(seq_len(n), each = n),
    col_idx = rep(seq_len(n), times = n),
    rho = as.vector(corr_mat),
    stringsAsFactors = FALSE
  ) |>
    mutate(
      var_row = factor(.data$row_idx, levels = seq_len(n), labels = labels),
      var_col = factor(.data$col_idx, levels = seq_len(n), labels = labels),
      cell_type = case_when(
        .data$row_idx < .data$col_idx ~ "upper",
        .data$row_idx == .data$col_idx ~ "diag",
        TRUE ~ "lower"
      ),
      fill_rho = if_else(.data$cell_type == "lower", .data$rho, NA_real_),
      label = case_when(
        .data$cell_type == "lower" ~ sprintf("%.2f", .data$rho),
        .data$cell_type == "diag" ~ labels[.data$row_idx],
        TRUE ~ ""
      ),
      text_color = if_else(.data$fill_rho >= 0.88, "white", "#1F3340")
    )

  rho_range <- range(corr_long$rho[corr_long$cell_type == "lower"], na.rm = TRUE)
  fill_low <- floor(rho_range[1] * 20) / 20 - 0.02
  fill_high <- 1

  lower_cells <- corr_long |> filter(.data$cell_type == "lower")
  diag_cells <- corr_long |> filter(.data$cell_type == "diag")

  tile_base <- ggplot(corr_long) +
    geom_tile(
      aes(x = .data$var_col, y = .data$var_row),
      fill = "#F4F6F9",
      color = "#FFFFFF",
      linewidth = 1.4
    ) +
    geom_tile(
      aes(x = .data$var_col, y = .data$var_row, fill = .data$fill_rho),
      color = "#FFFFFF",
      linewidth = 1.4
    ) +
    geom_text(
      data = lower_cells,
      aes(x = .data$var_col, y = .data$var_row, label = .data$label, color = .data$text_color),
      size = 3.6,
      fontface = "bold"
    ) +
    geom_text(
      data = diag_cells,
      aes(x = .data$var_col, y = .data$var_row, label = .data$label),
      size = 3.1,
      color = "#5C6B7A",
      fontface = "plain"
    ) +
    scale_fill_gradient(
      low = "#E8EEF4",
      high = "#2F5D7A",
      limits = c(fill_low, fill_high),
      na.value = NA,
      name = expression(Spearman~rho),
      breaks = pretty(c(fill_low, fill_high), n = 4),
      labels = label_number(accuracy = 0.01),
      guide = guide_colorbar(
        barwidth = unit(0.55, "cm"),
        barheight = unit(3.2, "cm"),
        frame.colour = "#D5DCE6",
        frame.linewidth = 0.35,
        title.position = "top",
        title.hjust = 0.5
      )
    ) +
    scale_color_identity() +
    scale_x_discrete(position = "top", expand = expansion(add = 0.6)) +
    scale_y_discrete(limits = rev(labels), expand = expansion(add = 0.6)) +
    coord_fixed(ratio = 1) +
    labs(
      title = "Spearman correlation matrix (city-road H3 metrics)",
      subtitle = sprintf(
        "Nairobi | H3 res %d | %dm road buffer | n = %s cells | lower triangle",
        args$h3_res,
        as.integer(args$road_buffer),
        comma(n_cells)
      ),
      x = NULL,
      y = NULL,
      caption = sprintf(
        "Diagonal = variable labels | Colour range scaled to observed \u03C1 (%.2f\u20131.00)",
        fill_low
      )
    ) +
    theme_minimal(base_size = 11, base_family = "sans") +
    theme(
      plot.background = element_rect(fill = "white", color = NA),
      panel.background = element_rect(fill = "#FAFBFC", color = NA),
      panel.grid = element_blank(),
      plot.title = element_text(face = "bold", size = 15, hjust = 0.5, color = "#1F2933", margin = margin(b = 4)),
      plot.subtitle = element_text(size = 10, hjust = 0.5, color = "#5C6B7A", margin = margin(b = 12)),
      plot.caption = element_text(size = 8.5, hjust = 0.5, color = "#7B8794", margin = margin(t = 10)),
      axis.text.x = element_text(
        angle = 30,
        hjust = 0,
        vjust = 0,
        color = "#3D4F5F",
        size = 10,
        face = "bold",
        margin = margin(b = 4)
      ),
      axis.text.y = element_text(color = "#3D4F5F", size = 10, face = "bold", margin = margin(r = 4)),
      axis.ticks = element_blank(),
      legend.position = "right",
      legend.title = element_text(face = "bold", size = 9.5, color = "#3D4F5F"),
      legend.text = element_text(size = 8.5, color = "#4B5B6A"),
      plot.margin = margin(16, 18, 14, 14)
    )

  out_path <- file.path(FIG_DIR, paste0("Nairobi_cityroad_correlation_spearman_", tag, ".png"))
  ggsave(out_path, plot = tile_base, width = 8.2, height = 7.4, dpi = 320, bg = "white")
  message("  ", basename(out_path))
}

plot_spearman_scatter_matrix <- function(grid_df, corr_mat, tag, n_cells) {
  pair_theme <- function(show_x = TRUE, show_y = TRUE) {
    theme_minimal(base_size = 10, base_family = "sans") +
      theme(
        plot.background = element_rect(fill = "white", color = NA),
        panel.background = element_rect(fill = "#F8F9FB", color = NA),
        panel.grid.major = element_line(color = "#E6EAF0", linewidth = 0.3),
        panel.grid.minor = element_blank(),
        panel.border = element_rect(color = "#D5DCE6", fill = NA, linewidth = 0.35),
        axis.title = element_text(size = 9, color = "#3D4F5F"),
        axis.text = element_text(size = 8, color = "#4B5B6A"),
        plot.margin = margin(4, 4, 4, 4),
        axis.title.x = if (show_x) element_text(margin = margin(t = 6)) else element_blank(),
        axis.title.y = if (show_y) element_text(margin = margin(r = 6)) else element_blank(),
        axis.text.x = if (show_x) element_text() else element_blank(),
        axis.text.y = if (show_y) element_text() else element_blank(),
        axis.ticks.x = if (show_x) element_line() else element_blank(),
        axis.ticks.y = if (show_y) element_line() else element_blank()
      )
  }

  make_scatter <- function(x_col, y_col, rho, show_x = TRUE, show_y = TRUE) {
    x_vals <- grid_df[[x_col]]
    y_vals <- grid_df[[y_col]]
    x_lab <- CORR_LABELS[[x_col]]
    y_lab <- CORR_LABELS[[y_col]]

    ggplot(grid_df, aes(x = .data[[x_col]], y = .data[[y_col]])) +
      geom_point(alpha = 0.38, size = 1.3, color = "#3D6B8C") +
      annotate(
        "label",
        x = -Inf,
        y = Inf,
        label = sprintf("\u03C1 = %.2f", rho),
        hjust = -0.08,
        vjust = 1.15,
        size = 3.2,
        fontface = "bold",
        fill = alpha("white", 0.92),
        linewidth = 0.2,
        color = "#1F2933"
      ) +
      scale_x_continuous(labels = label_number(accuracy = 0.1)) +
      scale_y_continuous(labels = label_number(accuracy = 0.1)) +
      labs(x = if (show_x) x_lab else NULL, y = if (show_y) y_lab else NULL) +
      pair_theme(show_x = show_x, show_y = show_y)
  }

  # Upper-triangle layout: row 1 has 3 panels, row 2 has 2, row 3 has 1.
  p12 <- make_scatter(CORR_COLUMNS[2], CORR_COLUMNS[1], corr_mat[1, 2], show_x = FALSE, show_y = TRUE)
  p13 <- make_scatter(CORR_COLUMNS[3], CORR_COLUMNS[1], corr_mat[1, 3], show_x = FALSE, show_y = FALSE)
  p14 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[1], corr_mat[1, 4], show_x = FALSE, show_y = FALSE)
  p23 <- make_scatter(CORR_COLUMNS[3], CORR_COLUMNS[2], corr_mat[2, 3], show_x = FALSE, show_y = TRUE)
  p24 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[2], corr_mat[2, 4], show_x = FALSE, show_y = FALSE)
  p34 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[3], corr_mat[3, 4], show_x = TRUE, show_y = TRUE)

  p <- wrap_plots(
    p12, p13, p14, p23, p24, p34,
    design = "
    ABC
    #DE
    ##F
    ",
    guides = "keep"
  ) +
    plot_annotation(
      title = "Spearman correlation scatter matrix (city-road H3 metrics)",
      subtitle = sprintf(
        "Nairobi | H3 res %d | %dm road buffer | n = %s cells | upper triangle: each panel = pairwise scatter with Spearman \u03C1",
        args$h3_res,
        as.integer(args$road_buffer),
        comma(n_cells)
      ),
      theme = theme(
        plot.title = element_text(face = "bold", size = 14, hjust = 0.5, color = "#1F2933"),
        plot.subtitle = element_text(size = 9.5, hjust = 0.5, color = "#5C6B7A", margin = margin(b = 8))
      )
    )

  out_path <- file.path(FIG_DIR, paste0("Nairobi_cityroad_correlation_spearman_", tag, "_scatter.png"))
  ggsave(out_path, plot = p, width = 10, height = 9.5, dpi = 320, bg = "white")
  message("  ", basename(out_path))
}

plot_spearman_correlation <- function(grid_df, tag, n_cells) {
  corr_mat <- compute_spearman_matrix(grid_df, tag)
  plot_spearman_heatmap(corr_mat, tag, n_cells)
  plot_spearman_scatter_matrix(grid_df, corr_mat, tag, n_cells)
}

`%||%` <- function(x, y) if (is.null(x)) y else x

args <- parse_args()
tag <- file_tag(args$h3_res, args$road_buffer)

grid <- st_read(file.path(DATA_DIR, paste0("Nairobi_cityroad_grid_", tag, ".gpkg")), quiet = TRUE) |>
  st_transform(CRS_EA)
boundary <- st_read(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)

message("Writing figures to ", FIG_DIR)

plot_continuous(
  grid, boundary, "road_length_density_km_per_km2",
  "Road length density (km/km²)",
  paste0("Nairobi_cityroad_density_", tag, ".png"),
  "km/km²"
)

plot_continuous(
  grid, boundary, "road_coverage_ratio",
  "Road coverage ratio (50 m buffer)",
  paste0("Nairobi_cityroad_coverage_", tag, ".png"),
  "Ratio"
)

plot_continuous(
  grid, boundary, "road_intersection_density_per_km2",
  "Road intersection density (per km²)",
  paste0("Nairobi_cityroad_intersections_", tag, ".png"),
  "Count/km²"
)

plot_continuous(
  grid, boundary, "road_segment_count",
  "Road segment count per cell",
  paste0("Nairobi_cityroad_segments_", tag, ".png"),
  "Segments"
)

grid_df <- st_drop_geometry(grid)
plot_spearman_correlation(grid_df, tag, nrow(grid_df))

message("Done.")

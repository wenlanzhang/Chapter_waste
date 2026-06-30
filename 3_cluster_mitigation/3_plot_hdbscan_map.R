#!/usr/bin/env Rscript
# HDBSCAN waste cluster maps — gsvi vs gsvi_selfcollected arms

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(ggrepel)
  library(patchwork)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
CLUSTER_DIR <- file.path(DATA_ROOT, "3_cluster_mitigation")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_cluster_mitigation")

MIN_CLUSTER_SIZE <- 25L
MIN_SAMPLES <- 6L
WGS84 <- 4326

CHOCOLATE_PALETTE <- c(
  "#6B4226", "#8B5E3C", "#A67B5B", "#C9A27F",
  "#E5C8A9", "#4B3621", "#7C482B"
)
NOISE_COLOUR <- "#D3D3D3"
CLUSTER_LABEL_COLOUR <- "#112721"
AXIS_COLOUR <- "#4D2D18"

LEGEND_LEVELS <- c(
  "Clustered Points",
  "Noise Points",
  "City Boundary"
)

make_hdbscan_legend <- function(waste) {
  n_clustered_points <- sum(waste$HDB_cluster != -1L)
  n_noise <- sum(waste$HDB_cluster == -1L)
  labels <- hdbscan_legend_labels(n_clustered_points, n_noise)
  values <- setNames(
    c("#8B5E3C", NOISE_COLOUR, "black"),
    labels
  )
  list(labels = labels, values = values)
}

MAP_SPECS <- list(
  list(
    tag = "gsvi",
    gpkg = "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    panel = "(A) GSVI only (Google)",
    subtitle_prefix = "Google Street View waste detections"
  ),
  list(
    tag = "gsvi_selfcollected",
    gpkg = "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
    panel = "(B) GSVI + self-collected",
    subtitle_prefix = "Google + Faith + self-collected (ZWL)"
  )
)

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

cluster_palette <- function(cluster_ids) {
  labels <- sort(setdiff(unique(cluster_ids), -1L))
  colours <- setNames(
    rep(CHOCOLATE_PALETTE, length.out = length(labels)),
    as.character(labels)
  )
  c(colours, "-1" = NOISE_COLOUR)
}

make_cluster_labels <- function(waste_wgs) {
  coords <- st_coordinates(waste_wgs)
  waste_wgs |>
    st_drop_geometry() |>
    mutate(lon = coords[, 1], lat = coords[, 2]) |>
    filter(HDB_cluster != -1L) |>
    group_by(HDB_cluster) |>
    summarise(lon = mean(lon), lat = mean(lat), .groups = "drop") |>
    mutate(label = as.character(HDB_cluster))
}

make_param_label <- function(n_clusters) {
  paste0(
    "Detected clusters: ", n_clusters, "\n",
    "HDBSCAN Parameters:\n",
    " \u2022 min_cluster_size = ", MIN_CLUSTER_SIZE, "\n",
    " \u2022 min_samples = ", MIN_SAMPLES
  )
}

make_legend_df <- function(labels) {
  data.frame(
    legend_type = factor(labels, levels = labels),
    lon = NA_real_,
    lat = NA_real_
  )
}

build_hdbscan_map <- function(
  waste,
  boundary,
  panel_title,
  subtitle_text = NULL,
  base_size = 11,
  label_size = 3.1,
  param_size = 3.4,
  show_panel_title = TRUE
) {
  waste <- waste |>
    mutate(cluster_id = if_else(HDB_cluster == -1L, "-1", as.character(HDB_cluster)))

  n_clusters <- length(setdiff(unique(waste$HDB_cluster), -1L))
  palette_vals <- cluster_palette(waste$HDB_cluster)
  cluster_labels <- make_cluster_labels(waste)
  legend_info <- make_hdbscan_legend(waste)
  legend_df <- make_legend_df(legend_info$labels)

  waste_coords <- st_coordinates(waste)
  waste_plot <- waste |>
    mutate(
      plot_x = waste_coords[, 1],
      plot_y = waste_coords[, 2],
      point_colour = unname(palette_vals[cluster_id])
    )

  p <- ggplot() +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.1) +
    geom_point(
      data = waste_plot,
      aes(x = plot_x, y = plot_y),
      colour = waste_plot$point_colour,
      size = 0.95,
      alpha = 0.82
    ) +
    geom_text_repel(
      data = cluster_labels,
      aes(x = lon, y = lat, label = label),
      colour = CLUSTER_LABEL_COLOUR,
      fontface = "bold",
      size = label_size,
      family = "sans",
      bg.color = "white",
      bg.r = 0.08,
      box.padding = 0.18,
      point.padding = 0.25,
      segment.color = alpha("grey35", 0.55),
      segment.size = 0.25,
      min.segment.length = 0.12,
      max.overlaps = Inf,
      seed = 42,
      show.legend = FALSE
    ) +
    annotate(
      "label",
      x = -Inf,
      y = Inf,
      label = make_param_label(n_clusters),
      hjust = -0.02,
      vjust = 1.08,
      size = param_size,
      fill = alpha("white", 0.92),
      colour = "grey75",
      linewidth = 0.35,
      label.padding = unit(0.35, "lines")
    ) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      na.rm = FALSE,
      inherit.aes = FALSE
    ) +
    scale_colour_manual(
      name = NULL,
      values = legend_info$values,
      breaks = legend_info$labels
    ) +
    guides(
      colour = guide_legend(
        override.aes = list(
          shape = c(16, 16, 22),
          size = c(3.0, 3.0, 2.4),
          fill = c(NA, NA, NA),
          colour = c("#8B5E3C", NOISE_COLOUR, "black"),
          stroke = c(0.5, 0.5, 1.1),
          alpha = c(1, 1, 1)
        ),
        keywidth = unit(1.0, "lines"),
        keyheight = unit(1.0, "lines"),
        ncol = 1
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = if (show_panel_title) panel_title else NULL,
      x = "Longitude",
      y = "Latitude"
    ) +
    hdbscan_map_theme(base_size)

  mitigation_map_decorations(p)
}


message("Reading shared layers...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
plots <- list()

for (spec in MAP_SPECS) {
  message("Building map: ", spec$tag)
  waste <- read_wgs84(file.path(CLUSTER_DIR, spec$gpkg))

  p <- build_hdbscan_map(
    waste = waste,
    boundary = boundary,
    panel_title = spec$panel,
    base_size = 11,
    label_size = 3.1,
    param_size = 3.4,
    show_panel_title = TRUE
  )

  out_path <- file.path(FIG_DIR, paste0("Waste_HDBSCAN_", spec$tag, ".png"))
  save_mitigation_map(p, out_path, boundary)
  message("  ", basename(out_path))

  plots[[spec$tag]] <- build_hdbscan_map(
    waste = waste,
    boundary = boundary,
    panel_title = spec$panel,
    base_size = 9.5,
    label_size = 2.6,
    param_size = 2.8,
    show_panel_title = TRUE
  )
}

message("Building comparison panel...")
comparison <- wrap_plots(plots$gsvi, plots$gsvi_selfcollected, ncol = 2) +
  plot_annotation(
    title = "HDBSCAN Clustering of Waste Points in Nairobi",
    subtitle = "Same HDBSCAN settings (min_cluster_size = 25, min_samples = 6); GSVI vs GSVI+self collected",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 10, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 8))
    )
  )

comparison_path <- file.path(FIG_DIR, "Waste_HDBSCAN_comparison.png")
comparison_size <- mitigation_fig_size(boundary, width = 8, title_pad = 0.9)
ggsave(
  comparison_path,
  plot = comparison,
  width = 16,
  height = comparison_size$height,
  dpi = 600,
  bg = "white"
)
message("  ", basename(comparison_path))
message("Done.")

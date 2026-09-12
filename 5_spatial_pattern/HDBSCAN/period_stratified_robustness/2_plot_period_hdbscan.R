#!/usr/bin/env Rscript
# Period-stratified HDBSCAN maps: 2015-2019 vs 2021-2022 waste-positive panoramas

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
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "..", "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "..", "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- chapter_data_root
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
CLUSTER_DIR <- file.path(
  DATA_ROOT, "5_spatial_pattern", "HDBSCAN", "period_stratified_robustness"
)
FIG_DIR <- file.path(
  script_dir, "..", "..", "..", "Figure", "5_spatial_pattern", "HDBSCAN",
  "period_stratified_robustness"
)
message("Cluster dir: ", CLUSTER_DIR)
MIN_CLUSTER_SIZE <- 25L
MIN_SAMPLES <- 6L
WGS84 <- 4326

CHOCOLATE_PALETTE <- c(
  "#6B4226", "#8B5E3C", "#A67B5B", "#C9A27F",
  "#E5C8A9", "#4B3621", "#7C482B"
)
NOISE_COLOUR <- "#D3D3D3"
CLUSTER_LABEL_COLOUR <- "#112721"
AXIS_COLOUR <- "#1F120C"
INFO_BOX_COLOUR <- "#1F120C"

MAP_SPECS <- list(
  list(
    tag = "2015_2019",
    gpkg = "Nairobi_waste_hdbscan_2015_2019_32737.gpkg",
    panel = "(A) 2015-2019"
  ),
  list(
    tag = "2021_2022",
    gpkg = "Nairobi_waste_hdbscan_2021_2022_32737.gpkg",
    panel = "(B) 2021-2022"
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

make_param_label <- function(n_clusters, n_points) {
  paste0(
    "Waste-positive panoramas: ", format(n_points, big.mark = ","), "\n",
    "Detected clusters: ", n_clusters, "\n",
    "HDBSCAN Parameters:\n",
    " \u2022 min_cluster_size = ", MIN_CLUSTER_SIZE, "\n",
    " \u2022 min_samples = ", MIN_SAMPLES
  )
}

build_period_map <- function(waste, boundary, panel_title, base_size = 9.5) {
  waste <- waste |>
    mutate(cluster_id = if_else(HDB_cluster == -1L, "-1", as.character(HDB_cluster)))

  n_clusters <- length(setdiff(unique(waste$HDB_cluster), -1L))
  palette_vals <- cluster_palette(waste$HDB_cluster)
  cluster_labels <- make_cluster_labels(waste)

  n_clustered <- sum(waste$HDB_cluster != -1L)
  n_noise <- sum(waste$HDB_cluster == -1L)
  legend_labels <- hdbscan_legend_labels(n_clustered, n_noise)
  legend_values <- setNames(
    c("#8B5E3C", NOISE_COLOUR, "black"),
    legend_labels
  )
  legend_df <- data.frame(
    legend_type = factor(legend_labels, levels = legend_labels),
    lon = NA_real_,
    lat = NA_real_
  )

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
      size = 0.9,
      alpha = 0.82
    ) +
    geom_text_repel(
      data = cluster_labels,
      aes(x = lon, y = lat, label = label),
      colour = CLUSTER_LABEL_COLOUR,
      fontface = "bold",
      size = 2.6,
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
      label = make_param_label(n_clusters, nrow(waste)),
      hjust = -0.02,
      vjust = 1.08,
      size = 3.0,
      family = "sans",
      fontface = "plain",
      fill = alpha("white", 0.94),
      colour = INFO_BOX_COLOUR,
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
      values = legend_values,
      breaks = legend_labels
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
      title = panel_title,
      x = "Longitude",
      y = "Latitude"
    ) +
    hdbscan_map_theme(base_size) +
    theme(
      axis.title.x = element_text(colour = AXIS_COLOUR, face = "italic"),
      axis.title.y = element_text(colour = AXIS_COLOUR, face = "italic"),
      axis.text = element_text(colour = AXIS_COLOUR),
      axis.line = element_line(colour = AXIS_COLOUR, linewidth = 0.4),
      panel.border = element_rect(colour = AXIS_COLOUR, fill = NA, linewidth = 0.5)
    )

  mitigation_map_decorations(p)
}

message("Reading boundary...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

plots <- list()
for (spec in MAP_SPECS) {
  gpkg_path <- file.path(CLUSTER_DIR, spec$gpkg)
  if (!file.exists(gpkg_path)) {
    stop(
      "Missing ", gpkg_path, "\nRun:\n",
      "  python 5_spatial_pattern/HDBSCAN/period_stratified_robustness/",
      "1_period_hdbscan.py"
    )
  }
  message("Building map: ", spec$tag)
  waste <- read_wgs84(gpkg_path)
  plots[[spec$tag]] <- build_period_map(
    waste = waste,
    boundary = boundary,
    panel_title = spec$panel
  )
}

comparison <- wrap_plots(plots$`2015_2019`, plots$`2021_2022`, ncol = 2) +
  plot_annotation(
    title = "Period-stratified HDBSCAN of waste-positive GSVI panoramas",
    subtitle = "Same parameters (min_cluster_size = 25, min_samples = 6)",
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = AXIS_COLOUR),
      plot.subtitle = element_text(
        size = 9.5, hjust = 0.5, colour = AXIS_COLOUR, margin = margin(b = 8)
      )
    )
  )

out <- file.path(FIG_DIR, "Period_HDBSCAN_comparison.png")
comparison_size <- mitigation_fig_size(boundary, width = 8, title_pad = 0.9)
ggsave(
  out,
  plot = comparison,
  width = 16,
  height = comparison_size$height,
  dpi = 300,
  bg = "white"
)
message("Wrote ", out)
message("Done.")

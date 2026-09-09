#!/usr/bin/env Rscript
# HDBSCAN context map: panoid clusters + urban-poor, major settlements, Dandora
# Ported from del/SVI_distance_use.ipynb (cell ~58), using panoid-level HDBSCAN.

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(ggrepel)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}
source(file.path(script_dir, "..", "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
CLUSTER_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "HDBSCAN")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "HDBSCAN")

MIN_CLUSTER_SIZE <- 25L
MIN_SAMPLES <- 6L
WGS84 <- 4326L

CHOCOLATE_PALETTE <- c(
  "#6B4226", "#8B5E3C", "#A67B5B", "#C9A27F",
  "#E5C8A9", "#4B3621", "#7C482B"
)
NOISE_COLOUR <- "#D3D3D3"
CLUSTER_LABEL_COLOUR <- "#112721"
SLUM_FILL <- "#496142"
SLUM_EDGE <- "#112721"
ANNOT_COLOUR <- "#991f00"
AXIS_COLOUR <- "#4D2D18"

# WGS84 landmarks (notebook coordinates)
DANDORA <- data.frame(
  name = "Dandora",
  lon = 36.89019083011253,
  lat = -1.248673295458689
)
MAJOR_SETTLEMENTS <- data.frame(
  name = c("Mukuru", "Kibera", "Mathare", "Kawangware"),
  lat = c(-1.3139, -1.3129, -1.2647, -1.2872),
  lon = c(36.8702, 36.7929, 36.8563, 36.7471)
)

MAP_SPECS <- list(
  list(
    tag = "gsvi",
    gpkg = "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    title = "HDBSCAN Hotspots of Waste-Positive GSVI Panoids",
    subtitle = "Urban-poor settlements, major areas, and Dandora landfill"
  ),
  list(
    tag = "gsvi_selfcollected",
    gpkg = "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
    title = "HDBSCAN Hotspots (GSVI Panoids + Self-Collected)",
    subtitle = "Urban-poor settlements, major areas, and Dandora landfill"
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
    "Waste+ panoids: ", format(n_points, big.mark = ",", trim = TRUE), "\n",
    "Detected clusters: ", n_clusters, "\n",
    "HDBSCAN Parameters:\n",
    " \u2022 min_cluster_size = ", MIN_CLUSTER_SIZE, "\n",
    " \u2022 min_samples = ", MIN_SAMPLES
  )
}

build_context_map <- function(waste, boundary, slums, title, subtitle) {
  waste <- waste |>
    mutate(cluster_id = if_else(HDB_cluster == -1L, "-1", as.character(HDB_cluster)))

  n_clusters <- length(setdiff(unique(waste$HDB_cluster), -1L))
  n_points <- nrow(waste)
  palette_vals <- cluster_palette(waste$HDB_cluster)
  cluster_labels <- make_cluster_labels(waste)

  n_clustered <- sum(waste$HDB_cluster != -1L)
  n_noise <- sum(waste$HDB_cluster == -1L)

  legend_levels <- c(
    "Clustered Points",
    "Noise Points",
    "City Boundary",
    "Urban Poor Boundary",
    "Dandora Landfill",
    "Major Urban Poor"
  )
  legend_values <- setNames(
    c("#8B5E3C", NOISE_COLOUR, "black", SLUM_FILL, ANNOT_COLOUR, ANNOT_COLOUR),
    legend_levels
  )
  legend_df <- data.frame(
    legend_type = factor(legend_levels, levels = legend_levels),
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

  # Draw noise first so clusters sit on top
  waste_noise <- waste_plot |> filter(HDB_cluster == -1L)
  waste_clust <- waste_plot |> filter(HDB_cluster != -1L)

  p <- ggplot() +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.05) +
    geom_point(
      data = waste_noise,
      aes(x = plot_x, y = plot_y),
      colour = NOISE_COLOUR,
      size = 0.85,
      alpha = 0.75
    ) +
    geom_point(
      data = waste_clust,
      aes(x = plot_x, y = plot_y),
      colour = waste_clust$point_colour,
      size = 0.95,
      alpha = 0.85
    ) +
    # Urban poor on top of points (light fill + thin outline)
    geom_sf(
      data = slums,
      fill = alpha(SLUM_FILL, 0.14),
      colour = alpha(SLUM_EDGE, 0.55),
      linewidth = 0.28
    ) +
    geom_text_repel(
      data = cluster_labels,
      aes(x = lon, y = lat, label = label),
      colour = CLUSTER_LABEL_COLOUR,
      fontface = "bold",
      size = 3.9,
      family = "sans",
      bg.color = "white",
      bg.r = 0.1,
      box.padding = 0.2,
      point.padding = 0.22,
      segment.color = alpha("grey35", 0.5),
      segment.size = 0.3,
      min.segment.length = 0.1,
      max.overlaps = Inf,
      seed = 42,
      show.legend = FALSE
    ) +
    # Dandora landfill
    geom_point(
      data = DANDORA,
      aes(x = lon, y = lat),
      shape = 21,
      fill = ANNOT_COLOUR,
      colour = "black",
      size = 3.8,
      stroke = 0.6,
      inherit.aes = FALSE
    ) +
    geom_text(
      data = DANDORA,
      aes(x = lon - 0.028, y = lat + 0.012, label = name),
      colour = ANNOT_COLOUR,
      fontface = "bold",
      size = 4.4,
      inherit.aes = FALSE
    ) +
    # Major urban-poor place marks
    geom_point(
      data = MAJOR_SETTLEMENTS,
      aes(x = lon, y = lat),
      shape = 4,
      colour = ANNOT_COLOUR,
      size = 3.8,
      stroke = 1.25,
      inherit.aes = FALSE
    ) +
    geom_text_repel(
      data = MAJOR_SETTLEMENTS,
      aes(x = lon, y = lat, label = name),
      colour = ANNOT_COLOUR,
      fontface = "bold",
      size = 4.3,
      box.padding = 0.4,
      point.padding = 0.28,
      segment.color = alpha(ANNOT_COLOUR, 0.45),
      segment.size = 0.35,
      min.segment.length = 0,
      max.overlaps = Inf,
      seed = 42,
      bg.color = "white",
      bg.r = 0.1,
      show.legend = FALSE
    ) +
    annotate(
      "label",
      x = -Inf,
      y = Inf,
      label = make_param_label(n_clusters, n_points),
      hjust = -0.02,
      vjust = 1.08,
      size = 4.0,
      fill = alpha("white", 0.94),
      colour = "grey20",
      linewidth = 0.4,
      label.padding = unit(0.4, "lines")
    ) +
    # Legend carriers
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      na.rm = FALSE,
      inherit.aes = FALSE
    ) +
    scale_colour_manual(
      name = NULL,
      values = legend_values,
      breaks = legend_levels
    ) +
    guides(
      colour = guide_legend(
        override.aes = list(
          shape = c(16, 16, 22, 22, 21, 4),
          size = c(3.4, 3.4, 2.8, 3.4, 3.6, 3.4),
          fill = c(
            NA, NA, NA,
            alpha(SLUM_FILL, 0.5),
            ANNOT_COLOUR,
            NA
          ),
          colour = c(
            "#8B5E3C", NOISE_COLOUR, "black",
            SLUM_EDGE, "black", ANNOT_COLOUR
          ),
          stroke = c(0.5, 0.5, 1.15, 0.65, 0.75, 1.15),
          alpha = c(1, 1, 1, 1, 1, 1)
        ),
        keywidth = unit(1.15, "lines"),
        keyheight = unit(1.15, "lines"),
        ncol = 1
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = title,
      subtitle = subtitle,
      x = "Longitude",
      y = "Latitude"
    ) +
    # Larger base type: high-dpi map otherwise looks empty with pt~11 labels
    hdbscan_map_theme(13.5) +
    theme(
      plot.title = element_text(
        face = "bold",
        size = 16,
        hjust = 0.5,
        colour = "#2f2f2f",
        margin = margin(t = 0, b = 3)
      ),
      plot.subtitle = element_text(
        size = 12,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 8)
      ),
      legend.text = element_text(size = 11.5, colour = "#2f2f2f"),
      legend.key.size = unit(1.05, "lines"),
      axis.title = element_text(size = 12.5),
      axis.text = element_text(size = 11)
    )

  mitigation_map_decorations(p)
}

message("Reading shared layers...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
# Merged settlement clusters → single multipolygon for “boundary” map style
# (source ~100 m cells look gridded; dissolve removes the cell edges)
slum_clusters <- read_wgs84(
  file.path(INPUT_DIR, "Nairobi_slum_cluster_polygon_32737.gpkg")
)
slums <- st_sf(
  geometry = st_make_valid(st_union(st_geometry(slum_clusters))),
  crs = st_crs(slum_clusters)
)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

for (spec in MAP_SPECS) {
  gpkg_path <- file.path(CLUSTER_DIR, spec$gpkg)
  if (!file.exists(gpkg_path)) {
    stop("Missing ", gpkg_path, "\nRun: python 5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py")
  }
  message("Building context map: ", spec$tag)
  waste <- read_wgs84(gpkg_path)
  p <- build_context_map(
    waste = waste,
    boundary = boundary,
    slums = slums,
    title = spec$title,
    subtitle = spec$subtitle
  )
  out_path <- file.path(
    FIG_DIR, paste0("Waste_HDBSCAN_context_", spec$tag, ".png")
  )
  size <- mitigation_fig_size(boundary, width = 8.5, title_pad = 0.85)
  ggsave(
    out_path,
    plot = p,
    width = size$width,
    height = size$height,
    dpi = 600,
    bg = "white"
  )
  message(
    "  ", basename(out_path),
    " (", round(size$width, 2), " x ", round(size$height, 2), " in @ 600 dpi)"
  )
}

message("Done.")

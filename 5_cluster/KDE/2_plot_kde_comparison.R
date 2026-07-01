#!/usr/bin/env Rscript
# KDE hotspot robustness maps — gsvi vs gsvi_selfcollected (two-panel + difference)

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(patchwork)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
KDE_DIR <- file.path(DATA_ROOT, "5_cluster", "KDE")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_cluster", "KDE")

GSVI_HOTSPOTS <- file.path(KDE_DIR, "Nairobi_kde_hotspot_polygons_gsvi_32737.gpkg")
SC_HOTSPOTS <- file.path(
  KDE_DIR,
  "Nairobi_kde_hotspot_polygons_gsvi_selfcollected_32737.gpkg"
)

OUT_GSVI <- file.path(FIG_DIR, "KDE_hotspot_gsvi.png")
OUT_SC <- file.path(FIG_DIR, "KDE_hotspot_gsvi_selfcollected.png")
OUT_COMPARISON <- file.path(FIG_DIR, "KDE_hotspot_comparison.png")
OUT_DIFFERENCE <- file.path(FIG_DIR, "KDE_hotspot_difference.png")

PROJECTED_CRS <- 32737
WGS84 <- 4326

GSVI_SVI_COLOUR <- "#D4CCC2"
ALL_SVI_COLOUR <- "#D4CCC2"
HOTSPOT_FILL <- "#F0E6D8"
HOTSPOT_EDGE <- "#C9A27F"
OVERLAP_FILL <- "#F0E6D8"
GSVI_SELF_FILL <- "#6B4226"
GSVI_ONLY_FILL <- "#C9A27F"
GSVI_WASTE_COLOUR <- "#C9A27F"
SELF_COLLECTED_WASTE_COLOUR <- "#6B4226"
BOUNDARY_COLOUR <- "black"

read_projected <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(PROJECTED_CRS)
}

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

load_waste_points <- function() {
  gsvi <- read_wgs84(file.path(INPUT_DIR, "Nairobi_Waste_point_gsvi_32737.gpkg"))
  all_waste <- read_wgs84(
    file.path(INPUT_DIR, "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg")
  )
  self_collected <- all_waste |> filter(source %in% c("ZWL", "Faith"))
  list(gsvi = gsvi, self_collected = self_collected)
}

load_gsvi_svi <- function() {
  read_wgs84(file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_32737.gpkg"))
}

load_all_svi <- function() {
  read_wgs84(file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg"))
}

fmt_km2 <- function(km2) {
  paste0(format(round(km2, 2), nsmall = 2), " km2")
}

area_km2 <- function(geom, crs = PROJECTED_CRS) {
  if (is.null(geom) || all(st_is_empty(geom))) {
    return(0)
  }
  g <- st_as_sf(st_sfc(geom, crs = crs))
  as.numeric(sum(st_area(g))) / 1e6
}

union_hotspots <- function(gdf) {
  if (nrow(gdf) == 0) {
    return(st_sfc(crs = st_crs(gdf)))
  }
  st_union(st_make_valid(st_geometry(gdf)))
}

safe_difference <- function(a, b) {
  if (length(a) == 0 || all(st_is_empty(a))) {
    return(st_sfc(crs = st_crs(a)))
  }
  out <- st_difference(st_make_valid(a), st_make_valid(b))
  out <- out[!st_is_empty(out)]
  if (length(out) == 0) {
    return(st_sfc(crs = st_crs(a)))
  }
  st_union(out)
}

to_wgs84_sf <- function(geom) {
  if (length(geom) == 0 || all(st_is_empty(geom))) {
    return(NULL)
  }
  st_as_sf(st_transform(st_sfc(geom, crs = PROJECTED_CRS), WGS84))
}

legend_guide <- function(legend_info, base_size = 11) {
  guide_legend(
    override.aes = list(
      shape = legend_info$shapes,
      fill = legend_info$fills,
      colour = legend_info$colours,
      stroke = legend_info$strokes,
      alpha = legend_info$alphas,
      size = legend_info$sizes
    ),
    keywidth = unit(1.6, "lines"),
    keyheight = unit(0.95, "lines"),
    ncol = 1
  )
}

make_panel_legend <- function(
  hotspot_km2,
  svi_label,
  n_svi,
  n_gsvi_waste,
  n_self_waste = 0L
) {
  labels <- c(
    paste0(svi_label, " (", format(n_svi, big.mark = ",", trim = TRUE), ")"),
    paste0("KDE hotspot (", fmt_km2(hotspot_km2), ")"),
    paste0("GSVI waste (", format(n_gsvi_waste, big.mark = ",", trim = TRUE), ")")
  )
  shapes <- c(16, 22, 16)
  fills <- c(NA, HOTSPOT_FILL, NA)
  colours <- c(GSVI_SVI_COLOUR, HOTSPOT_EDGE, GSVI_WASTE_COLOUR)
  strokes <- c(0.5, 0.45, 0.5)
  alphas <- c(0.55, 0.95, 1)

  if (n_self_waste > 0L) {
    labels <- c(
      labels,
      paste0(
        "Self-collected SVI waste (",
        format(n_self_waste, big.mark = ",", trim = TRUE),
        ")"
      )
    )
    shapes <- c(shapes, 16)
    fills <- c(fills, NA)
    colours <- c(colours, SELF_COLLECTED_WASTE_COLOUR)
    strokes <- c(strokes, 0.5)
    alphas <- c(alphas, 1)
  }

  labels <- c(labels, "City Boundary")
  shapes <- c(shapes, 22)
  fills <- c(fills, NA)
  colours <- c(colours, BOUNDARY_COLOUR)
  strokes <- c(strokes, 1.1)
  alphas <- c(alphas, 1)

  sizes <- rep(2.8, length(labels))
  sizes[shapes == 16 & grepl("SVI", labels) & !grepl("waste", labels, ignore.case = TRUE)] <- 2.2
  sizes[grepl("waste", labels, ignore.case = TRUE)] <- 3.0
  sizes[labels == "City Boundary"] <- 2.4

  list(
    labels = labels,
    shapes = shapes,
    fills = fills,
    colours = colours,
    strokes = strokes,
    alphas = alphas,
    sizes = sizes
  )
}

build_kde_panel <- function(
  svi_bg,
  svi_colour,
  gsvi_waste,
  self_waste = NULL,
  hotspot_sf,
  boundary,
  panel_title,
  legend_info,
  base_size = 11
) {
  legend_df <- data.frame(
    legend_type = factor(legend_info$labels, levels = legend_info$labels),
    lon = NA_real_,
    lat = NA_real_
  )

  p <- ggplot() +
    geom_sf(
      data = svi_bg,
      colour = svi_colour,
      size = 0.06,
      alpha = 0.3,
      linewidth = 0
    )

  if (!is.null(hotspot_sf) && nrow(hotspot_sf) > 0) {
    p <- p +
      geom_sf(
        data = hotspot_sf,
        fill = HOTSPOT_FILL,
        colour = alpha(HOTSPOT_EDGE, 0.65),
        linewidth = 0.3
      )
  }

  p <- p +
    geom_sf(
      data = gsvi_waste,
      colour = GSVI_WASTE_COLOUR,
      size = 0.42,
      alpha = 0.78,
      linewidth = 0
    )

  if (!is.null(self_waste) && nrow(self_waste) > 0) {
    p <- p +
      geom_sf(
        data = self_waste,
        colour = SELF_COLLECTED_WASTE_COLOUR,
        size = 0.62,
        alpha = 0.92,
        linewidth = 0
      )
  }

  p +
    geom_sf(data = boundary, fill = NA, colour = BOUNDARY_COLOUR, linewidth = 1.1) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      inherit.aes = FALSE,
      na.rm = FALSE
    ) +
    scale_colour_manual(
      name = NULL,
      values = setNames(legend_info$colours, legend_info$labels),
      breaks = legend_info$labels
    ) +
    guides(colour = legend_guide(legend_info, base_size)) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = panel_title,
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size) +
    theme(
      plot.title = element_text(margin = margin(t = 0, b = 2)),
      plot.margin = margin(t = 1, r = 2, b = 1, l = 3, unit = "mm"),
      legend.text = element_text(size = base_size - 1.8)
    )
}

make_diff_legend <- function(
  overlap_km2,
  gsvi_self_km2,
  gsvi_only_km2,
  n_all_svi,
  n_gsvi_waste,
  n_self_waste
) {
  labels <- c(
    paste0("All SVI (", format(n_all_svi, big.mark = ",", trim = TRUE), ")"),
    paste0("Overlapping hotspot (", fmt_km2(overlap_km2), ")"),
    paste0("GSVI + Self hotspot (", fmt_km2(gsvi_self_km2), ")")
  )
  shapes <- c(16, 22, 22)
  fills <- c(NA, OVERLAP_FILL, GSVI_SELF_FILL)
  colours <- c(ALL_SVI_COLOUR, HOTSPOT_EDGE, GSVI_SELF_FILL)
  strokes <- c(0.5, 0.45, 0.45)
  alphas <- c(0.55, 0.95, 0.95)

  if (gsvi_only_km2 > 0.001) {
    labels <- c(
      labels,
      paste0("GSVI-only hotspot (", fmt_km2(gsvi_only_km2), ")")
    )
    shapes <- c(shapes, 22)
    fills <- c(fills, GSVI_ONLY_FILL)
    colours <- c(colours, GSVI_ONLY_FILL)
    strokes <- c(strokes, 0.45)
    alphas <- c(alphas, 0.95)
  }

  labels <- c(
    labels,
    paste0("GSVI waste (", format(n_gsvi_waste, big.mark = ",", trim = TRUE), ")"),
    paste0(
      "Self-collected SVI waste (",
      format(n_self_waste, big.mark = ",", trim = TRUE),
      ")"
    ),
    "City Boundary"
  )
  shapes <- c(shapes, 16, 16, 22)
  fills <- c(fills, NA, NA, NA)
  colours <- c(colours, GSVI_WASTE_COLOUR, SELF_COLLECTED_WASTE_COLOUR, BOUNDARY_COLOUR)
  strokes <- c(strokes, 0.5, 0.5, 1.1)
  alphas <- c(alphas, 1, 1, 1)

  sizes <- rep(2.8, length(labels))
  sizes[shapes == 16] <- 3.0
  sizes[labels == "City Boundary"] <- 2.4
  sizes[grepl("^All SVI", labels)] <- 2.2

  list(
    labels = labels,
    shapes = shapes,
    fills = fills,
    colours = colours,
    strokes = strokes,
    alphas = alphas,
    sizes = sizes
  )
}

build_kde_difference_map <- function(
  all_svi,
  overlap_sf,
  gsvi_self_sf,
  gsvi_only_sf,
  gsvi_waste,
  self_waste,
  boundary,
  legend_info,
  base_size = 11
) {
  legend_df <- data.frame(
    legend_type = factor(legend_info$labels, levels = legend_info$labels),
    lon = NA_real_,
    lat = NA_real_
  )

  p <- ggplot() +
    geom_sf(
      data = all_svi,
      colour = ALL_SVI_COLOUR,
      size = 0.06,
      alpha = 0.3,
      linewidth = 0
    )

  if (!is.null(overlap_sf)) {
    p <- p + geom_sf(
      data = overlap_sf,
      fill = OVERLAP_FILL,
      colour = alpha(HOTSPOT_EDGE, 0.55),
      linewidth = 0.25
    )
  }

  if (!is.null(gsvi_self_sf)) {
    p <- p + geom_sf(
      data = gsvi_self_sf,
      fill = alpha(GSVI_SELF_FILL, 0.55),
      colour = GSVI_SELF_FILL,
      linewidth = 0.35
    )
  }

  if (!is.null(gsvi_only_sf)) {
    p <- p + geom_sf(
      data = gsvi_only_sf,
      fill = alpha(GSVI_ONLY_FILL, 0.5),
      colour = GSVI_ONLY_FILL,
      linewidth = 0.3
    )
  }

  p <- p +
    geom_sf(
      data = gsvi_waste,
      colour = GSVI_WASTE_COLOUR,
      size = 0.42,
      alpha = 0.78,
      linewidth = 0
    ) +
    geom_sf(
      data = self_waste,
      colour = SELF_COLLECTED_WASTE_COLOUR,
      size = 0.62,
      alpha = 0.92,
      linewidth = 0
    ) +
    geom_sf(data = boundary, fill = NA, colour = BOUNDARY_COLOUR, linewidth = 1.1) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      inherit.aes = FALSE,
      na.rm = FALSE
    ) +
    scale_colour_manual(
      name = NULL,
      values = setNames(legend_info$colours, legend_info$labels),
      breaks = legend_info$labels
    ) +
    guides(colour = legend_guide(legend_info, base_size)) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = "KDE Hotspot Area Difference After Adding Self-collected Imagery",
      subtitle = "Where GSVI-only and GSVI + self-collected KDE hotspots overlap, expand, or shift",
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size) +
    theme(
      plot.subtitle = element_text(
        size = base_size - 1.5,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 4, t = 0)
      ),
      legend.text = element_text(size = base_size - 1.8)
    )

  mitigation_map_decorations(p)
}

for (path in c(GSVI_HOTSPOTS, SC_HOTSPOTS)) {
  if (!file.exists(path)) {
    stop(
      "Missing ", path,
      "\nRun: python 5_cluster/KDE/1_kde_hotspots.py"
    )
  }
}

message("Reading KDE hotspot polygons, SVI, and waste points...")
gsvi_polys <- read_projected(GSVI_HOTSPOTS)
sc_polys <- read_projected(SC_HOTSPOTS)
gsvi_svi <- load_gsvi_svi()
all_svi <- load_all_svi()
waste_layers <- load_waste_points()
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |>
  st_transform(WGS84)

gsvi_union <- union_hotspots(gsvi_polys)
sc_union <- union_hotspots(sc_polys)

gsvi_hotspot_km2 <- area_km2(gsvi_union)
sc_hotspot_km2 <- area_km2(sc_union)

overlap_geom <- st_intersection(st_make_valid(gsvi_union), st_make_valid(sc_union))
gsvi_self_geom <- safe_difference(sc_union, gsvi_union)
gsvi_only_geom <- safe_difference(gsvi_union, sc_union)

overlap_km2 <- area_km2(overlap_geom)
gsvi_self_km2 <- area_km2(gsvi_self_geom)
gsvi_only_km2 <- area_km2(gsvi_only_geom)

gsvi_hotspot_wgs <- to_wgs84_sf(gsvi_union)
sc_hotspot_wgs <- to_wgs84_sf(sc_union)
overlap_sf <- to_wgs84_sf(overlap_geom)
gsvi_self_sf <- to_wgs84_sf(gsvi_self_geom)
gsvi_only_sf <- if (gsvi_only_km2 > 0.001) to_wgs84_sf(gsvi_only_geom) else NULL

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

legend_gsvi <- make_panel_legend(
  hotspot_km2 = gsvi_hotspot_km2,
  svi_label = "GSVI SVI",
  n_svi = nrow(gsvi_svi),
  n_gsvi_waste = nrow(waste_layers$gsvi)
)

legend_sc <- make_panel_legend(
  hotspot_km2 = sc_hotspot_km2,
  svi_label = "All SVI",
  n_svi = nrow(all_svi),
  n_gsvi_waste = nrow(waste_layers$gsvi),
  n_self_waste = nrow(waste_layers$self_collected)
)

p_gsvi <- build_kde_panel(
  svi_bg = gsvi_svi,
  svi_colour = GSVI_SVI_COLOUR,
  gsvi_waste = waste_layers$gsvi,
  hotspot_sf = gsvi_hotspot_wgs,
  boundary = boundary,
  panel_title = "(A) GSVI only: KDE hotspots",
  legend_info = legend_gsvi
)

p_sc <- build_kde_panel(
  svi_bg = all_svi,
  svi_colour = ALL_SVI_COLOUR,
  gsvi_waste = waste_layers$gsvi,
  self_waste = waste_layers$self_collected,
  hotspot_sf = sc_hotspot_wgs,
  boundary = boundary,
  panel_title = "(B) GSVI + self-collected: KDE hotspots",
  legend_info = legend_sc
)

save_mitigation_map(p_gsvi, OUT_GSVI, boundary)
save_mitigation_map(p_sc, OUT_SC, boundary)

comparison <- p_gsvi + p_sc +
  plot_layout(ncol = 2, widths = c(1, 1)) &
  theme(
    plot.margin = margin(t = 0, r = 1, b = 0, l = 2, unit = "mm"),
    plot.title = element_text(margin = margin(t = 0, b = 1)),
    axis.title.x = element_text(margin = margin(t = -8, b = 0)),
    axis.title.y = element_text(margin = margin(r = -8, l = 0))
  )

panel_width <- 8
comp_size <- mitigation_fig_size(boundary, width = panel_width, title_pad = 0.15)
ggsave(
  OUT_COMPARISON,
  plot = comparison,
  width = panel_width * 2,
  height = comp_size$height,
  dpi = 600,
  bg = "white"
)

legend_diff <- make_diff_legend(
  overlap_km2,
  gsvi_self_km2,
  gsvi_only_km2,
  nrow(all_svi),
  nrow(waste_layers$gsvi),
  nrow(waste_layers$self_collected)
)

p_diff <- build_kde_difference_map(
  all_svi = all_svi,
  overlap_sf = overlap_sf,
  gsvi_self_sf = gsvi_self_sf,
  gsvi_only_sf = gsvi_only_sf,
  gsvi_waste = waste_layers$gsvi,
  self_waste = waste_layers$self_collected,
  boundary = boundary,
  legend_info = legend_diff
)

save_mitigation_map(p_diff, OUT_DIFFERENCE, boundary)

message("Wrote ", OUT_GSVI)
message("Wrote ", OUT_SC)
message("Wrote ", OUT_COMPARISON)
message("Wrote ", OUT_DIFFERENCE)
message("Done.")

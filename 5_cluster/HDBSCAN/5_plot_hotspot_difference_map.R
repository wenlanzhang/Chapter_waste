#!/usr/bin/env Rscript
# Hotspot polygon overlap vs additional area — gsvi vs gsvi_selfcollected

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
MITIGATION_DIR <- file.path(DATA_ROOT, "5_cluster", "HDBSCAN")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_cluster", "HDBSCAN")

GSVI_HOTSPOTS <- file.path(MITIGATION_DIR, "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg")
SC_HOTSPOTS <- file.path(
  MITIGATION_DIR,
  "Nairobi_waste_hotspot_polygons_gsvi_selfcollected_32737.gpkg"
)
OUT_PATH <- file.path(FIG_DIR, "Hotspot_area_difference_gsvi_selfcollected.png")

PROJECTED_CRS <- 32737
WGS84 <- 4326

ALL_SVI_COLOUR <- "#D4CCC2"
OVERLAP_FILL <- "#F0E6D8"
ADDITIONAL_FILL <- "#6B4226"
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

load_all_svi <- function() {
  read_wgs84(file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg"))
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

make_legend_info <- function(
  overlap_km2,
  additional_km2,
  gsvi_only_km2,
  n_all_svi,
  n_gsvi_waste,
  n_self_waste
) {
  labels <- c(
    paste0("All SVI (", format(n_all_svi, big.mark = ",", trim = TRUE), ")"),
    paste0(
      "Overlapping hotspot area (",
      format(round(overlap_km2, 2), nsmall = 2),
      " km²)"
    ),
    paste0(
      "Additional hotspot area (",
      format(round(additional_km2, 2), nsmall = 2),
      " km²)"
    )
  )
  shapes <- c(16, 22, 22)
  fills <- c(NA, OVERLAP_FILL, ADDITIONAL_FILL)
  colours <- c(ALL_SVI_COLOUR, "#C9A27F", ADDITIONAL_FILL)
  strokes <- c(0.5, 0.45, 0.45)
  alphas <- c(0.55, 0.95, 0.95)

  if (gsvi_only_km2 > 0.001) {
    labels <- c(
      labels,
      paste0(
        "GSVI-only hotspot area (",
        format(round(gsvi_only_km2, 2), nsmall = 2),
        " km²)"
      )
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

build_hotspot_difference_map <- function(
  all_svi,
  overlap_sf,
  additional_sf,
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
      colour = alpha("#C9A27F", 0.55),
      linewidth = 0.25
    )
  }

  if (!is.null(additional_sf)) {
    p <- p + geom_sf(
      data = additional_sf,
      fill = alpha(ADDITIONAL_FILL, 0.55),
      colour = ADDITIONAL_FILL,
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
    guides(
      colour = guide_legend(
        override.aes = list(
          shape = legend_info$shapes,
          fill = legend_info$fills,
          colour = legend_info$colours,
          stroke = legend_info$strokes,
          alpha = legend_info$alphas,
          size = legend_info$sizes
        ),
        keywidth = unit(1.0, "lines"),
        keyheight = unit(1.0, "lines"),
        ncol = 1
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = "Hotspot Area Difference After Adding Self-collected Imagery",
      subtitle = "Where GSVI-only and GSVI + self-collected cluster hulls overlap, expand, or shift",
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size) +
    theme(
      plot.subtitle = element_text(
        size = base_size - 1.5,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 6)
      )
    )

  mitigation_map_decorations(p)
}

for (path in c(GSVI_HOTSPOTS, SC_HOTSPOTS)) {
  if (!file.exists(path)) {
    stop(
      "Missing ", path,
      "\nRun: python 5_cluster/HDBSCAN/4_mitigation_comparison.py"
    )
  }
}

message("Reading hotspot polygons, SVI, and waste points...")
gsvi_polys <- read_projected(GSVI_HOTSPOTS)
sc_polys <- read_projected(SC_HOTSPOTS)
all_svi <- load_all_svi()
waste_layers <- load_waste_points()
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |>
  st_transform(WGS84)

gsvi_union <- union_hotspots(gsvi_polys)
sc_union <- union_hotspots(sc_polys)

overlap_geom <- st_intersection(
  st_make_valid(gsvi_union),
  st_make_valid(sc_union)
)
additional_geom <- safe_difference(sc_union, gsvi_union)
gsvi_only_geom <- safe_difference(gsvi_union, sc_union)

overlap_km2 <- area_km2(overlap_geom)
additional_km2 <- area_km2(additional_geom)
gsvi_only_km2 <- area_km2(gsvi_only_geom)

message(sprintf("  Overlap area:     %.3f km²", overlap_km2))
message(sprintf("  Additional area:  %.3f km²", additional_km2))
message(sprintf("  GSVI-only area:   %.3f km²", gsvi_only_km2))
message(sprintf("  All SVI panoids:  %s", format(nrow(all_svi), big.mark = ",")))
message(sprintf("  GSVI waste pts:   %s", format(nrow(waste_layers$gsvi), big.mark = ",")))
message(sprintf(
  "  Self-collected:   %s",
  format(nrow(waste_layers$self_collected), big.mark = ",")
))

legend_info <- make_legend_info(
  overlap_km2,
  additional_km2,
  gsvi_only_km2,
  nrow(all_svi),
  nrow(waste_layers$gsvi),
  nrow(waste_layers$self_collected)
)

overlap_sf <- to_wgs84_sf(overlap_geom)
additional_sf <- to_wgs84_sf(additional_geom)
gsvi_only_sf <- if (gsvi_only_km2 > 0.001) to_wgs84_sf(gsvi_only_geom) else NULL

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

p <- build_hotspot_difference_map(
  all_svi = all_svi,
  overlap_sf = overlap_sf,
  additional_sf = additional_sf,
  gsvi_only_sf = gsvi_only_sf,
  gsvi_waste = waste_layers$gsvi,
  self_waste = waste_layers$self_collected,
  boundary = boundary,
  legend_info = legend_info
)

save_mitigation_map(p, OUT_PATH, boundary)
message("Wrote ", OUT_PATH)
message("Done.")

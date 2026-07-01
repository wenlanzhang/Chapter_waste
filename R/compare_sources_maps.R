# Shared loaders and map builders for 4_compare source maps

WGS84 <- 4326

ALL_SVI_COLOUR <- "#D4CCC2"
GSVI_COLOUR <- "#C9A27F"
SELF_COLLECTED_COLOUR <- "#6B4226"
SLUM_FILL <- "#496142"
SLUM_EDGE <- "#112721"
SLUM_ALPHA <- 0.22

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

load_svi_by_source <- function(svi_gpkg) {
  all_svi <- read_wgs84(svi_gpkg)
  gsvi_svi <- all_svi |> filter(source == "Google")
  self_svi <- all_svi |> filter(source %in% c("Faith", "ZWL"))
  list(gsvi = gsvi_svi, self_collected = self_svi, all = all_svi)
}

load_waste_by_source <- function(input_dir) {
  gsvi <- read_wgs84(file.path(input_dir, "Nairobi_Waste_point_gsvi_32737.gpkg"))
  all_waste <- read_wgs84(
    file.path(input_dir, "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg")
  )
  self_collected <- all_waste |> filter(source %in% c("ZWL", "Faith"))
  list(gsvi = gsvi, self_collected = self_collected)
}

build_svi_sources_map <- function(
  all_svi,
  gsvi_svi,
  self_svi,
  boundary,
  slums_union,
  panel_title = NULL,
  base_size = 11
) {
  legend_info <- make_source_legend(
    n_all_svi = nrow(all_svi),
    n_gsvi = nrow(gsvi_svi),
    n_self = nrow(self_svi)
  )
  legend_labels <- legend_info$labels
  legend_df <- make_source_legend_df(legend_labels)
  legend_colours <- make_source_legend_colours(
    legend_labels,
    ALL_SVI_COLOUR,
    GSVI_COLOUR,
    SELF_COLLECTED_COLOUR,
    SLUM_FILL
  )

  title <- if (is.null(panel_title)) {
    "Street View Imagery by Source in Nairobi"
  } else {
    panel_title
  }

  p <- ggplot() +
    geom_sf(
      data = all_svi,
      colour = ALL_SVI_COLOUR,
      size = 0.08,
      alpha = 0.32,
      linewidth = 0
    ) +
    geom_sf(
      data = gsvi_svi,
      colour = GSVI_COLOUR,
      size = 0.08,
      alpha = 0.38,
      linewidth = 0
    ) +
    geom_sf(
      data = self_svi,
      colour = SELF_COLLECTED_COLOUR,
      size = 0.55,
      alpha = 0.92,
      linewidth = 0
    ) +
    geom_sf(
      data = slums_union,
      fill = alpha(SLUM_FILL, SLUM_ALPHA),
      colour = SLUM_EDGE,
      linewidth = 0.35
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.1) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      inherit.aes = FALSE,
      na.rm = FALSE
    ) +
    scale_colour_manual(name = NULL, values = legend_colours, breaks = legend_labels) +
    guides(
      colour = source_legend_guide(
        legend_labels,
        ALL_SVI_COLOUR,
        GSVI_COLOUR,
        SELF_COLLECTED_COLOUR,
        SLUM_FILL,
        SLUM_EDGE,
        SLUM_ALPHA
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = title,
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size)

  mitigation_map_decorations(p)
}

build_waste_sources_map <- function(
  all_svi,
  gsvi_waste,
  self_waste,
  boundary,
  slums_union,
  panel_title = NULL,
  base_size = 11
) {
  legend_info <- make_source_legend(
    n_all_svi = nrow(all_svi),
    n_gsvi = nrow(gsvi_waste),
    n_self = nrow(self_waste)
  )
  legend_labels <- legend_info$labels
  legend_df <- make_source_legend_df(legend_labels)
  legend_colours <- make_source_legend_colours(
    legend_labels,
    ALL_SVI_COLOUR,
    GSVI_COLOUR,
    SELF_COLLECTED_COLOUR,
    SLUM_FILL
  )

  title <- if (is.null(panel_title)) {
    "Waste Detections by Source in Nairobi"
  } else {
    panel_title
  }

  p <- ggplot() +
    geom_sf(
      data = all_svi,
      colour = ALL_SVI_COLOUR,
      size = 0.08,
      alpha = 0.32,
      linewidth = 0
    ) +
    geom_sf(
      data = gsvi_waste,
      colour = GSVI_COLOUR,
      size = 0.95,
      alpha = 0.82,
      linewidth = 0
    ) +
    geom_sf(
      data = self_waste,
      colour = SELF_COLLECTED_COLOUR,
      size = 0.95,
      alpha = 0.88,
      linewidth = 0
    ) +
    geom_sf(
      data = slums_union,
      fill = alpha(SLUM_FILL, SLUM_ALPHA),
      colour = SLUM_EDGE,
      linewidth = 0.35
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.1) +
    geom_point(
      data = legend_df,
      aes(x = lon, y = lat, colour = legend_type),
      inherit.aes = FALSE,
      na.rm = FALSE
    ) +
    scale_colour_manual(name = NULL, values = legend_colours, breaks = legend_labels) +
    guides(
      colour = source_legend_guide(
        legend_labels,
        ALL_SVI_COLOUR,
        GSVI_COLOUR,
        SELF_COLLECTED_COLOUR,
        SLUM_FILL,
        SLUM_EDGE,
        SLUM_ALPHA
      )
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = title,
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size)

  mitigation_map_decorations(p)
}

load_compare_layers <- function(input_dir, svi_gpkg) {
  boundary <- read_wgs84(file.path(input_dir, "Nairobi_boundary_polygon_32737.gpkg"))
  slums <- read_wgs84(file.path(input_dir, "Nairobi_slum_polygon_32737.gpkg"))
  slums_union <- slums |>
    st_union() |>
    st_as_sf() |>
    st_make_valid()
  svi_layers <- load_svi_by_source(svi_gpkg)
  waste_layers <- load_waste_by_source(input_dir)
  list(
    boundary = boundary,
    slums_union = slums_union,
    svi_layers = svi_layers,
    waste_layers = waste_layers
  )
}

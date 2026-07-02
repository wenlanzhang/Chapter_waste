#!/usr/bin/env Rscript
# Zoomed process map: city H3 → roads → SVI coverage → waste (2–3 central H3 cells)
# Outputs: 4-panel schematic + optional single-map multi-layer version

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
ROAD_GPKG <- "Nairobi_road_03_local_cleaned_32737.gpkg"
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737

parse_args <- function() {
  defaults <- list(
    h3_res = 8L,
    road_buffer = 50,
    svi_buffer = 50,
    density_min = 20,
    density_max = 30,
    n_cells = 3L,
    window_buffer_m = 180,
    layers_n_cells = 1L,
    layers_window_buffer_m = 95,
    layers_waste_min = 2L,
    layers_waste_max = 5L,
    svi_buffer_examples = 4L,
    interior_min_ratio = 0.98,
    layout = "both"
  )
  for (arg in commandArgs(trailingOnly = TRUE)) {
    if (grepl("^--h3-res=", arg)) defaults$h3_res <- as.integer(sub("^--h3-res=", "", arg))
    if (grepl("^--road-buffer-m=", arg)) defaults$road_buffer <- as.numeric(sub("^--road-buffer-m=", "", arg))
    if (grepl("^--svi-buffer-m=", arg)) defaults$svi_buffer <- as.numeric(sub("^--svi-buffer-m=", "", arg))
    if (grepl("^--density-min=", arg)) defaults$density_min <- as.numeric(sub("^--density-min=", "", arg))
    if (grepl("^--density-max=", arg)) defaults$density_max <- as.numeric(sub("^--density-max=", "", arg))
    if (grepl("^--n-cells=", arg)) defaults$n_cells <- as.integer(sub("^--n-cells=", "", arg))
    if (grepl("^--window-buffer-m=", arg)) defaults$window_buffer_m <- as.numeric(sub("^--window-buffer-m=", "", arg))
    if (grepl("^--layers-n-cells=", arg)) defaults$layers_n_cells <- as.integer(sub("^--layers-n-cells=", "", arg))
    if (grepl("^--layers-window-buffer-m=", arg)) defaults$layers_window_buffer_m <- as.numeric(sub("^--layers-window-buffer-m=", "", arg))
    if (grepl("^--layers-waste-min=", arg)) defaults$layers_waste_min <- as.integer(sub("^--layers-waste-min=", "", arg))
    if (grepl("^--layers-waste-max=", arg)) defaults$layers_waste_max <- as.integer(sub("^--layers-waste-max=", "", arg))
    if (grepl("^--svi-buffer-examples=", arg)) defaults$svi_buffer_examples <- as.integer(sub("^--svi-buffer-examples=", "", arg))
    if (grepl("^--interior-min-ratio=", arg)) defaults$interior_min_ratio <- as.numeric(sub("^--interior-min-ratio=", "", arg))
    if (grepl("^--layout=", arg)) defaults$layout <- sub("^--layout=", "", arg)
  }
  if (!defaults$layout %in% c("panel", "layers", "both")) {
    stop("--layout must be one of: panel, layers, both")
  }
  defaults
}

file_tag <- function(h3_res, road_buffer, svi_buffer) {
  sprintf("h3_res%d_buf%dm_svi%d", h3_res, as.integer(road_buffer), as.integer(svi_buffer))
}

read_layer <- function(path) {
  x <- st_read(path, quiet = TRUE) |> st_transform(CRS_EA)
  if (!"geometry" %in% names(x) && "geom" %in% names(x)) {
    x <- x |> rename(geometry = geom)
  }
  st_as_sf(x)
}

density_in_range <- function(x, min_val, max_val) {
  x >= min_val & x <= max_val
}

filter_interior_cells <- function(grid, min_area_ratio = 0.98) {
  if (!all(c("city_area_m2", "cell_area_m2") %in% names(grid))) {
    warning("Missing city_area_m2/cell_area_m2; skipping interior-cell filter.")
    return(grid)
  }
  out <- grid |>
    mutate(.area_ratio = .data$city_area_m2 / .data$cell_area_m2) |>
    filter(.data$.area_ratio >= min_area_ratio) |>
    select(-.area_ratio)
  if (nrow(out) == 0) {
    stop("No interior H3 cells remain after applying area ratio >= ", min_area_ratio)
  }
  out
}

select_focus_cells <- function(grid, density_min, density_max, n_cells, interior_min_ratio = 0.98) {
  grid <- filter_interior_cells(grid, interior_min_ratio)
  in_range <- density_in_range(grid$road_length_density_km_per_km2, density_min, density_max)
  candidates <- grid[in_range, ]
  if (nrow(candidates) == 0) {
    stop("No H3 cells found in density range ", density_min, "–", density_max, " km/km²")
  }

  best_seed <- NULL
  best_count <- -1L
  for (i in seq_len(nrow(candidates))) {
    seed <- candidates[i, ]
    nb <- st_touches(seed, grid)[[1]]
    if (!length(nb)) next
    n_in <- sum(in_range[nb])
    if (n_in > best_count) {
      best_count <- n_in
      best_seed <- seed$h3_index[[1]]
    }
  }

  seed <- grid |> filter(.data$h3_index == best_seed)
  nb <- st_touches(seed, grid)[[1]]
  neighbor_ids <- grid[nb, ] |>
    filter(
      density_in_range(.data$road_length_density_km_per_km2, density_min, density_max),
      (.data$city_area_m2 / .data$cell_area_m2) >= interior_min_ratio
    ) |>
    arrange(desc(.data$road_length_density_km_per_km2)) |>
    slice_head(n = max(0L, n_cells - 1L)) |>
    pull(.data$h3_index)

  focus_ids <- c(seed$h3_index[[1]], neighbor_ids)
  focus <- grid |> filter(.data$h3_index %in% focus_ids)

  if (nrow(focus) < min(n_cells, 2L)) {
    warning("Fewer than ", n_cells, " cells in range; using best available cluster.")
  }
  focus
}

select_layers_focus_cell <- function(
  grid,
  waste_points,
  density_min,
  density_max,
  exclude_h3 = NULL,
  waste_min = 2L,
  waste_max = 5L,
  interior_min_ratio = 0.98
) {
  grid <- filter_interior_cells(grid, interior_min_ratio)
  in_range <- density_in_range(grid$road_length_density_km_per_km2, density_min, density_max)
  candidates <- grid[in_range, ]
  if (nrow(candidates) == 0) {
    stop("No H3 cells found in density range ", density_min, "–", density_max, " km/km²")
  }
  if (!is.null(exclude_h3)) {
    candidates <- candidates |> filter(.data$h3_index != exclude_h3)
  }
  if (nrow(candidates) == 0) {
    stop("No alternative H3 cells available after excluding ", exclude_h3)
  }

  waste_hits <- st_join(
    waste_points,
    candidates |> select(.data$h3_index, .data$geometry),
    join = st_within,
    left = FALSE
  )
  waste_counts <- if (nrow(waste_hits) > 0) {
    waste_hits |>
      st_drop_geometry() |>
      count(.data$h3_index, name = "waste_count")
  } else {
    data.frame(h3_index = character(), waste_count = integer())
  }

  picked <- candidates |>
    left_join(waste_counts, by = "h3_index") |>
    mutate(waste_count = coalesce(.data$waste_count, 0L)) |>
    filter(.data$waste_count >= waste_min, .data$waste_count <= waste_max) |>
    mutate(waste_target_dist = abs(.data$waste_count - (waste_min + waste_max) / 2)) |>
    arrange(.data$waste_target_dist, desc(.data$road_length_density_km_per_km2))

  if (nrow(picked) == 0) {
    stop(
      "No H3 cells in density range ", density_min, "–", density_max,
      " km/km² have ", waste_min, "–", waste_max, " waste-positive panoids."
    )
  }

  message(
    "  Layers hex ", picked$h3_index[[1]],
    " (", picked$waste_count[[1]], " waste-positive panoid",
    if (picked$waste_count[[1]] == 1L) ")" else "s)",
    " | density ", sprintf("%.1f", picked$road_length_density_km_per_km2[[1]]), " km/km²",
    " | interior cell"
  )
  picked[1, ]
}

neighbor_context_cells <- function(grid, focus) {
  nb <- st_touches(focus, grid)[[1]]
  if (!length(nb)) {
    return(grid[0, ] |> mutate(cell_role = "Context H3 cell"))
  }
  grid[nb, ] |> mutate(cell_role = "Context H3 cell")
}

select_svi_buffer_examples <- function(svi, focus, n_examples, buffer_m) {
  in_focus <- svi[st_intersects(svi, focus, sparse = FALSE)[, 1], ]
  if (nrow(in_focus) == 0) {
    empty <- in_focus
    return(list(points = empty, buffers = empty))
  }

  cen <- st_centroid(st_union(focus$geometry))
  coords <- st_coordinates(in_focus)
  cc <- st_coordinates(cen)
  in_focus <- in_focus |>
    mutate(.angle = atan2(coords[, 2] - cc[2], coords[, 1] - cc[1])) |>
    arrange(.angle)

  n_pick <- min(n_examples, nrow(in_focus))
  idx <- unique(pmax(1L, round(seq(1, nrow(in_focus), length.out = n_pick))))
  picked <- in_focus[idx, ] |> select(-.angle)

  buffers <- st_buffer(picked, dist = buffer_m)
  buffers$layer <- sprintf("SVI buffer (%dm)", as.integer(buffer_m))
  list(points = picked, buffers = buffers)
}

clip_lines <- function(lines, window) {
  cropped <- st_crop(lines, st_as_sfc(st_bbox(window)))
  out <- st_intersection(cropped, window)
  out <- out[!st_is_empty(out), ]
  if (nrow(out) == 0) return(out)
  out |> filter(st_geometry_type(.data$geometry) %in% c("LINESTRING", "MULTILINESTRING"))
}

extract_line_parts <- function(geom, min_length_m = 0.1) {
  if (length(geom) == 0 || all(st_is_empty(geom))) {
    return(st_sfc(crs = st_crs(geom)))
  }
  geom <- st_make_valid(geom)
  gt <- as.character(st_geometry_type(geom))
  parts <- st_sfc(crs = st_crs(geom))
  if ("LINESTRING" %in% gt) {
    parts <- c(parts, geom[gt == "LINESTRING"])
  }
  if ("MULTILINESTRING" %in% gt) {
    ml <- geom[gt == "MULTILINESTRING"]
    for (i in seq_along(ml)) {
      parts <- c(parts, st_cast(ml[i], "LINESTRING"))
    }
  }
  if ("GEOMETRYCOLLECTION" %in% gt) {
    gc <- geom[gt == "GEOMETRYCOLLECTION"]
    for (i in seq_along(gc)) {
      lines <- st_collection_extract(gc[i], "LINESTRING")
      if (length(lines)) parts <- c(parts, lines)
    }
  }
  if (length(parts) == 0) {
    return(st_sfc(crs = st_crs(geom)))
  }
  parts <- parts[!st_is_empty(parts)]
  len <- as.numeric(st_length(parts))
  parts[len >= min_length_m]
}

compute_window_roadsvi_coverage <- function(roads, svi, window, buffer_m, min_length_m = 0.1) {
  roads_clip <- clip_lines(roads, window)
  empty <- st_sf(
    coverage_status = character(),
    length_m = numeric(),
    geometry = st_sfc(crs = st_crs(roads)),
    crs = st_crs(roads)
  )
  if (nrow(roads_clip) == 0) {
    return(list(covered = empty, uncovered = empty))
  }

  reach <- st_buffer(window, dist = buffer_m)
  svi_use <- svi[st_intersects(svi, reach, sparse = FALSE)[, 1], ]
  if (nrow(svi_use) == 0) {
    unc <- roads_clip |>
      mutate(
        coverage_status = "uncovered",
        length_m = as.numeric(st_length(.))
      )
    return(list(covered = empty, uncovered = unc))
  }

  buf_union <- st_union(st_buffer(svi_use, dist = buffer_m))
  cov_parts <- st_sfc(crs = st_crs(roads_clip))
  unc_parts <- st_sfc(crs = st_crs(roads_clip))

  for (i in seq_len(nrow(roads_clip))) {
    seg <- st_geometry(roads_clip)[i]
    cov_lines <- extract_line_parts(st_intersection(seg, buf_union), min_length_m)
    unc_lines <- extract_line_parts(st_difference(seg, buf_union), min_length_m)
    if (length(cov_lines)) cov_parts <- c(cov_parts, cov_lines)
    if (length(unc_lines)) unc_parts <- c(unc_parts, unc_lines)
  }

  covered <- if (length(cov_parts)) {
    st_sf(
      coverage_status = "covered",
      length_m = as.numeric(st_length(cov_parts)),
      geometry = cov_parts,
      crs = st_crs(roads_clip)
    )
  } else {
    empty
  }

  uncovered <- if (length(unc_parts)) {
    st_sf(
      coverage_status = "uncovered",
      length_m = as.numeric(st_length(unc_parts)),
      geometry = unc_parts,
      crs = st_crs(roads_clip)
    )
  } else {
    empty
  }

  list(covered = covered, uncovered = uncovered)
}

clip_points <- function(points, window) {
  st_intersection(points, window)
}

panel_coords <- function(bbox) {
  coord_sf(
    crs = map_crs(),
    xlim = c(bbox[["xmin"]], bbox[["xmax"]]),
    ylim = c(bbox[["ymin"]], bbox[["ymax"]]),
    datum = NA,
    expand = FALSE
  )
}

inner_legend_theme <- function() {
  theme(
    legend.position = c(0.98, 0.04),
    legend.justification = c(1, 0),
    legend.title = element_text(size = 8, face = "bold"),
    legend.text = element_text(size = 7),
    legend.key.height = unit(0.4, "cm"),
    legend.background = element_rect(fill = alpha("white", 0.88), color = NA),
    legend.box.background = element_rect(fill = alpha("white", 0.88), color = "grey75", linewidth = 0.3),
    legend.box.margin = margin(3, 5, 3, 5)
  )
}

layers_legend_theme <- function() {
  theme(
    legend.position = c(0.02, 0.04),
    legend.justification = c(0, 0),
    legend.title = element_text(size = 9.5, face = "bold", hjust = 0, lineheight = 1.05),
    legend.text = element_text(size = 9),
    legend.key.height = unit(0.5, "cm"),
    legend.background = element_rect(fill = alpha("white", 0.90), color = NA),
    legend.box.background = element_rect(fill = alpha("white", 0.90), color = "grey75", linewidth = 0.3),
    legend.box.margin = margin(4, 6, 4, 6)
  )
}

panel_theme <- function(show_legend = FALSE) {
  base <- theme_minimal(base_size = 10) +
    theme(
      panel.grid.major = element_line(color = "grey92", linewidth = 0.2),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "grey75", fill = NA, linewidth = 0.3),
      plot.title = element_text(size = 11, face = "bold", hjust = 0, margin = margin(b = 2)),
      plot.subtitle = element_text(size = 8, hjust = 0, color = "grey35", margin = margin(b = 4)),
      plot.tag = element_text(size = 12, face = "bold", hjust = 0, vjust = 1),
      plot.margin = margin(2, 2, 2, 2),
      axis.text = element_text(size = 7, color = "grey25"),
      axis.title = element_text(size = 8),
      legend.position = "none"
    )
  if (!show_legend) return(base)

  base +
    theme(
      legend.position = c(0.8, 0.05),
      legend.justification = c(0, 0),
      legend.title = element_text(size = 7.5, face = "bold"),
      legend.text = element_text(size = 6.5),
      legend.key.height = unit(0.35, "cm"),
      legend.background = element_rect(fill = alpha("white", 0.88), color = NA),
      legend.box.background = element_rect(fill = alpha("white", 0.88), color = "grey75", linewidth = 0.3),
      legend.box.margin = margin(2, 4, 2, 4)
    )
}

load_zoom_data <- function(args, n_cells = args$n_cells, window_buffer_m = args$window_buffer_m, include_buffer_examples = FALSE) {
  grid <- read_layer(file.path(
    DATA_DIR,
    paste0("Nairobi_cityroad_grid_", sprintf("h3_res%d_buf%dm", args$h3_res, as.integer(args$road_buffer)), ".gpkg")
  ))
  roads <- read_layer(file.path(INPUT_DIR, ROAD_GPKG))
  svi <- read_layer(file.path(INPUT_DIR, "Nairobi_SVI_point_gsvi_32737.gpkg"))
  waste <- read_layer(file.path(INPUT_DIR, "Nairobi_Waste_point_gsvi_32737.gpkg"))
  slums <- read_layer(file.path(INPUT_DIR, "Nairobi_slum_polygon_32737.gpkg"))
  sviwaste <- read_layer(file.path(DATA_DIR, "Nairobi_sviwaste_points.gpkg"))

  if (include_buffer_examples && n_cells == 1L) {
    panel_seed <- select_focus_cells(
      grid, args$density_min, args$density_max, 1L, args$interior_min_ratio
    )
    waste_pos_all <- sviwaste |> filter(.data$waste_positive == 1)
    focus <- select_layers_focus_cell(
      grid,
      waste_pos_all,
      args$density_min,
      args$density_max,
      exclude_h3 = panel_seed$h3_index[[1]],
      waste_min = args$layers_waste_min,
      waste_max = args$layers_waste_max,
      interior_min_ratio = args$interior_min_ratio
    )
  } else {
    focus <- select_focus_cells(
      grid, args$density_min, args$density_max, n_cells, args$interior_min_ratio
    )
  }
  window <- st_buffer(st_union(focus$geometry), dist = window_buffer_m)
  bbox <- st_bbox(window)

  if (n_cells == 1L) {
    context <- neighbor_context_cells(grid, focus)
  } else {
    context <- grid[st_intersects(grid, window, sparse = FALSE)[, 1], ] |>
      mutate(
        cell_role = if_else(.data$h3_index %in% focus$h3_index, "Focus H3 cell", "Context H3 cell")
      )
  }

  buffer_examples <- if (include_buffer_examples) {
    select_svi_buffer_examples(svi, focus, args$svi_buffer_examples, args$svi_buffer)
  } else {
    list(points = svi[0, ], buffers = svi[0, ])
  }

  roads_clip <- clip_lines(roads, window)
  local_coverage <- compute_window_roadsvi_coverage(roads, svi, window, args$svi_buffer)

  list(
    focus = focus,
    window = window,
    bbox = bbox,
    context = context,
    n_cells = n_cells,
    focus_labels = focus |> mutate(label = sprintf("%.1f", .data$road_length_density_km_per_km2)),
    focus_summary = focus |>
      st_drop_geometry() |>
      summarise(
        n_cells = n(),
        density_range = if (n() == 1L) {
          sprintf("%.1f km/km²", .data$road_length_density_km_per_km2[[1]])
        } else {
          sprintf(
            "%.1f–%.1f km/km²",
            min(.data$road_length_density_km_per_km2),
            max(.data$road_length_density_km_per_km2)
          )
        },
        segments = sum(.data$road_segment_count)
      ),
    n_roads_in_view = nrow(roads_clip),
    roads_clip = roads_clip,
    covered_clip = local_coverage$covered,
    uncovered_clip = local_coverage$uncovered,
    svi_clip = clip_points(svi, window),
    waste_clip = clip_points(waste, window),
    waste_pos_clip = sviwaste |> filter(.data$waste_positive == 1) |> clip_points(window),
    slums_clip = st_intersection(st_make_valid(slums), window),
    svi_buffer_examples = buffer_examples$buffers,
    svi_buffer_points = buffer_examples$points
  )
}

build_panel_figure <- function(d, args) {
  main_subtitle <- sprintf(
    "%d focus H3 cells (res %d) | road density %s | %s road segments in view",
    d$focus_summary$n_cells,
    args$h3_res,
    d$focus_summary$density_range,
    comma(d$n_roads_in_view)
  )

  dens_min <- min(d$focus$road_length_density_km_per_km2)
  dens_max <- max(d$focus$road_length_density_km_per_km2)

  p_city <- ggplot() +
    geom_sf(
      data = d$context |> filter(.data$cell_role == "Context H3 cell"),
      fill = "grey96",
      color = "grey82",
      linewidth = 0.15
    ) +
    geom_sf(
      data = d$context |> filter(.data$cell_role == "Focus H3 cell"),
      aes(fill = .data$road_length_density_km_per_km2),
      color = "#252525",
      linewidth = 0.55
    ) +
    geom_sf(data = d$slums_clip, fill = alpha("#756bb1", 0.18), color = NA) +
    geom_sf(data = d$focus, fill = NA, color = "#252525", linewidth = 0.75) +
    geom_sf_text(
      data = d$focus_labels,
      aes(label = .data$label),
      size = 2.8,
      color = "grey10",
      fontface = "bold"
    ) +
    scale_fill_viridis_c(
      option = "C",
      name = "Road density\n(km/km²)",
      labels = label_number(accuracy = 0.1),
      guide = guide_colorbar(
        barwidth = unit(0.35, "cm"),
        barheight = unit(1.6, "cm"),
        frame.colour = "grey75",
        frame.linewidth = 0.3,
        title.position = "top",
        title.hjust = 0.5
      )
    ) +
    panel_coords(d$bbox) +
    labs(
      title = "City → H3 grid",
      subtitle = "Hex = cityroad unit; fill = road length density"
    ) +
    panel_theme(show_legend = TRUE)

  p_roads <- ggplot() +
    geom_sf(data = d$focus, fill = alpha("#fee0d2", 0.35), color = "#636363", linewidth = 0.45) +
    geom_sf(data = d$roads_clip, color = "#252525", linewidth = 0.35, alpha = 0.92) +
    panel_coords(d$bbox) +
    labs(
      title = "City → Roads",
      subtitle = "Local cleaned OSM road segments"
    ) +
    panel_theme()

  p_svi <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = "grey55", linewidth = 0.35) +
    geom_sf(data = d$roads_clip, color = "#ececec", linewidth = 0.22, alpha = 0.85) +
    geom_sf(data = d$covered_clip, color = "#bdbdbd", linewidth = 0.32, alpha = 0.95) +
    geom_sf(data = d$uncovered_clip, color = "#ef3b2c", linewidth = 0.55, alpha = 0.95) +
    geom_sf(data = d$svi_clip, color = "#2171b5", size = 0.45, alpha = 0.65) +
    panel_coords(d$bbox) +
    labs(
      title = "Road → SVI coverage",
      subtitle = sprintf(
        "Blue = SVI panoid | Grey = covered metres | Red = road metres outside %dm SVI buffer",
        as.integer(args$svi_buffer)
      )
    ) +
    panel_theme()

  p_waste <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = "grey55", linewidth = 0.35) +
    geom_sf(data = d$roads_clip, color = "#e0e0e0", linewidth = 0.18, alpha = 0.8) +
    geom_sf(data = d$svi_clip, color = "#9ecae1", size = 0.4, alpha = 0.45) +
    geom_sf(data = d$waste_pos_clip, color = "#cb181d", size = 0.9, alpha = 0.95) +
    geom_sf(data = d$waste_clip, color = "#99000d", size = 0.55, alpha = 0.85, shape = 17) +
    panel_coords(d$bbox) +
    labs(
      title = "SVI → Waste",
      subtitle = "Red = waste-positive panoid | Triangles = waste detections"
    ) +
    panel_theme()

  (p_city | p_roads) / (p_svi | p_waste) +
    plot_layout(guides = "keep", widths = c(1, 1), heights = c(1, 1)) +
    plot_annotation(
      tag_levels = "A",
      tag_prefix = "",
      tag_suffix = "",
      title = "Nairobi coverage pipeline (zoomed exemplar)",
      subtitle = main_subtitle,
      caption = paste0(
        "Focus cells selected by road_length_density_km_per_km2 in ",
        args$density_min, "–", args$density_max,
        " km/km² | EPSG:", CRS_EA,
        " | Hierarchy: boundary → H3 → roads → SVI → waste"
      ),
      theme = theme(
        plot.tag = element_text(size = 12, face = "bold", hjust = 0, vjust = 1),
        plot.tag.position = c(0.02, 0.98),
        plot.title = element_text(face = "bold", size = 15, hjust = 0.5),
        plot.subtitle = element_text(size = 10, hjust = 0.5, color = "grey35"),
        plot.caption = element_text(size = 8, color = "grey45", hjust = 1)
      )
    )
}

build_layers_figure <- function(d, args) {
  cell_label <- if (d$n_cells == 1L) "focus H3 cell" else "focus H3 cells"
  main_subtitle <- sprintf(
    "%d %s (res %d) | road density %s | all pipeline layers combined",
    d$focus_summary$n_cells,
    cell_label,
    args$h3_res,
    d$focus_summary$density_range
  )

  roads_ok <- if (nrow(d$covered_clip)) {
    d$covered_clip |> mutate(layer = "Road (SVI covered)")
  } else {
    NULL
  }
  roads_gap <- if (nrow(d$uncovered_clip)) {
    d$uncovered_clip |> mutate(layer = "Road (no SVI cover)")
  } else {
    NULL
  }
  svi_pts <- if (nrow(d$svi_clip)) {
    d$svi_clip |> mutate(layer = "SVI panoid")
  } else {
    NULL
  }
  waste_pos <- if (nrow(d$waste_pos_clip)) {
    d$waste_pos_clip |> mutate(layer = "Waste-positive panoid")
  } else {
    NULL
  }
  svi_buffers <- d$svi_buffer_examples

  layer_order <- c(
    "Road (SVI covered)",
    "Road (no SVI cover)",
    "SVI panoid",
    "Waste-positive panoid"
  )
  color_values <- c(
    "Road (SVI covered)" = "#bdbdbd",
    "Road (no SVI cover)" = "#ef3b2c",
    "SVI panoid" = "#2171b5",
    "Waste-positive panoid" = "#cb181d"
  )
  shape_values <- c(
    "Road (SVI covered)" = 15,
    "Road (no SVI cover)" = 15,
    "SVI panoid" = 16,
    "Waste-positive panoid" = 17
  )

  line_layers <- bind_rows(roads_ok, roads_gap)
  active_layers <- intersect(
    layer_order,
    c(
      if (nrow(line_layers)) unique(line_layers$layer) else character(),
      if (!is.null(svi_pts)) "SVI panoid",
      if (!is.null(waste_pos)) "Waste-positive panoid"
    )
  )

  if (nrow(line_layers)) {
    line_layers <- line_layers |> mutate(layer = factor(.data$layer, levels = active_layers))
  }
  if (!is.null(svi_pts)) {
    svi_pts <- svi_pts |> mutate(layer = factor(.data$layer, levels = active_layers))
  }
  if (!is.null(waste_pos)) {
    waste_pos <- waste_pos |> mutate(layer = factor(.data$layer, levels = active_layers))
  }

  is_line <- active_layers %in% c("Road (SVI covered)", "Road (no SVI cover)")
  legend_override <- list(
    linewidth = ifelse(is_line, 1.1, NA_real_),
    linetype = ifelse(is_line, "solid", NA_character_),
    shape = ifelse(is_line, NA_real_, shape_values[active_layers]),
    size = ifelse(
      active_layers == "SVI panoid", 3.0,
      ifelse(active_layers == "Waste-positive panoid", 4.2, NA_real_)
    ),
    alpha = rep(1, length(active_layers))
  )

  p <- ggplot() +
    geom_sf(data = d$slums_clip, fill = alpha("#756bb1", 0.10), color = NA)

  if (nrow(line_layers)) {
    p <- p +
      geom_sf(
        data = line_layers,
        aes(color = .data$layer),
        linewidth = 0.42,
        alpha = 0.95
      )
  }

  if (nrow(d$context) > 0) {
    p <- p +
      geom_sf(
        data = d$context,
        fill = NA,
        color = "#666666",
        linewidth = 0.55,
        linetype = "solid"
      )
  }

  if (nrow(svi_buffers) > 0) {
    p <- p +
      geom_sf(
        data = svi_buffers,
        fill = alpha("#9ecae1", 0.10),
        color = alpha("#2171b5", 0.55),
        linewidth = 0.35,
        linetype = "3313"
      )
  }

  if (!is.null(svi_pts)) {
    p <- p +
      geom_sf(
        data = svi_pts,
        aes(color = .data$layer, shape = .data$layer),
        size = 1.9,
        alpha = 0.92
      )
  }
  if (!is.null(waste_pos)) {
    p <- p +
      geom_sf(
        data = waste_pos,
        aes(color = .data$layer, shape = .data$layer),
        size = 3.2,
        alpha = 0.95
      )
  }
  p <- p +
    geom_sf(
      data = d$focus,
      fill = NA,
      color = "#111111",
      linewidth = 1.25
    ) +
    scale_color_manual(
      name = sprintf("Focus H3 cell\n%s", d$focus$h3_index[[1]]),
      values = color_values[active_layers],
      drop = FALSE
    ) +
    scale_shape_manual(
      name = NULL,
      values = shape_values[active_layers],
      drop = FALSE
    ) +
    guides(
      color = guide_legend(
        override.aes = legend_override,
        ncol = 1
      ),
      shape = "none"
    ) +
    panel_coords(d$bbox) +
    labs(
      title = "Nairobi coverage pipeline (zoomed exemplar, all layers)",
      subtitle = main_subtitle,
      caption = paste0(
        "Bold hex = focus H3 cell (", args$density_min, "–", args$density_max,
        " km/km² road density); faint hex = neighbours clipped at view | Interior H3 cells only (ratio >= ",
        args$interior_min_ratio, ") | Dashed circles = ",
        as.integer(args$svi_buffer), " m SVI buffer examples | Road cover recomputed in view | EPSG:", CRS_EA,
        " | Hierarchy: H3 → roads → SVI → waste"
      ),
      x = "Easting (m)",
      y = "Northing (m)"
    ) +
    map_theme() +
    layers_legend_theme() +
    theme(
      plot.title = element_text(face = "bold", size = 16, hjust = 0.5),
      plot.subtitle = element_text(size = 11, hjust = 0.5, color = "grey35"),
      plot.caption = element_text(size = 9, color = "grey45", hjust = 1),
      axis.title = element_text(size = 11),
      axis.text = element_text(size = 9, color = "grey25")
    )

  p
}

args <- parse_args()
tag <- file_tag(args$h3_res, args$road_buffer, args$svi_buffer)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
message("Writing process zoom maps to ", FIG_DIR)

if (args$layout %in% c("panel", "both")) {
  d_panel <- load_zoom_data(args, n_cells = args$n_cells, window_buffer_m = args$window_buffer_m)
  message("Panel focus H3 cells: ", paste(d_panel$focus$h3_index, collapse = ", "))
  save_map(
    build_panel_figure(d_panel, args),
    file.path(FIG_DIR, paste0("Nairobi_process_zoom_", tag, "_panels.png")),
    width = 14,
    height = 12,
    dpi = 300
  )
}

if (args$layout %in% c("layers", "both")) {
  d_layers <- load_zoom_data(
    args,
    n_cells = args$layers_n_cells,
    window_buffer_m = args$layers_window_buffer_m,
    include_buffer_examples = TRUE
  )
  message("Layers focus H3 cell: ", paste(d_layers$focus$h3_index, collapse = ", "))
  save_map(
    build_layers_figure(d_layers, args),
    file.path(FIG_DIR, paste0("Nairobi_process_zoom_", tag, "_layers.png")),
    width = 10,
    height = 10,
    dpi = 300
  )
}

message("Done.")

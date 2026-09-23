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
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "chapter_arms.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))

ARM <- parse_arm_arg()

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
ROAD_GPKG <- "Nairobi_road_03_local_cleaned_32737.gpkg"
FIG_DIR_ROOT <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
MAIN_SVI_BUFFER_M <- 50L

# Main SVI buffer (50 m) stays in FIG_DIR_ROOT; sensitivity buffers go under buffer/
fig_out_dir <- function(svi_buffer) {
  if (as.integer(svi_buffer) == MAIN_SVI_BUFFER_M) {
    FIG_DIR_ROOT
  } else {
    file.path(FIG_DIR_ROOT, "buffer")
  }
}
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
    layout = "both",
    zoom_palette = "sage"
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
    if (grepl("^--zoom-palette=", arg)) defaults$zoom_palette <- sub("^--zoom-palette=", "", arg)
  }
  if (!defaults$layout %in% c("panel", "layers", "both")) {
    stop("--layout must be one of: panel, layers, both")
  }
  if (!defaults$zoom_palette %in% ZOOM_PALETTE_CHOICES) {
    stop(
      "--zoom-palette must be one of: ",
      paste(ZOOM_PALETTE_CHOICES, collapse = ", ")
    )
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
      plot.background = element_rect(fill = NA, color = NA),
      panel.background = element_rect(fill = NA, color = NA),
      panel.grid.major = element_line(color = "grey92", linewidth = 0.2),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "grey75", fill = NA, linewidth = 0.3),
      plot.title = element_text(size = 11, face = "bold", hjust = 0, margin = margin(b = 2)),
      plot.subtitle = element_text(size = 8, hjust = 0, color = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 4)),
      plot.tag = element_text(size = 12, face = "bold", hjust = 0, vjust = 1),
      plot.margin = margin(2, 2, 2, 2),
      axis.text = element_blank(),
      axis.title = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "none"
    )
  if (!show_legend) return(base)

  base +
    theme(
      legend.position = c(0.975, 0.03),
      legend.justification = c(1, 0),
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
  svi <- read_layer(file.path(INPUT_DIR, arm_filename("Nairobi_SVI_point", ARM)))
  waste <- read_layer(file.path(INPUT_DIR, arm_filename("Nairobi_Waste_point", ARM)))
  slums <- read_layer(file.path(INPUT_DIR, "Nairobi_slum_polygon_32737.gpkg"))
  boundary <- read_layer(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
  sviwaste <- read_layer(file.path(DATA_DIR, arm_filename("Nairobi_sviwaste_points", ARM)))

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
    city_grid = grid,
    boundary = boundary,
    svi_buffer_examples = buffer_examples$buffers,
    svi_buffer_points = buffer_examples$points
  )
}

build_panel_figure <- function(d, args, pal) {
  svi_buf <- as.integer(args$svi_buffer)
  gap_colour <- if (!is.null(pal$road_uncovered_soft)) pal$road_uncovered_soft else pal$road_uncovered
  density_unit <- "km km\u207b\u00b2"

  # Dark hexagon fills need a light label; the gradient spans the focus cells only
  dens <- d$focus_labels$road_length_density_km_per_km2
  dens_rel <- if (diff(range(dens)) > 0) {
    (dens - min(dens)) / diff(range(dens))
  } else {
    rep(0, length(dens))
  }
  label_colours <- ifelse(dens_rel > 0.55, pal$density_low, pal$hex_label)

  p_city <- ggplot() +
    geom_sf(
      data = d$context |> filter(.data$cell_role == "Context H3 cell"),
      fill = pal$context_fill,
      color = pal$context_edge,
      linewidth = 0.15
    ) +
    geom_sf(
      data = d$context |> filter(.data$cell_role == "Focus H3 cell"),
      aes(fill = .data$road_length_density_km_per_km2),
      color = pal$focus_edge,
      linewidth = 0.55
    ) +
    geom_sf(data = d$focus, fill = NA, color = pal$focus_edge, linewidth = 0.75) +
    geom_sf_text(
      data = d$focus_labels,
      aes(label = .data$label),
      size = 2.8,
      color = label_colours,
      fontface = "bold"
    ) +
    scale_fill_zoom_density(
      pal,
      name = paste0("Road density\n(", density_unit, ")"),
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
      title = "A. H3 analytical grid",
      subtitle = "Hexagon = analytical unit; fill = road length density"
    ) +
    panel_theme(show_legend = TRUE)

  p_roads <- ggplot() +
    geom_sf(data = d$focus, fill = alpha(pal$focus_fill, 0.55), color = pal$focus_edge, linewidth = 0.45) +
    geom_sf(data = d$roads_clip, color = pal$road, linewidth = 0.35, alpha = 0.92) +
    panel_coords(d$bbox) +
    labs(
      title = "B. Mapped-road network",
      subtitle = "Cleaned OpenStreetMap road segments"
    ) +
    panel_theme()

  p_svi <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = pal$context_edge, linewidth = 0.35) +
    geom_sf(data = d$roads_clip, color = pal$road_faint, linewidth = 0.22, alpha = 0.85) +
    geom_sf(data = d$covered_clip, color = pal$road_covered, linewidth = 0.36, alpha = 0.95) +
    geom_sf(data = d$uncovered_clip, color = gap_colour, linewidth = 0.4, alpha = 0.85) +
    geom_sf(data = d$svi_clip, color = pal$svi, size = 0.4, alpha = 0.5) +
    panel_coords(d$bbox) +
    labs(
      title = "C. GSVI-supported road network",
      subtitle = sprintf(
        "Green = road within %d m of a GSVI panorama; red = road without GSVI support",
        svi_buf
      )
    ) +
    panel_theme()

  p_waste <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = pal$context_edge, linewidth = 0.35) +
    geom_sf(data = d$roads_clip, color = pal$road_faint, linewidth = 0.18, alpha = 0.8) +
    geom_sf(data = d$svi_clip, color = pal$svi_light, size = 0.4, alpha = 0.45) +
    geom_sf(data = d$waste_pos_clip, color = pal$waste_pos, size = 1.5, alpha = 0.95, shape = 17) +
    panel_coords(d$bbox) +
    labs(
      title = "D. Waste-positive observations",
      subtitle = "Triangles = GSVI panoramas with at least one waste detection"
    ) +
    panel_theme()

  n_word <- c("one", "two", "three", "four", "five")
  cell_count <- d$focus_summary$n_cells
  cell_count_label <- if (cell_count <= length(n_word)) n_word[[cell_count]] else as.character(cell_count)
  observed_range <- sprintf(
    "%.1f\u2013%.1f",
    min(d$focus$road_length_density_km_per_km2),
    max(d$focus$road_length_density_km_per_km2)
  )

  (p_city | p_roads) / (p_svi | p_waste) +
    plot_layout(guides = "keep", widths = c(1, 1), heights = c(1, 1)) +
    plot_annotation(
      title = "Zoomed exemplar of the Nairobi observation pipeline",
      caption = paste0(
        "Note: The ", cell_count_label, " adjacent cells were selected from the ",
        args$density_min, "\u2013", args$density_max, " ", density_unit,
        " mapped-road-density range (observed range: ", observed_range, " ", density_unit, ").\n",
        "Road sections within ", svi_buf, " m of an available GSVI panorama were classified as GSVI-supported. ",
        "The exemplar was selected for visual clarity and is not representative of Nairobi."
      ),
      theme = theme(
        plot.title = element_text(face = "bold", size = 15, hjust = 0.5, margin = margin(b = 8)),
        plot.caption = element_text(
          size = 8.5,
          color = "grey35",
          hjust = 0.5,
          lineheight = 1.25,
          margin = margin(t = 10)
        )
      )
    )
}

build_layers_figure <- function(d, args, pal) {
  svi_buf <- as.integer(args$svi_buffer)
  road_covered_label <- sprintf("Road within %d m of GSVI", svi_buf)
  road_gap_label <- "Road without GSVI support"
  svi_label <- "GSVI panorama"
  waste_label <- "Waste-positive panorama"
  focus_label <- "Focus H3 cell boundary"
  buffer_label <- sprintf("%d m GSVI buffer", svi_buf)

  roads_ok <- if (nrow(d$covered_clip)) {
    d$covered_clip |> mutate(layer = road_covered_label)
  } else {
    NULL
  }
  roads_gap <- if (nrow(d$uncovered_clip)) {
    d$uncovered_clip |> mutate(layer = road_gap_label)
  } else {
    NULL
  }
  svi_pts <- if (nrow(d$svi_clip)) {
    d$svi_clip |> mutate(layer = svi_label)
  } else {
    NULL
  }
  waste_pos <- if (nrow(d$waste_pos_clip)) {
    d$waste_pos_clip |> mutate(layer = waste_label)
  } else {
    NULL
  }
  svi_buffers <- d$svi_buffer_examples
  focus_boundary <- if (nrow(d$focus) > 0) {
    d$focus |> mutate(layer = focus_label)
  } else {
    NULL
  }
  buffer_layer <- if (nrow(svi_buffers) > 0) {
    svi_buffers |> mutate(layer = buffer_label)
  } else {
    NULL
  }

  layer_order <- c(
    focus_label,
    road_covered_label,
    road_gap_label,
    svi_label,
    waste_label,
    buffer_label
  )
  color_values <- zoom_layer_colours(pal, svi_buf)
  shape_values <- setNames(
    c(NA_real_, 15, 15, 16, 17, NA_real_),
    layer_order
  )

  line_layers <- bind_rows(roads_ok, roads_gap)
  active_layers <- intersect(
    layer_order,
    c(
      if (!is.null(focus_boundary)) focus_label,
      if (nrow(line_layers)) unique(line_layers$layer) else character(),
      if (!is.null(svi_pts)) svi_label,
      if (!is.null(waste_pos)) waste_label,
      if (!is.null(buffer_layer)) buffer_label
    )
  )

  factorise <- function(x) {
    if (is.null(x) || !nrow(x)) return(x)
    x |> mutate(layer = factor(.data$layer, levels = active_layers))
  }
  line_layers <- factorise(line_layers)
  svi_pts <- factorise(svi_pts)
  waste_pos <- factorise(waste_pos)
  focus_boundary <- factorise(focus_boundary)
  buffer_layer <- factorise(buffer_layer)

  is_line <- active_layers %in% c(focus_label, road_covered_label, road_gap_label, buffer_label)
  is_buffer <- active_layers == buffer_label
  is_focus <- active_layers == focus_label
  legend_override <- list(
    linewidth = ifelse(
      is_focus, 1.35,
      ifelse(is_buffer, 0.85, ifelse(is_line, 1.1, NA_real_))
    ),
    linetype = ifelse(
      is_buffer, "3313",
      ifelse(is_line, "solid", NA_character_)
    ),
    shape = ifelse(is_line, NA_real_, shape_values[active_layers]),
    size = ifelse(
      active_layers == svi_label, 2.0,
      ifelse(active_layers == waste_label, 5.5, NA_real_)
    ),
    alpha = ifelse(active_layers == svi_label, 0.9, 1)
  )

  p <- ggplot() +
    geom_sf(data = d$slums_clip, fill = alpha(pal$slum, SLUM_ALPHA * 0.45), color = NA)

  if (!is.null(line_layers) && nrow(line_layers)) {
    p <- p +
      geom_sf(
        data = line_layers,
        aes(color = .data$layer),
        linewidth = 0.42,
        alpha = 0.95
      )
  }

  if (!is.null(buffer_layer)) {
    p <- p +
      geom_sf(
        data = buffer_layer,
        aes(color = .data$layer),
        fill = alpha(pal$svi_buffer_fill, 0.08),
        linewidth = 0.6,
        linetype = "3313"
      )
  }

  if (!is.null(svi_pts)) {
    p <- p +
      geom_sf(
        data = svi_pts,
        aes(color = .data$layer, shape = .data$layer),
        size = 1.3,
        alpha = 0.9
      )
  }
  if (!is.null(waste_pos)) {
    p <- p +
      geom_sf(
        data = waste_pos,
        aes(color = .data$layer, shape = .data$layer),
        size = 4.6,
        alpha = 0.95
      )
  }
  if (!is.null(focus_boundary)) {
    p <- p +
      geom_sf(
        data = focus_boundary,
        aes(color = .data$layer),
        fill = NA,
        linewidth = 1.25
      )
  }
  p <- p +
    scale_color_manual(
      name = NULL,
      values = color_values[active_layers],
      drop = FALSE,
      breaks = active_layers
    ) +
    scale_shape_manual(
      name = NULL,
      values = shape_values[active_layers],
      drop = FALSE,
      breaks = active_layers
    ) +
    guides(
      color = guide_legend(
        override.aes = legend_override,
        ncol = 1
      ),
      shape = "none"
    ) +
    panel_coords(d$bbox) +
    annotation_scale(
      location = "br",
      width_hint = 0.18,
      style = "ticks",
      line_width = 0.45,
      text_cex = 0.8,
      pad_x = unit(0.25, "cm"),
      pad_y = unit(0.25, "cm")
    ) +
    labs(
      title = "Zoomed illustration of the observation pipeline",
      x = NULL,
      y = NULL
    ) +
    map_theme(transparent_bg = TRUE, show_grid = FALSE) +
    layers_legend_theme() +
    theme(
      plot.title = element_text(face = "bold", size = 16, hjust = 0.5),
      plot.subtitle = element_text(size = 11, hjust = 0.5, color = CHAPTER_SUBTITLE_COLOUR),
      plot.caption = element_text(size = 9, color = CHAPTER_CAPTION_COLOUR, hjust = 0.5, margin = margin(t = 6)),
      axis.title = element_blank(),
      axis.text = element_blank(),
      axis.ticks = element_blank()
    )

  p
}

build_overview_inset_map <- function(d, pal) {
  focus_ids <- d$focus$h3_index
  city_grid <- d$city_grid |>
    mutate(is_focus = .data$h3_index %in% focus_ids)
  zoom_box <- st_as_sfc(st_bbox(d$window), crs = st_crs(d$boundary))

  ggplot() +
    geom_sf(
      data = d$boundary,
      fill = alpha(pal$context_fill, 0.45),
      color = pal$focus_edge,
      linewidth = 0.35
    ) +
    geom_sf(
      data = city_grid |> filter(!.data$is_focus),
      fill = alpha(pal$context_fill, 0.85),
      color = alpha(pal$context_edge, 0.55),
      linewidth = 0.06
    ) +
    geom_sf(
      data = city_grid |> filter(.data$is_focus),
      fill = alpha(pal$focus_edge, 0.45),
      color = pal$focus_outline,
      linewidth = 0.45
    ) +
    geom_sf(
      data = zoom_box,
      fill = NA,
      color = pal$focus_outline,
      linewidth = 0.55
    ) +
    coord_map_limits(d$boundary) +
    theme_void() +
    theme(
      # Border on the map panel only so the caption can sit outside the frame
      plot.background = element_rect(fill = alpha("white", 0.93), color = NA),
      panel.background = element_rect(fill = alpha("white", 0.93), color = NA),
      panel.border = element_rect(color = "grey70", fill = NA, linewidth = 0.35),
      plot.margin = margin(0, 0, 0, 0)
    )
}

build_overview_inset_label <- function() {
  ggplot() +
    annotate(
      "text",
      x = 0.5,
      y = 0.5,
      label = "Study area",
      fontface = "bold",
      size = 2.7,
      colour = "#2f2f2f"
    ) +
    scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
    theme_void() +
    theme(
      plot.background = element_rect(fill = NA, color = NA),
      plot.margin = margin(1.5, 0, 0, 0)
    )
}

build_overview_inset <- function(d, pal) {
  # Map on top (framed); label below, outside the frame
  build_overview_inset_map(d, pal) / build_overview_inset_label() +
    plot_layout(heights = c(1, 0.16))
}

build_layers_figure_with_inset <- function(d, args, pal) {
  # Pull panel flush to the top-right so the inset can sit on the frame
  main <- build_layers_figure(d, args, pal) +
    theme(plot.margin = margin(6, 0, 6, 6))
  inset <- build_overview_inset(d, pal)
  bb <- sf::st_bbox(d$boundary)
  asp <- as.numeric((bb[["xmax"]] - bb[["xmin"]]) / (bb[["ymax"]] - bb[["ymin"]]))
  # Geographic map height; total inset taller to fit the outside label
  label_ratio <- 0.16
  map_share <- 1 / (1 + label_ratio)
  inset_map_height <- 0.16
  inset_width <- asp * inset_map_height
  inset_height <- inset_map_height / map_share
  main + inset_element(
    inset,
    left = 1 - inset_width,
    bottom = 1 - inset_height,
    right = 1,
    top = 1,
    align_to = "panel",
    clip = TRUE
  )
}

save_zoom_maps <- function(args, palette_name, out_dir) {
  pal <- get_zoom_palette(palette_name)
  tag <- file_tag(args$h3_res, args$road_buffer, args$svi_buffer)
  suffix <- paste0(if (palette_name == "sage") "" else paste0("_", palette_name), arm_fig_suffix(ARM))

  message("Palette: ", palette_name, " — ", pal$label)

  if (args$layout %in% c("panel", "both")) {
    d_panel <- load_zoom_data(args, n_cells = args$n_cells, window_buffer_m = args$window_buffer_m)
    message("Panel focus H3 cells: ", paste(d_panel$focus$h3_index, collapse = ", "))
    save_map(
      build_panel_figure(d_panel, args, pal),
      file.path(out_dir, paste0("Nairobi_process_zoom_", tag, "_panels", suffix, ".png")),
      width = 14,
      height = 12,
      dpi = 300,
      bg = "transparent"
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
      build_layers_figure(d_layers, args, pal),
      file.path(out_dir, paste0("Nairobi_process_zoom_", tag, "_layers", suffix, ".png")),
      width = 10,
      height = 10,
      dpi = 300,
      bg = "transparent"
    )
    save_map(
      build_layers_figure_with_inset(d_layers, args, pal),
      file.path(out_dir, paste0("Nairobi_process_zoom_", tag, "_layers_inset", suffix, ".png")),
      width = 10,
      height = 10,
      dpi = 300,
      bg = "transparent"
    )
  }
}

args <- parse_args()

out_dir <- fig_out_dir(args$svi_buffer)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
message("Writing process zoom maps to ", out_dir)

palette_names <- if (args$zoom_palette == "all") {
  c("sage", "mixed", "earth")
} else {
  args$zoom_palette
}

for (palette_name in palette_names) {
  save_zoom_maps(args, palette_name, out_dir)
}

message("Done.")

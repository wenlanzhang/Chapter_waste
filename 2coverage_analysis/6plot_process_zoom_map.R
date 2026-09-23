#!/usr/bin/env Rscript
# Zoomed process map on the 100 m grid: grid → roads → SVI coverage → waste,
# for a compact block of cells (default 3 × 3 = 9 cells; --block-cols/--block-rows).
# Outputs: 4-panel schematic + single-map multi-layer version (+ inset).

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
# Observation wording follows the arm
OBS_NAME <- if (ARM == "gsvi") "GSVI" else "SVI"
OBS_POINT <- if (ARM == "gsvi") "GSVI panorama" else "SVI sampling point"

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
ROAD_GPKG <- "Nairobi_road_03_local_cleaned_32737.gpkg"
GRID_GPKG <- "1_Nairobi_cityroad_grid100m_32737.gpkg"
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737


parse_args <- function() {
  defaults <- list(
    svi_buffer = 50,
    block_cols = 3L,
    block_rows = 3L,
    density_min = 10,
    density_max = 30,
    window_buffer_m = 60,
    layers_window_buffer_m = 45,
    # Selection thresholds scale with block size (per cell) unless given explicitly
    panel_waste_min = 1L,
    panel_waste_max = NA_integer_,
    layers_waste_min = NA_integer_,
    layers_waste_max = NA_integer_,
    min_svi_points = NA_integer_,
    svi_buffer_examples = 4L,
    interior_min_dist_m = 500,
    seed_cell_id = NA_integer_,
    layers_seed_cell_id = NA_integer_,
    layout = "both",
    zoom_palette = "sage"
  )
  for (arg in commandArgs(trailingOnly = TRUE)) {
    if (grepl("^--svi-buffer-m=", arg)) defaults$svi_buffer <- as.numeric(sub("^--svi-buffer-m=", "", arg))
    if (grepl("^--block-cols=", arg)) defaults$block_cols <- as.integer(sub("^--block-cols=", "", arg))
    if (grepl("^--block-rows=", arg)) defaults$block_rows <- as.integer(sub("^--block-rows=", "", arg))
    if (grepl("^--density-min=", arg)) defaults$density_min <- as.numeric(sub("^--density-min=", "", arg))
    if (grepl("^--density-max=", arg)) defaults$density_max <- as.numeric(sub("^--density-max=", "", arg))
    if (grepl("^--window-buffer-m=", arg)) defaults$window_buffer_m <- as.numeric(sub("^--window-buffer-m=", "", arg))
    if (grepl("^--layers-window-buffer-m=", arg)) defaults$layers_window_buffer_m <- as.numeric(sub("^--layers-window-buffer-m=", "", arg))
    if (grepl("^--panel-waste-min=", arg)) defaults$panel_waste_min <- as.integer(sub("^--panel-waste-min=", "", arg))
    if (grepl("^--panel-waste-max=", arg)) defaults$panel_waste_max <- as.integer(sub("^--panel-waste-max=", "", arg))
    if (grepl("^--layers-waste-min=", arg)) defaults$layers_waste_min <- as.integer(sub("^--layers-waste-min=", "", arg))
    if (grepl("^--layers-waste-max=", arg)) defaults$layers_waste_max <- as.integer(sub("^--layers-waste-max=", "", arg))
    if (grepl("^--min-svi-points=", arg)) defaults$min_svi_points <- as.integer(sub("^--min-svi-points=", "", arg))
    if (grepl("^--svi-buffer-examples=", arg)) defaults$svi_buffer_examples <- as.integer(sub("^--svi-buffer-examples=", "", arg))
    if (grepl("^--interior-min-dist-m=", arg)) defaults$interior_min_dist_m <- as.numeric(sub("^--interior-min-dist-m=", "", arg))
    if (grepl("^--seed-cell-id=", arg)) defaults$seed_cell_id <- as.integer(sub("^--seed-cell-id=", "", arg))
    if (grepl("^--layers-seed-cell-id=", arg)) defaults$layers_seed_cell_id <- as.integer(sub("^--layers-seed-cell-id=", "", arg))
    if (grepl("^--layout=", arg)) defaults$layout <- sub("^--layout=", "", arg)
    if (grepl("^--zoom-palette=", arg)) defaults$zoom_palette <- sub("^--zoom-palette=", "", arg)
  }
  n_cells <- defaults$block_cols * defaults$block_rows
  if (is.na(defaults$min_svi_points)) defaults$min_svi_points <- 2L * n_cells
  if (is.na(defaults$panel_waste_max)) defaults$panel_waste_max <- max(6L, n_cells)
  if (is.na(defaults$layers_waste_min)) defaults$layers_waste_min <- max(2L, n_cells %/% 3L)
  if (is.na(defaults$layers_waste_max)) defaults$layers_waste_max <- max(6L, n_cells)
  if (!defaults$layout %in% c("panel", "layers", "both")) {
    stop("--layout must be one of: panel, layers, both")
  }
  if (!defaults$zoom_palette %in% ZOOM_PALETTE_CHOICES) {
    stop("--zoom-palette must be one of: ", paste(ZOOM_PALETTE_CHOICES, collapse = ", "))
  }
  defaults
}

file_tag <- function(args) sprintf("grid100m_%dx%d_svi%d", args$block_cols, args$block_rows, as.integer(args$svi_buffer))

read_layer <- function(path) {
  x <- st_read(path, quiet = TRUE) |> st_transform(CRS_EA)
  if (!"geometry" %in% names(x) && "geom" %in% names(x)) x <- x |> rename(geometry = geom)
  st_as_sf(x)
}

density_in_range <- function(x, min_val, max_val) x >= min_val & x <= max_val

# ---------------------------------------------------------------------------
# Block selection on the 100 m grid
# ---------------------------------------------------------------------------
# Shared-edge (rook) neighbours among a small local subset of cells
rook_neighbours <- function(cell, local) {
  hits <- st_relate(cell, local, pattern = "F***1****", sparse = TRUE)[[1]]
  local[hits, ]
}

# Step from `cell` to the rook neighbour lying most in direction (dx, dy)
step_cell <- function(cell, local, dx, dy) {
  nb <- rook_neighbours(cell, local)
  if (nrow(nb) == 0) return(NULL)
  c0 <- st_coordinates(st_centroid(st_geometry(cell)))
  cn <- st_coordinates(st_centroid(st_geometry(nb)))
  score <- (cn[, 1] - c0[1]) * dx + (cn[, 2] - c0[2]) * dy
  if (max(score) < 40) return(NULL)  # no neighbour in that direction
  nb[which.max(score), ]
}

# Build a cols × rows block with `seed` as its bottom-left cell; NULL if incomplete
build_block <- function(seed, grid, cols, rows) {
  local <- grid[st_intersects(grid, st_buffer(st_geometry(seed), 150 * max(cols, rows)), sparse = FALSE)[, 1], ]
  ids <- integer()
  row_start <- seed
  for (r in seq_len(rows)) {
    if (r > 1) {
      row_start <- step_cell(row_start, local, 0, 1)
      if (is.null(row_start)) return(NULL)
    }
    cell <- row_start
    ids <- c(ids, cell$cell_id)
    for (c in seq_len(cols - 1L)) {
      cell <- step_cell(cell, local, 1, 0)
      if (is.null(cell)) return(NULL)
      ids <- c(ids, cell$cell_id)
    }
  }
  if (length(unique(ids)) != cols * rows) return(NULL)
  grid |> filter(.data$cell_id %in% ids)
}

points_in_block <- function(block, points) {
  sum(st_intersects(points, st_union(st_geometry(block)), sparse = FALSE)[, 1])
}

# Pick a block whose cells all fall in the density range (and optionally carry
# waste_min..waste_max waste-positive points). Candidates are interior cells,
# tried in order of closeness to the middle of the density range.
select_block <- function(grid, args, svi_points, waste_points = NULL, waste_min = NULL, waste_max = NULL,
                         exclude_ids = integer(), seed_cell_id = NA_integer_, label = "block") {
  cols <- args$block_cols
  rows <- args$block_rows
  if (!is.na(seed_cell_id)) {
    seed <- grid |> filter(.data$cell_id == seed_cell_id)
    if (nrow(seed) == 0) stop("Seed cell ", seed_cell_id, " not found in grid.")
    block <- build_block(seed, grid, cols, rows)
    if (is.null(block)) stop("Cannot build a ", cols, "x", rows, " block from seed cell ", seed_cell_id)
    message("  ", label, ": seed cell ", seed_cell_id, " (manual)")
    return(block)
  }
  mid <- (args$density_min + args$density_max) / 2
  keep <- grid$is_interior &
    density_in_range(grid$road_density_km_per_km2, args$density_min, args$density_max) &
    !grid$cell_id %in% exclude_ids
  candidates <- grid[keep, ]
  candidates <- candidates[order(abs(candidates$road_density_km_per_km2 - mid)), ]
  if (nrow(candidates) == 0) {
    stop("No interior cells in density range ", args$density_min, "–", args$density_max, " km/km²")
  }
  n_try <- min(nrow(candidates), 2000L)
  for (i in seq_len(n_try)) {
    block <- build_block(candidates[i, ], grid, cols, rows)
    if (is.null(block)) next
    if (!all(density_in_range(block$road_density_km_per_km2, args$density_min, args$density_max))) next
    if (any(block$cell_id %in% exclude_ids)) next
    n_svi <- points_in_block(block, svi_points)
    if (n_svi < args$min_svi_points) next
    if (!is.null(waste_points)) {
      n_w <- points_in_block(block, waste_points)
      if (n_w < waste_min || n_w > waste_max) next
      message("  ", label, ": seed cell ", candidates$cell_id[i], " | ", n_svi, " SVI points | ", n_w, " waste-positive",
              " | density ", sprintf("%.1f–%.1f", min(block$road_density_km_per_km2), max(block$road_density_km_per_km2)), " km/km²")
    } else {
      message("  ", label, ": seed cell ", candidates$cell_id[i], " | ", n_svi, " SVI points",
              " | density ", sprintf("%.1f–%.1f", min(block$road_density_km_per_km2), max(block$road_density_km_per_km2)), " km/km²")
    }
    return(block)
  }
  stop("No ", cols, "x", rows, " block satisfied the selection criteria (tried ", n_try, " seeds). ",
       "Relax --density-min/--density-max or pass --seed-cell-id.")
}

select_svi_buffer_examples <- function(svi, focus, n_examples, buffer_m) {
  focus_union <- st_union(st_geometry(focus))
  in_focus <- svi[st_intersects(svi, focus_union, sparse = FALSE)[, 1], ]
  if (nrow(in_focus) == 0) return(list(points = in_focus, buffers = in_focus))

  cen <- st_centroid(focus_union)
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

# ---------------------------------------------------------------------------
# Window clipping + local metre-level coverage split
# ---------------------------------------------------------------------------
clip_lines <- function(lines, window) {
  cropped <- st_crop(lines, st_as_sfc(st_bbox(window)))
  out <- st_intersection(cropped, window)
  out <- out[!st_is_empty(out), ]
  if (nrow(out) == 0) return(out)
  out |> filter(st_geometry_type(.data$geometry) %in% c("LINESTRING", "MULTILINESTRING"))
}

extract_line_parts <- function(geom, min_length_m = 0.1) {
  if (length(geom) == 0 || all(st_is_empty(geom))) return(st_sfc(crs = st_crs(geom)))
  geom <- st_make_valid(geom)
  gt <- as.character(st_geometry_type(geom))
  parts <- st_sfc(crs = st_crs(geom))
  if ("LINESTRING" %in% gt) parts <- c(parts, geom[gt == "LINESTRING"])
  if ("MULTILINESTRING" %in% gt) {
    ml <- geom[gt == "MULTILINESTRING"]
    for (i in seq_along(ml)) parts <- c(parts, st_cast(ml[i], "LINESTRING"))
  }
  if ("GEOMETRYCOLLECTION" %in% gt) {
    gc <- geom[gt == "GEOMETRYCOLLECTION"]
    for (i in seq_along(gc)) {
      lines <- st_collection_extract(gc[i], "LINESTRING")
      if (length(lines)) parts <- c(parts, lines)
    }
  }
  if (length(parts) == 0) return(st_sfc(crs = st_crs(geom)))
  parts <- parts[!st_is_empty(parts)]
  len <- as.numeric(st_length(parts))
  parts[len >= min_length_m]
}

compute_window_roadsvi_coverage <- function(roads, svi, window, buffer_m, min_length_m = 0.1) {
  roads_clip <- clip_lines(roads, window)
  empty <- st_sf(coverage_status = character(), length_m = numeric(),
                 geometry = st_sfc(crs = st_crs(roads)), crs = st_crs(roads))
  if (nrow(roads_clip) == 0) return(list(covered = empty, uncovered = empty))

  reach <- st_buffer(window, dist = buffer_m)
  svi_use <- svi[st_intersects(svi, reach, sparse = FALSE)[, 1], ]
  if (nrow(svi_use) == 0) {
    unc <- roads_clip |> mutate(coverage_status = "uncovered", length_m = as.numeric(st_length(roads_clip)))
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
  as_sf <- function(parts, status) {
    if (!length(parts)) return(empty)
    st_sf(coverage_status = status, length_m = as.numeric(st_length(parts)),
          geometry = parts, crs = st_crs(roads_clip))
  }
  list(covered = as_sf(cov_parts, "covered"), uncovered = as_sf(unc_parts, "uncovered"))
}

clip_points <- function(points, window) st_intersection(points, window)

panel_coords <- function(bbox) {
  coord_sf(crs = map_crs(), xlim = c(bbox[["xmin"]], bbox[["xmax"]]),
           ylim = c(bbox[["ymin"]], bbox[["ymax"]]), datum = NA, expand = FALSE)
}

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
load_base_layers <- function(args) {
  grid <- read_layer(file.path(DATA_DIR, GRID_GPKG))
  boundary <- read_layer(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
  # Interior = centroid well inside the constituency, so the window never hits the edge
  boundary_line <- st_boundary(st_union(st_geometry(boundary)))
  grid$is_interior <- as.numeric(st_distance(st_centroid(st_geometry(grid)), boundary_line)) >= args$interior_min_dist_m
  list(
    grid = grid,
    boundary = boundary,
    roads = read_layer(file.path(INPUT_DIR, ROAD_GPKG)),
    svi = read_layer(file.path(INPUT_DIR, arm_filename("Nairobi_SVI_point", ARM))),
    waste = read_layer(file.path(INPUT_DIR, arm_filename("Nairobi_Waste_point", ARM))),
    sviwaste = read_layer(file.path(DATA_DIR, arm_filename("3_Nairobi_sviwaste_points", ARM)))
  )
}

build_zoom_data <- function(base, focus, args, window_buffer_m, include_buffer_examples = FALSE,
                            extra_top_frac = 0) {
  focus_union <- st_union(st_geometry(focus))
  bb <- st_bbox(st_buffer(focus_union, dist = window_buffer_m))
  # Optional extra map extent above the block (room for the study-area inset)
  bb[["ymax"]] <- bb[["ymax"]] + extra_top_frac * (bb[["ymax"]] - bb[["ymin"]])
  window <- st_as_sfc(bb)
  bbox <- st_bbox(window)

  context <- base$grid[st_intersects(base$grid, window, sparse = FALSE)[, 1], ] |>
    mutate(cell_role = if_else(.data$cell_id %in% focus$cell_id, "Focus cell", "Context cell"))

  buffer_examples <- if (include_buffer_examples) {
    select_svi_buffer_examples(base$svi, focus, args$svi_buffer_examples, args$svi_buffer)
  } else {
    list(points = base$svi[0, ], buffers = base$svi[0, ])
  }

  roads_clip <- clip_lines(base$roads, window)
  local_coverage <- compute_window_roadsvi_coverage(base$roads, base$svi, window, args$svi_buffer)
  waste_pos <- base$sviwaste |> filter(.data$waste_positive == 1)

  list(
    focus = focus,
    focus_union = focus_union,
    window = window,
    bbox = bbox,
    context = context,
    focus_labels = focus |> mutate(label = sprintf("%.1f", .data$road_density_km_per_km2)),
    n_focus = nrow(focus),
    roads_clip = roads_clip,
    covered_clip = local_coverage$covered,
    uncovered_clip = local_coverage$uncovered,
    svi_clip = clip_points(base$svi, window),
    waste_pos_clip = clip_points(waste_pos, window),
    boundary = base$boundary,
    svi_buffer_examples = buffer_examples$buffers,
    svi_buffer_points = buffer_examples$points
  )
}

# ---------------------------------------------------------------------------
# 4-panel figure
# ---------------------------------------------------------------------------
build_panel_figure <- function(d, args, pal) {
  svi_buf <- as.integer(args$svi_buffer)
  gap_colour <- if (!is.null(pal$road_uncovered_soft)) pal$road_uncovered_soft else pal$road_uncovered
  density_unit <- "km km⁻²"

  dens <- d$focus_labels$road_density_km_per_km2
  dens_rel <- if (diff(range(dens)) > 0) (dens - min(dens)) / diff(range(dens)) else rep(0, length(dens))
  label_colours <- ifelse(dens_rel > 0.55, pal$density_low, pal$hex_label)

  p_city <- ggplot() +
    geom_sf(data = d$context |> filter(.data$cell_role == "Context cell"),
            fill = pal$context_fill, color = pal$context_edge, linewidth = 0.15) +
    geom_sf(data = d$context |> filter(.data$cell_role == "Focus cell"),
            aes(fill = .data$road_density_km_per_km2), color = pal$focus_edge, linewidth = 0.45) +
    geom_sf(data = st_sf(geometry = d$focus_union), fill = NA, color = pal$focus_edge, linewidth = 0.9) +
    geom_sf_text(data = d$focus_labels, aes(label = .data$label), size = 2.8,
                 color = label_colours, fontface = "bold") +
    scale_fill_zoom_density(
      pal,
      name = paste0("Road density\n(", density_unit, ")"),
      labels = label_number(accuracy = 0.1),
      guide = guide_colorbar(barwidth = unit(0.35, "cm"), barheight = unit(1.6, "cm"),
                             frame.colour = "grey75", frame.linewidth = 0.3,
                             title.position = "top", title.hjust = 0.5)
    ) +
    panel_coords(d$bbox) +
    labs(title = "A. 100 m analytical grid",
         subtitle = "Cell = analytical unit; fill = mapped road density") +
    panel_theme(show_legend = TRUE)

  p_roads <- ggplot() +
    geom_sf(data = d$focus, fill = alpha(pal$focus_fill, 0.55), color = pal$focus_edge, linewidth = 0.35) +
    geom_sf(data = d$roads_clip, color = pal$road, linewidth = 0.5, alpha = 0.92) +
    panel_coords(d$bbox) +
    labs(title = "B. Mapped-road network", subtitle = "Cleaned OpenStreetMap road segments") +
    panel_theme()

  p_svi <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = pal$context_edge, linewidth = 0.3) +
    geom_sf(data = d$roads_clip, color = pal$road_faint, linewidth = 0.3, alpha = 0.85) +
    geom_sf(data = d$covered_clip, color = pal$road_covered, linewidth = 0.55, alpha = 0.95) +
    geom_sf(data = d$uncovered_clip, color = gap_colour, linewidth = 0.6, alpha = 0.85) +
    geom_sf(data = d$svi_clip, color = pal$svi, size = 0.9, alpha = 0.7) +
    panel_coords(d$bbox) +
    labs(
      title = sprintf("C. %s-supported road network", OBS_NAME),
      subtitle = sprintf("Green = road within %d m of a %s; red = road without %s support",
                         svi_buf, OBS_POINT, OBS_NAME)
    ) +
    panel_theme()

  p_waste <- ggplot() +
    geom_sf(data = d$focus, fill = NA, color = pal$context_edge, linewidth = 0.3) +
    geom_sf(data = d$roads_clip, color = pal$road_faint, linewidth = 0.25, alpha = 0.8) +
    geom_sf(data = d$svi_clip, color = pal$svi_light, size = 0.9, alpha = 0.6) +
    geom_sf(data = d$waste_pos_clip, color = pal$waste_pos, size = 2.6, alpha = 0.95, shape = 17) +
    panel_coords(d$bbox) +
    labs(title = "D. Waste-positive observations",
         subtitle = sprintf("Triangles = %ss with at least one waste detection", OBS_POINT)) +
    panel_theme()

  observed_range <- sprintf("%.1f–%.1f", min(dens), max(dens))
  (p_city | p_roads) / (p_svi | p_waste) +
    plot_layout(guides = "keep", widths = c(1, 1), heights = c(1, 1)) +
    plot_annotation(
      title = "Zoomed exemplar of the Nairobi observation pipeline",
      caption = paste0(
        "Note: The ", d$n_focus, " adjacent 100 m cells (", args$block_cols, " × ", args$block_rows,
        ") were selected from the ", args$density_min, "–", args$density_max, " ", density_unit,
        " mapped-road-density range (observed range: ", observed_range, " ", density_unit, ").\n",
        "Road sections within ", svi_buf, " m of an available ", OBS_POINT, " were classified as ",
        OBS_NAME, "-supported. The exemplar was selected for visual clarity and is not representative of Nairobi."
      ),
      theme = theme(
        plot.title = element_text(face = "bold", size = 15, hjust = 0.5, margin = margin(b = 8)),
        plot.caption = element_text(size = 8.5, color = "grey35", hjust = 0.5, lineheight = 1.25, margin = margin(t = 10))
      )
    )
}

# ---------------------------------------------------------------------------
# Single multi-layer figure
# ---------------------------------------------------------------------------
build_layers_figure <- function(d, args, pal) {
  svi_buf <- as.integer(args$svi_buffer)
  road_covered_label <- sprintf("Road within %d m of %s", svi_buf, OBS_NAME)
  road_gap_label <- sprintf("Road without %s support", OBS_NAME)
  svi_label <- OBS_POINT
  waste_label <- sprintf("Waste-positive %s", tolower(sub("^\\w+ ", "", OBS_POINT)))
  focus_label <- sprintf("Focus 100 m cells (%d)", d$n_focus)
  buffer_label <- sprintf("%d m %s buffer", svi_buf, OBS_NAME)

  roads_ok <- if (nrow(d$covered_clip)) d$covered_clip |> mutate(layer = road_covered_label) else NULL
  roads_gap <- if (nrow(d$uncovered_clip)) d$uncovered_clip |> mutate(layer = road_gap_label) else NULL
  svi_pts <- if (nrow(d$svi_clip)) d$svi_clip |> mutate(layer = svi_label) else NULL
  waste_pos <- if (nrow(d$waste_pos_clip)) d$waste_pos_clip |> mutate(layer = waste_label) else NULL
  focus_boundary <- if (nrow(d$focus) > 0) d$focus |> mutate(layer = focus_label) else NULL
  buffer_layer <- if (nrow(d$svi_buffer_examples) > 0) d$svi_buffer_examples |> mutate(layer = buffer_label) else NULL

  layer_order <- c(focus_label, road_covered_label, road_gap_label, svi_label, waste_label, buffer_label)
  # zoom_layer_colours() keys by legacy GSVI labels; map onto the current wording by position
  legacy <- zoom_layer_colours(pal, svi_buf)
  color_values <- setNames(unname(legacy), layer_order)
  shape_values <- setNames(c(NA_real_, 15, 15, 16, 17, NA_real_), layer_order)

  line_layers <- bind_rows(roads_ok, roads_gap)
  active_layers <- intersect(layer_order, c(
    if (!is.null(focus_boundary)) focus_label,
    if (nrow(line_layers)) unique(line_layers$layer) else character(),
    if (!is.null(svi_pts)) svi_label,
    if (!is.null(waste_pos)) waste_label,
    if (!is.null(buffer_layer)) buffer_label
  ))
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
    linewidth = ifelse(is_focus, 1.35, ifelse(is_buffer, 0.85, ifelse(is_line, 1.1, NA_real_))),
    linetype = ifelse(is_buffer, "3313", ifelse(is_line, "solid", NA_character_)),
    shape = ifelse(is_line, NA_real_, shape_values[active_layers]),
    size = ifelse(active_layers == svi_label, 2.0, ifelse(active_layers == waste_label, 5.5, NA_real_)),
    alpha = ifelse(active_layers == svi_label, 0.9, 1)
  )

  p <- ggplot() +
    # faint internal cell edges so the block reads as 100 m cells
    geom_sf(data = d$context, fill = NA, color = alpha(pal$context_edge, 0.6), linewidth = 0.2)

  if (!is.null(line_layers) && nrow(line_layers)) {
    p <- p + geom_sf(data = line_layers, aes(color = .data$layer), linewidth = 0.7, alpha = 0.95)
  }
  if (!is.null(buffer_layer)) {
    p <- p + geom_sf(data = buffer_layer, aes(color = .data$layer),
                     fill = alpha(pal$svi_buffer_fill, 0.08), linewidth = 0.6, linetype = "3313")
  }
  if (!is.null(svi_pts)) {
    p <- p + geom_sf(data = svi_pts, aes(color = .data$layer, shape = .data$layer), size = 1.8, alpha = 0.9)
  }
  if (!is.null(waste_pos)) {
    p <- p + geom_sf(data = waste_pos, aes(color = .data$layer, shape = .data$layer), size = 5, alpha = 0.95)
  }
  if (!is.null(focus_boundary)) {
    p <- p + geom_sf(data = focus_boundary, aes(color = .data$layer), fill = NA, linewidth = 0.55) +
      geom_sf(data = st_sf(geometry = d$focus_union), fill = NA, color = color_values[[focus_label]], linewidth = 1.25)
  }
  p +
    scale_color_manual(name = NULL, values = color_values[active_layers], drop = FALSE, breaks = active_layers) +
    scale_shape_manual(name = NULL, values = shape_values[active_layers], drop = FALSE, breaks = active_layers) +
    guides(color = guide_legend(override.aes = legend_override, ncol = 1), shape = "none") +
    panel_coords(d$bbox) +
    annotation_scale(location = "br", width_hint = 0.18, style = "ticks", line_width = 0.45,
                     text_cex = 0.8, pad_x = unit(0.25, "cm"), pad_y = unit(0.25, "cm")) +
    labs(title = "Zoomed illustration of the observation pipeline", x = NULL, y = NULL) +
    map_theme(transparent_bg = TRUE, show_grid = FALSE) +
    layers_legend_theme() +
    theme(
      plot.title = element_text(face = "bold", size = 16, hjust = 0.5),
      plot.subtitle = element_text(size = 11, hjust = 0.5, color = CHAPTER_SUBTITLE_COLOUR),
      plot.caption = element_text(size = 9, color = CHAPTER_CAPTION_COLOUR, hjust = 0.5, margin = margin(t = 6)),
      axis.title = element_blank(), axis.text = element_blank(), axis.ticks = element_blank()
    )
}

# ---------------------------------------------------------------------------
# Study-area inset (block is ~300 m, so it is marked with a point at city scale)
# ---------------------------------------------------------------------------
build_overview_inset <- function(d, pal) {
  marker <- st_sf(geometry = st_centroid(d$focus_union))
  bb <- st_bbox(d$boundary)
  ggplot() +
    geom_sf(data = d$boundary, fill = alpha(pal$context_fill, 0.7), color = pal$focus_edge, linewidth = 0.35) +
    geom_sf(data = marker, shape = 21, size = 3.2, stroke = 0.9,
            fill = alpha(pal$focus_edge, 0.55), color = pal$focus_outline) +
    # Label inside the frame, bottom-right (the constituency's south-east is empty there)
    annotate("text", x = bb[["xmax"]], y = bb[["ymin"]], label = "Study area",
             hjust = 1.05, vjust = -0.4, fontface = "bold", size = 2.7, colour = "#2f2f2f") +
    coord_map_limits(d$boundary) +
    theme_void() +
    theme(
      plot.background = element_rect(fill = alpha("white", 0.95), color = NA),
      panel.background = element_rect(fill = alpha("white", 0.95), color = NA),
      panel.border = element_rect(color = "grey70", fill = NA, linewidth = 0.35),
      plot.margin = margin(0, 0, 0, 0)
    )
}

INSET_HEIGHT_FRAC <- 0.17  # share of panel height taken by the study-area inset

build_layers_figure_with_inset <- function(d, args, pal) {
  main <- build_layers_figure(d, args, pal) + theme(plot.margin = margin(6, 6, 6, 0))
  inset <- build_overview_inset(d, pal)
  bb <- sf::st_bbox(d$boundary)
  asp <- as.numeric((bb[["xmax"]] - bb[["xmin"]]) / (bb[["ymax"]] - bb[["ymin"]]))
  inset_width <- asp * INSET_HEIGHT_FRAC
  # Top-left corner (legend sits bottom-left); the window was extended upward so
  # the inset sits over context, not over the focus block
  main + inset_element(inset, left = 0, bottom = 1 - INSET_HEIGHT_FRAC, right = inset_width, top = 1,
                       align_to = "panel", clip = TRUE)
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
save_zoom_maps <- function(args, palette_name, out_dir, base) {
  pal <- get_zoom_palette(palette_name)
  tag <- file_tag(args)
  suffix <- paste0(if (palette_name == "sage") "" else paste0("_", palette_name), arm_fig_suffix(ARM))
  message("Palette: ", palette_name, " — ", pal$label)

  panel_block <- NULL
  waste_pos <- base$sviwaste |> filter(.data$waste_positive == 1)
  if (args$layout %in% c("panel", "both")) {
    panel_block <- select_block(
      base$grid, args, base$svi, waste_points = waste_pos,
      waste_min = args$panel_waste_min, waste_max = args$panel_waste_max,
      seed_cell_id = args$seed_cell_id, label = "Panel block"
    )
    d_panel <- build_zoom_data(base, panel_block, args, args$window_buffer_m)
    save_map(build_panel_figure(d_panel, args, pal),
             file.path(out_dir, paste0("6_Nairobi_process_zoom_", tag, "_panels", suffix, ".png")),
             width = 14, height = 12, dpi = 300, bg = "transparent")
  }

  if (args$layout %in% c("layers", "both")) {
    layers_block <- select_block(
      base$grid, args, base$svi, waste_points = waste_pos,
      waste_min = args$layers_waste_min, waste_max = args$layers_waste_max,
      exclude_ids = if (is.null(panel_block)) integer() else panel_block$cell_id,
      seed_cell_id = args$layers_seed_cell_id, label = "Layers block"
    )
    d_layers <- build_zoom_data(base, layers_block, args, args$layers_window_buffer_m, include_buffer_examples = TRUE)
    save_map(build_layers_figure(d_layers, args, pal),
             file.path(out_dir, paste0("6_Nairobi_process_zoom_", tag, "_layers", suffix, ".png")),
             width = 10, height = 10, dpi = 300, bg = "transparent")
    d_layers_inset <- build_zoom_data(base, layers_block, args, args$layers_window_buffer_m,
                                      include_buffer_examples = TRUE, extra_top_frac = INSET_HEIGHT_FRAC + 0.02)
    save_map(build_layers_figure_with_inset(d_layers_inset, args, pal),
             file.path(out_dir, paste0("6_Nairobi_process_zoom_", tag, "_layers_inset", suffix, ".png")),
             width = 10, height = 10, dpi = 300, bg = "transparent")
  }
}

args <- parse_args()
out_dir <- FIG_DIR
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
message("Writing process zoom maps to ", out_dir)

base <- load_base_layers(args)
palette_names <- if (args$zoom_palette == "all") c("sage", "mixed", "earth") else args$zoom_palette
for (palette_name in palette_names) save_zoom_maps(args, palette_name, out_dir, base)
message("Done.")

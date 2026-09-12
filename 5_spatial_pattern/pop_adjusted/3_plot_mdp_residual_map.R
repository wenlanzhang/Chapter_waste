#!/usr/bin/env Rscript
# Population-adjusted residual / excess-occurrence map (MDP panorama residuals).
#
# Maps where observed waste occurrence is higher (brown) or lower (blue) than
# expected after MDP:
#   waste ~ s(signed distance) + s(log1p(population)) + year
#
# Distinct from the two-panel adjusted-effects figure: here the question is
# where the model still under- or over-predicts, not the adjusted smooths.

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
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "..", "R", "chapter_colours.R"))
source(file.path(script_dir, "..", "..", "R", "mitigation_map_theme.R"))

trailing <- commandArgs(trailingOnly = TRUE)
get_opt <- function(name, default = NULL) {
  hit <- grep(paste0("^--", name, "="), trailing, value = TRUE)
  if (length(hit)) sub(paste0("^--", name, "="), "", hit[[1]]) else default
}

data_subdir <- get_opt("data-subdir", "")
fig_subdir <- get_opt("fig-subdir", data_subdir)
pop_caption <- get_opt(
  "pop-caption",
  "WorldPop Constrained Kenya 2024 (100 m), static density covariate (not matched to panorama year)."
)
run_hint <- get_opt(
  "run-hint",
  "python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py --residuals-only"
)

DATA_ROOT <- chapter_data_root
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
POP_DIR <- if (nzchar(data_subdir)) {
  file.path(DATA_ROOT, "5_spatial_pattern", "pop_adjusted", data_subdir)
} else {
  file.path(DATA_ROOT, "5_spatial_pattern", "pop_adjusted")
}

fig_root <- normalizePath(
  file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "pop_adjusted"),
  mustWork = FALSE
)
if (basename(normalizePath(script_dir)) == "worldpop_2020") {
  fig_root <- normalizePath(
    file.path(script_dir, "..", "..", "..", "Figure", "5_spatial_pattern", "pop_adjusted"),
    mustWork = FALSE
  )
}
FIG_DIR <- if (nzchar(fig_subdir)) {
  file.path(fig_root, fig_subdir)
} else {
  fig_root
}

WGS84 <- 4326L
PROJECTED_CRS <- 32737L
HEX_BINS <- 70L
MIN_HEX_N <- 8L

# Diverging chapter palette: sage green (deficit) ↔ cream ↔ waste brown (excess)
RESID_LOW <- "#657359"
RESID_MID <- "#F1E4DB"
RESID_HIGH <- "#6B4226"
SLUM_FILL <- "#496142"
SLUM_EDGE <- "#112721"
ANNOT_COLOUR <- "#991f00"
AXIS_COLOUR <- "#4D2D18"

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

resolve_input <- function(filename) {
  candidates <- c(
    file.path(POP_DIR, filename),
    file.path(script_dir, filename)
  )
  for (p in candidates) {
    if (file.exists(p)) return(p)
  }
  candidates[[1]]
}

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

hex_summary_sf <- function(pts, z_col, bins = HEX_BINS, min_n = MIN_HEX_N) {
  mean_layer <- ggplot_build(
    ggplot(pts, aes(x = lon, y = lat, z = .data[[z_col]])) +
      stat_summary_hex(fun = mean, bins = bins)
  )$data[[1]]
  count_layer <- ggplot_build(
    ggplot(pts, aes(x = lon, y = lat, z = .data[[z_col]])) +
      stat_summary_hex(fun = length, bins = bins)
  )$data[[1]]

  need <- c("x", "y", "width", "height", "value")
  if (!all(need %in% names(mean_layer)) || !all(c("x", "y", "value") %in% names(count_layer))) {
    stop("stat_summary_hex did not return expected columns")
  }

  mean_df <- mean_layer[, c("x", "y", "width", "height", "value")]
  names(mean_df)[names(mean_df) == "value"] <- "mean_resid"
  count_df <- count_layer[, c("x", "y", "value")]
  names(count_df)[names(count_df) == "value"] <- "n"

  # Match cells on rounded centres (floating-point safe)
  key <- function(df) paste(round(df$x, 8), round(df$y, 8), sep = "_")
  mean_df$key <- key(mean_df)
  count_df$key <- key(count_df)
  ok <- merge(
    mean_df,
    count_df[, c("key", "n")],
    by = "key",
    all.x = TRUE
  )
  ok <- ok[is.finite(ok$mean_resid) & is.finite(ok$n) & ok$n >= min_n, , drop = FALSE]
  if (nrow(ok) == 0) {
    stop("No hex cells with >= ", min_n, " panoramas for ", z_col)
  }

  polys <- lapply(seq_len(nrow(ok)), function(i) {
    cx <- ok$x[i]
    cy <- ok$y[i]
    w <- ok$width[i]
    h <- ok$height[i]
    dx <- c(0, w / 2, w / 2, 0, -w / 2, -w / 2, 0)
    dy <- c(h / 2, h / 4, -h / 4, -h / 2, -h / 4, h / 4, h / 2)
    st_polygon(list(cbind(cx + dx, cy + dy)))
  })
  st_sf(
    mean_resid = ok$mean_resid,
    n = ok$n,
    geometry = st_sfc(polys, crs = WGS84)
  )
}

add_landmarks <- function(p) {
  p +
    geom_point(
      data = DANDORA,
      aes(x = lon, y = lat),
      shape = 21,
      fill = ANNOT_COLOUR,
      colour = "black",
      size = 3.4,
      stroke = 0.55,
      inherit.aes = FALSE
    ) +
    geom_text(
      data = DANDORA,
      aes(x = lon - 0.028, y = lat + 0.012, label = name),
      colour = ANNOT_COLOUR,
      fontface = "bold",
      size = 3.8,
      inherit.aes = FALSE
    ) +
    geom_point(
      data = MAJOR_SETTLEMENTS,
      aes(x = lon, y = lat),
      shape = 4,
      colour = ANNOT_COLOUR,
      size = 3.2,
      stroke = 1.05,
      inherit.aes = FALSE
    ) +
    geom_text_repel(
      data = MAJOR_SETTLEMENTS,
      aes(x = lon, y = lat, label = name),
      colour = ANNOT_COLOUR,
      fontface = "bold",
      size = 3.6,
      box.padding = 0.35,
      point.padding = 0.25,
      segment.color = alpha(ANNOT_COLOUR, 0.4),
      segment.size = 0.3,
      min.segment.length = 0,
      max.overlaps = Inf,
      seed = 42,
      bg.color = "white",
      bg.r = 0.08,
      show.legend = FALSE
    )
}

build_residual_map <- function(
  hex_sf,
  boundary,
  slums,
  lim,
  fill_name,
  title,
  subtitle,
  caption = NULL,
  fill_labels = waiver()
) {
  hex_sf <- hex_sf |>
    mutate(mean_resid_plot = pmax(pmin(mean_resid, lim), -lim))

  p <- ggplot() +
    geom_sf(data = boundary, fill = "grey96", colour = NA) +
    geom_sf(
      data = hex_sf,
      aes(fill = mean_resid_plot),
      colour = alpha("grey35", 0.18),
      linewidth = 0.12
    ) +
    scale_fill_gradient2(
      name = fill_name,
      low = RESID_LOW,
      mid = RESID_MID,
      high = RESID_HIGH,
      midpoint = 0,
      limits = c(-lim, lim),
      oob = squish,
      breaks = pretty_breaks(n = 5),
      labels = fill_labels,
      guide = guide_colourbar(
        title.position = "top",
        title.hjust = 0.5,
        direction = "horizontal",
        barwidth = unit(3.4, "cm"),
        barheight = unit(0.42, "cm"),
        ticks.colour = "grey30",
        frame.colour = "grey40"
      )
    ) +
    geom_sf(
      data = slums,
      fill = alpha(SLUM_FILL, 0.12),
      colour = alpha(SLUM_EDGE, 0.55),
      linewidth = 0.28
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 0.95)

  p <- add_landmarks(p) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = title,
      subtitle = subtitle,
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(12) +
    theme(
      plot.title = element_text(
        face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f",
        margin = margin(b = 3)
      ),
      plot.subtitle = element_text(
        size = 9.5, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 6)
      ),
      plot.caption = element_blank(),
      legend.position = "inside",
      legend.position.inside = c(0.985, 0.02),
      legend.justification = c(1, 0),
      legend.direction = "horizontal",
      legend.background = element_rect(
        fill = alpha("white", 0.94),
        colour = "grey78",
        linewidth = 0.35
      ),
      legend.box.margin = margin(4, 6, 4, 6),
      legend.title = element_text(size = 8.5, colour = "#2f2f2f", face = "bold"),
      legend.text = element_text(size = 8, colour = "#2f2f2f")
    )
  mitigation_map_decorations(p)
}

resid_path <- resolve_input("Nairobi_pop_adjusted_mdp_residuals.csv")
if (!file.exists(resid_path)) {
  stop(
    "Missing MDP residuals. Run:\n  ", run_hint, "\n",
    "Expected: ", resid_path
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

message("Reading residuals: ", resid_path)
resid <- read.csv(resid_path, stringsAsFactors = FALSE)
need <- c("x", "y", "resid_pearson", "resid_response", "waste_positive")
missing <- setdiff(need, names(resid))
if (length(missing)) {
  stop("Residual CSV missing columns: ", paste(missing, collapse = ", "))
}

resid <- resid |>
  filter(
    is.finite(x), is.finite(y),
    is.finite(resid_pearson), is.finite(resid_response)
  )

pts <- st_as_sf(
  resid,
  coords = c("x", "y"),
  crs = PROJECTED_CRS,
  remove = FALSE
) |>
  st_transform(WGS84)

coords <- st_coordinates(pts)
pts <- pts |>
  mutate(lon = coords[, 1], lat = coords[, 2])

message("Reading boundary / settlements...")
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))
slum_path <- file.path(INPUT_DIR, "Nairobi_slum_cluster_polygon_32737.gpkg")
if (file.exists(slum_path)) {
  slum_clusters <- read_wgs84(slum_path)
  slums <- st_sf(
    geometry = st_make_valid(st_union(st_geometry(slum_clusters))),
    crs = st_crs(slum_clusters)
  )
} else {
  slums <- read_wgs84(file.path(INPUT_DIR, "Nairobi_slum_polygon_32737.gpkg"))
}

n_pano <- nrow(pts)
n_pos <- sum(pts$waste_positive == 1L)
mean_pred <- if ("pred_prob" %in% names(pts)) {
  mean(pts$pred_prob, na.rm = TRUE)
} else {
  NA_real_
}

message("Building Pearson residual hex map...")
hex_p <- hex_summary_sf(pts, "resid_pearson")
lim_p <- max(as.numeric(quantile(abs(hex_p$mean_resid), 0.98, na.rm = TRUE)), 0.25)

subtitle_p <- sprintf(
  "Hex mean Pearson residual | n = %s panoramas (%s waste+)%s",
  format(n_pano, big.mark = ",", trim = TRUE),
  format(n_pos, big.mark = ",", trim = TRUE),
  if (is.finite(mean_pred)) {
    sprintf(" | mean MDP P(waste+) = %.1f%%", 100 * mean_pred)
  } else {
    ""
  }
)

p_pearson <- build_residual_map(
  hex_sf = hex_p,
  boundary = boundary,
  slums = slums,
  lim = lim_p,
  fill_name = "Mean Pearson\nresidual",
  title = "Population-adjusted residual / excess-occurrence map",
  subtitle = subtitle_p
)

size <- mitigation_fig_size(boundary, width = 9.2, title_pad = 0.85)
out_p <- file.path(FIG_DIR, "Pop_adjusted_mdp_residual_map.png")
ggsave(
  out_p,
  plot = p_pearson,
  width = size$width,
  height = size$height,
  dpi = 400,
  bg = "white"
)
message("Wrote ", out_p, " (", round(size$width, 2), " x ", round(size$height, 2), " in)")

message("Building response residual (excess probability) hex map...")
hex_r <- hex_summary_sf(pts, "resid_response")
lim_r <- max(as.numeric(quantile(abs(hex_r$mean_resid), 0.98, na.rm = TRUE)), 0.02)

p_response <- build_residual_map(
  hex_sf = hex_r,
  boundary = boundary,
  slums = slums,
  lim = lim_r,
  fill_name = "Mean response\nresidual (y − μ)",
  title = "Population-adjusted excess probability map",
  subtitle = sprintf(
    "Hex mean response residual (y − predicted P) | n = %s",
    format(n_pano, big.mark = ",", trim = TRUE)
  ),
  fill_labels = label_number(accuracy = 0.01)
)

out_r <- file.path(FIG_DIR, "Pop_adjusted_mdp_excess_prob_map.png")
ggsave(
  out_r,
  plot = p_response,
  width = size$width,
  height = size$height,
  dpi = 400,
  bg = "white"
)
message("Wrote ", out_r)

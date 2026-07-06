# Shared ggplot2 map styling for Chapter_waste figures.

library(ggplot2)
library(ggspatial)

get_repo_root <- function(script_dir) {
  normalizePath(file.path(script_dir, ".."))
}

source_chapter_colours <- function(script_dir) {
  source(file.path(get_repo_root(script_dir), "R", "chapter_colours.R"))
}

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg)) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  }
  "."
}

.chapter_colours_path <- file.path(get_script_dir(), "..", "R", "chapter_colours.R")
if (file.exists(.chapter_colours_path) && !exists("CHAPTER_AXIS_COLOUR")) {
  source(.chapter_colours_path)
}

bbox_limits <- function(x) {
  bb <- sf::st_bbox(x)
  list(
    xmin = unname(bb["xmin"]),
    xmax = unname(bb["xmax"]),
    ymin = unname(bb["ymin"]),
    ymax = unname(bb["ymax"])
  )
}

coord_map_limits <- function(x, crs = map_crs(), expand = 0) {
  bb <- bbox_limits(x)
  coord_sf(
    crs = crs,
    xlim = c(bb$xmin, bb$xmax),
    ylim = c(bb$ymin, bb$ymax),
    expand = expand,
    datum = NA,
    clip = "on"
  )
}

map_figure_dims <- function(x, base_size = 10) {
  bb <- bbox_limits(x)
  width_m <- bb$xmax - bb$xmin
  height_m <- bb$ymax - bb$ymin
  if (!is.finite(width_m) || !is.finite(height_m) || height_m <= 0) {
    return(list(width = base_size, height = base_size))
  }
  ratio <- width_m / height_m
  if (ratio >= 1) {
    list(width = base_size, height = base_size / ratio)
  } else {
    list(height = base_size, width = base_size * ratio)
  }
}

map_theme <- function(transparent_bg = FALSE, show_grid = TRUE) {
  base <- theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      panel.grid.major = if (show_grid) element_line(color = "grey90", linewidth = 0.25) else element_blank(),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "grey70", fill = NA, linewidth = 0.4),
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, color = CHAPTER_TITLE_COLOUR, margin = margin(b = 4)),
      plot.subtitle = element_text(size = 10, hjust = 0.5, color = CHAPTER_TITLE_COLOUR, margin = margin(b = 6)),
      plot.caption = element_text(size = 8, color = CHAPTER_AXIS_COLOUR, hjust = 1),
      axis.text = element_text(size = 8, color = CHAPTER_AXIS_COLOUR),
      axis.title = element_text(size = 10, color = CHAPTER_AXIS_COLOUR),
      legend.title = element_text(size = 9, face = "bold"),
      legend.text = element_text(size = 8),
      legend.key.height = unit(0.45, "cm"),
      legend.position = c(0.98, 0.03),
      legend.justification = c(1, 0),
      legend.background = element_rect(fill = alpha("white", 0.88), color = NA),
      legend.box.background = element_rect(fill = alpha("white", 0.88), color = "grey75", linewidth = 0.3),
      legend.box.margin = margin(3, 5, 3, 5),
      plot.margin = margin(12, 12, 12, 12)
    )

  if (!show_grid) {
    base <- base + theme(panel.grid = element_blank())
  }

  if (transparent_bg) {
    base <- base + theme(
      plot.background = element_rect(fill = NA, color = NA),
      panel.background = element_rect(fill = NA, color = NA),
      plot.margin = margin(6, 6, 6, 6)
    )
  }

  base
}

map_crs <- function() {
  sf::st_crs(32737)
}

boundary_layer <- function(boundary, linewidth = 0.45) {
  geom_sf(
    data = boundary,
    fill = NA,
    color = "black",
    linewidth = linewidth,
    inherit.aes = FALSE
  )
}

map_elements <- function() {
  list(
    annotation_scale(
      location = "bl",
      width_hint = 0.22,
      style = "ticks",
      line_width = 0.5,
      text_cex = 0.85,
      pad_x = unit(0.25, "cm"),
      pad_y = unit(0.25, "cm")
    ),
    annotation_north_arrow(
      location = "tr",
      which_north = "true",
      style = north_arrow_fancy_orienteering(
        fill = c("grey20", "white"),
        line_col = "grey20"
      ),
      height = unit(1.15, "cm"),
      width = unit(1.15, "cm"),
      pad_x = unit(0.3, "cm"),
      pad_y = unit(0.3, "cm")
    )
  )
}

trim_map_png <- function(path) {
  if (!requireNamespace("magick", quietly = TRUE)) {
    return(invisible(path))
  }
  img <- magick::image_read(path)
  img <- magick::image_trim(img)
  magick::image_write(img, path, format = "png")
  invisible(path)
}

save_map <- function(
  plot,
  path,
  width = NULL,
  height = NULL,
  dpi = 300,
  bg = "white",
  limits = NULL,
  base_size = 10,
  trim = identical(bg, "transparent")
) {
  if (!is.null(limits)) {
    dims <- map_figure_dims(limits, base_size = base_size)
    width <- dims$width
    height <- dims$height
  }
  width <- if (is.null(width)) base_size else width
  height <- if (is.null(height)) base_size else height
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggsave(filename = path, plot = plot, width = width, height = height, dpi = dpi, bg = bg)
  if (trim && grepl("\\.[Pp][Nn][Gg]$", path, perl = TRUE)) {
    trim_map_png(path)
  }
  message("  ", basename(path), sprintf(" (%.1f x %.1f in)", width, height))
}

make_base_map <- function(boundary, title, subtitle = NULL, caption = NULL, transparent_bg = FALSE, show_grid = FALSE) {
  ggplot() +
    boundary_layer(boundary) +
    coord_map_limits(boundary) +
    labs(
      title = title,
      subtitle = subtitle,
      caption = caption,
      x = "Longitude",
      y = "Latitude"
    ) +
    map_theme(transparent_bg = transparent_bg, show_grid = show_grid) +
    map_elements()
}

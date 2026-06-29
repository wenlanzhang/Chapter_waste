# Shared ggplot2 map styling for Chapter_waste figures.

library(ggplot2)
library(ggspatial)

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg)) {
    return(dirname(normalizePath(sub("^--file=", "", file_arg))))
  }
  "."
}

map_theme <- function() {
  theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      panel.grid.major = element_line(color = "grey90", linewidth = 0.25),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "grey70", fill = NA, linewidth = 0.4),
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, margin = margin(b = 6)),
      plot.subtitle = element_text(size = 10, hjust = 0.5, color = "grey35", margin = margin(b = 8)),
      plot.caption = element_text(size = 8, color = "grey45", hjust = 1),
      axis.text = element_text(size = 8, color = "grey25"),
      axis.title = element_text(size = 10),
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

save_map <- function(plot, path, width = 10, height = 10, dpi = 300) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggsave(filename = path, plot = plot, width = width, height = height, dpi = dpi, bg = "white")
  message("  ", basename(path))
}

make_base_map <- function(boundary, title, subtitle = NULL, caption = NULL) {
  ggplot() +
    boundary_layer(boundary) +
    coord_sf(crs = map_crs(), datum = NA, expand = FALSE) +
    labs(
      title = title,
      subtitle = subtitle,
      caption = caption,
      x = "Easting (m)",
      y = "Northing (m)"
    ) +
    map_theme() +
    map_elements()
}

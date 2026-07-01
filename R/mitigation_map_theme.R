# Shared styling for 4_compare and 5_cluster figures

suppressPackageStartupMessages({
  library(ggplot2)
  library(ggspatial)
  library(sf)
})

MITIGATION_AXIS_COLOUR <- "#4D2D18"

make_source_legend <- function(n_all_svi, n_gsvi, n_self) {
  labels <- c(
    paste0("All SVI (", format(n_all_svi, big.mark = ",", trim = TRUE), ")"),
    paste0("GSVI waste (", format(n_gsvi, big.mark = ",", trim = TRUE), ")"),
    paste0(
      "Self-collected SVI waste (",
      format(n_self, big.mark = ",", trim = TRUE),
      ")"
    ),
    "City Boundary",
    "Urban Poor Settlements"
  )

  list(labels = labels, labels_only = labels)
}

make_source_legend_colours <- function(
  labels,
  all_svi_colour,
  gsvi_colour,
  self_collected_colour,
  slum_fill
) {
  setNames(
    c(all_svi_colour, gsvi_colour, self_collected_colour, "black", slum_fill),
    labels
  )
}

make_source_legend_df <- function(labels) {
  data.frame(
    legend_type = factor(labels, levels = labels),
    lon = NA_real_,
    lat = NA_real_
  )
}

source_legend_guide <- function(
  labels,
  all_svi_colour,
  gsvi_colour,
  self_collected_colour,
  slum_fill,
  slum_edge,
  slum_alpha
) {
  guide_legend(
    override.aes = list(
      shape = c(16, 16, 16, 22, 22),
      size = c(2.2, 3.0, 3.0, 2.4, 3.0),
      fill = c(NA, NA, NA, NA, alpha(slum_fill, slum_alpha)),
      colour = c(
        all_svi_colour,
        gsvi_colour,
        self_collected_colour,
        "black",
        slum_edge
      ),
      stroke = c(0.5, 0.5, 0.5, 1.1, 0.6),
      alpha = c(0.55, 1, 1, 1, 1)
    ),
    keywidth = unit(1.0, "lines"),
    keyheight = unit(1.0, "lines"),
    ncol = 1
  )
}

mitigation_coord <- function(crs, boundary = NULL, pad_frac = 0.03) {
  args <- list(crs = crs, datum = NA, expand = FALSE)
  if (!is.null(boundary)) {
    bb <- st_bbox(boundary)
    lon_span <- as.numeric(bb["xmax"] - bb["xmin"])
    lat_span <- as.numeric(bb["ymax"] - bb["ymin"])
    pad_lon <- lon_span * pad_frac
    pad_lat <- lat_span * pad_frac
    args$xlim <- c(bb["xmin"] - pad_lon, bb["xmax"] + pad_lon)
    args$ylim <- c(bb["ymin"] - pad_lat, bb["ymax"] + pad_lat)
  }
  do.call(coord_sf, args)
}

mitigation_fig_size <- function(boundary, width = 10, title_pad = 0.45) {
  bb <- st_bbox(boundary)
  mid_lat <- mean(c(bb["ymin"], bb["ymax"])) * pi / 180
  lon_span <- as.numeric(bb["xmax"] - bb["xmin"])
  lat_span <- as.numeric(bb["ymax"] - bb["ymin"])
  panel_ratio <- lat_span / (lon_span * cos(mid_lat))
  height <- width * panel_ratio + title_pad
  list(width = width, height = height)
}

save_mitigation_map <- function(
  plot,
  path,
  boundary,
  width = 10,
  dpi = 600,
  bg = "white"
) {
  size <- mitigation_fig_size(boundary, width = width)
  ggsave(
    path,
    plot = plot,
    width = size$width,
    height = size$height,
    dpi = dpi,
    bg = bg
  )
}

mitigation_map_decorations <- function(p) {
  p +
    annotation_scale(
      location = "bl",
      width_hint = 0.18,
      style = "ticks",
      line_width = 0.45,
      text_cex = 0.8,
      pad_x = unit(0.2, "cm"),
      pad_y = unit(0.35, "cm")
    ) +
    annotation_north_arrow(
      location = "tr",
      which_north = "true",
      style = north_arrow_fancy_orienteering(
        fill = c("grey20", "white"),
        line_col = "grey20"
      ),
      height = unit(0.9, "cm"),
      width = unit(0.9, "cm"),
      pad_x = unit(0.2, "cm"),
      pad_y = unit(0.2, "cm")
    )
}

mitigation_map_theme <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "sans") +
    theme(
      panel.grid = element_blank(),
      panel.background = element_rect(fill = "#fafafa", colour = NA),
      panel.border = element_rect(colour = "grey55", fill = NA, linewidth = 0.45),
      plot.background = element_rect(fill = "white", colour = NA),
      plot.title = element_text(
        face = "bold",
        size = base_size + 2,
        hjust = 0.5,
        colour = "#2f2f2f",
        margin = margin(t = 0, b = 2)
      ),
      plot.subtitle = element_blank(),
      axis.title.x = element_text(
        colour = MITIGATION_AXIS_COLOUR,
        size = base_size - 1,
        face = "italic",
        hjust = 0.5,
        vjust = 1,
        margin = margin(t = -20, b = 0)
      ),
      axis.title.y = element_text(
        colour = MITIGATION_AXIS_COLOUR,
        size = base_size - 1,
        face = "italic",
        angle = 90,
        hjust = 0.5,
        vjust = 0.62,
        margin = margin(r = -20, l = 0)
      ),
      axis.text = element_text(
        colour = MITIGATION_AXIS_COLOUR,
        size = base_size - 2.5
      ),
      axis.line = element_line(colour = "grey55", linewidth = 0.35),
      legend.position = "inside",
      legend.position.inside = c(0.985, 0.015),
      legend.justification = c(1, 0),
      legend.background = element_rect(
        fill = alpha("white", 0.94),
        colour = "grey78",
        linewidth = 0.35
      ),
      legend.key = element_rect(fill = NA, colour = NA),
      legend.text = element_text(size = base_size - 1.6, colour = "#2f2f2f"),
      legend.spacing.y = unit(0.12, "lines"),
      legend.box.margin = margin(3, 5, 3, 5),
      plot.margin = margin(t = 2, r = 2.5, b = 2, l = 4, unit = "mm")
    )
}

hdbscan_legend_labels <- function(n_clustered_points, n_noise) {
  c(
    paste0(
      "Clustered waste points (",
      format(n_clustered_points, big.mark = ",", trim = TRUE),
      ")"
    ),
    paste0(
      "Noise waste points (",
      format(n_noise, big.mark = ",", trim = TRUE),
      ")"
    ),
    "City Boundary"
  )
}

hdbscan_map_theme <- function(base_size = 11) {
  mitigation_map_theme(base_size)
}

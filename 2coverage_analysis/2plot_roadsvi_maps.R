#!/usr/bin/env Rscript
# Road → SVI maps: uncovered road metres + H3 coverage choropleth + hist/scatter

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
  library(hrbrthemes)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737
MAIN_SVI_BUFFER_M <- 50L
FILL_COLOUR <- "#8B5A3C"

parse_args <- function() {
  defaults <- list(svi_buffer = 50, h3_res = 8L)
  args <- commandArgs(trailingOnly = TRUE)
  for (arg in args) {
    if (grepl("^--svi-buffer-m=", arg)) defaults$svi_buffer <- as.numeric(sub("^--svi-buffer-m=", "", arg))
    if (grepl("^--h3-res=", arg)) defaults$h3_res <- as.integer(sub("^--h3-res=", "", arg))
  }
  defaults
}

file_tag <- function(svi_buffer) {
  sprintf("buf%dm", as.integer(svi_buffer))
}

h3_file_tag <- function(h3_res, svi_buffer) {
  sprintf("h3_res%d_buf%dm", h3_res, as.integer(svi_buffer))
}

# Main result stays in FIG_DIR; sensitivity buffers go under buffer/
fig_out_dir <- function(svi_buffer) {
  if (as.integer(svi_buffer) == MAIN_SVI_BUFFER_M) {
    FIG_DIR
  } else {
    file.path(FIG_DIR, "buffer")
  }
}

panel_theme <- function() {
  theme_ipsum(base_size = 11) +
    theme(
      plot.background = element_rect(fill = NA, color = NA),
      panel.background = element_rect(fill = NA, color = NA),
      plot.title = element_text(face = "bold", size = 12.5, hjust = 0, color = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.5, hjust = 0, color = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      plot.tag = element_text(size = 12, face = "bold", color = CHAPTER_TITLE_COLOUR),
      plot.tag.position = c(0.02, 0.98),
      axis.title = element_text(size = 10, color = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 9, color = CHAPTER_SUBTITLE_COLOUR),
      plot.margin = margin(10, 14, 8, 12)
    )
}

format_stat <- function(x, digits = 2) {
  if (abs(x - round(x)) < 1e-9) {
    return(as.character(as.integer(round(x))))
  }
  format(round(x, digits), nsmall = digits, trim = TRUE)
}

args <- parse_args()
tag <- file_tag(args$svi_buffer)
h3_tag <- h3_file_tag(args$h3_res, args$svi_buffer)
out_dir <- fig_out_dir(args$svi_buffer)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

coverage <- st_read(
  file.path(DATA_DIR, paste0("Nairobi_roadsvi_coverage_", tag, ".gpkg")),
  quiet = TRUE
) |> st_transform(CRS_EA)

summary <- read.csv(file.path(DATA_DIR, paste0("Nairobi_roadsvi_summary_", tag, ".csv")))
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |> st_transform(CRS_EA)

uncovered <- coverage |> filter(.data$coverage_status == "uncovered")

subtitle <- sprintf(
  "%.1f km uncovered (%.1f%%) | %s coverage parts | SVI buffer %dm",
  summary$uncovered_road_length_km,
  summary$pct_road_length_not_covered,
  comma(summary$coverage_part_count),
  as.integer(args$svi_buffer)
)

p_uncovered <- ggplot() +
  geom_sf(data = coverage, aes(color = "All roads"), linewidth = 0.10, alpha = 0.95) +
  geom_sf(data = uncovered, aes(color = "Not covered by SVI"), linewidth = 0.28, alpha = 0.95) +
  geom_sf(data = boundary, fill = NA, color = "black", linewidth = 0.45) +
  scale_color_manual(
    name = NULL,
    values = c(
      "All roads" = ROAD_BASELINE_COLOUR,
      "Not covered by SVI" = HIGHLIGHT_NEGATIVE_COLOUR
    )
  ) +
  guides(color = guide_legend(override.aes = list(linewidth = c(1.0, 1.6), alpha = 1))) +
  coord_map_limits(boundary) +
  labs(
    title = "Road metres not covered by SVI",
    subtitle = subtitle,
    caption = paste0(
      "SVI coverage = road metres outside ", as.integer(args$svi_buffer),
      " m panoid buffer union (partial gaps shown)"
    ),
    x = "Longitude",
    y = "Latitude"
  ) +
  map_theme(transparent_bg = TRUE) +
  map_elements()

message("Writing figures to ", out_dir)

report_path <- file.path(out_dir, paste0("Nairobi_roadsvi_uncovered_", tag, ".png"))
hires_path <- file.path(out_dir, paste0("Nairobi_roadsvi_uncovered_", tag, "_hires.png"))

save_map(p_uncovered, report_path, limits = boundary, base_size = 10, dpi = 300, bg = "transparent")
save_map(p_uncovered, hires_path, limits = boundary, base_size = 20, dpi = 600, bg = "transparent")

# --- H3 coverage-ratio choropleth + distribution panels ---
h3_gpkg <- file.path(DATA_DIR, paste0("Nairobi_roadsvi_grid_", h3_tag, ".gpkg"))
h3_csv <- file.path(DATA_DIR, paste0("Nairobi_roadsvi_grid_", h3_tag, ".csv"))
if (!file.exists(h3_gpkg)) {
  message("H3 grid not found (", basename(h3_gpkg), "); skip H3 map/analysis. Run 2roadsvi.py first.")
} else {
  grid <- st_read(h3_gpkg, quiet = TRUE) |> st_transform(CRS_EA)
  grid_road <- grid |> filter(.data$has_road == 1)

  mean_ratio <- if ("mean_h3_svi_coverage_ratio" %in% names(summary)) {
    summary$mean_h3_svi_coverage_ratio
  } else {
    mean(grid_road$svi_coverage_ratio, na.rm = TRUE)
  }
  median_ratio <- median(grid_road$svi_coverage_ratio, na.rm = TRUE)

  h3_subtitle <- sprintf(
    "H3 res %d | SVI buffer %dm | mean coverage %.1f%% (cells with road)",
    args$h3_res,
    as.integer(args$svi_buffer),
    100 * mean_ratio
  )

  p_h3 <- make_base_map(
    boundary,
    title = "H3 road-length SVI coverage ratio",
    subtitle = h3_subtitle,
    caption = paste0(
      "Ratio = covered road metres / total road metres in cell | ",
      as.integer(args$svi_buffer), " m SVI buffer"
    ),
    transparent_bg = TRUE
  ) +
    geom_sf(data = grid_road, aes(fill = .data$svi_coverage_ratio), color = NA) +
    scale_fill_chapter_c(
      name = "SVI coverage",
      labels = label_percent(accuracy = 1),
      limits = c(0, 1)
    )

  h3_path <- file.path(out_dir, paste0("Nairobi_roadsvi_coverage_", h3_tag, ".png"))
  save_map(p_h3, h3_path, limits = boundary, base_size = 10, bg = "transparent")
  message("  ", basename(h3_path))

  # Histogram + scatter (cells with road)
  grid_df <- if (file.exists(h3_csv)) {
    read.csv(h3_csv, stringsAsFactors = FALSE) |> filter(.data$has_road == 1)
  } else {
    grid_road |> st_drop_geometry()
  }
  grid_df <- grid_df |>
    filter(is.finite(.data$svi_coverage_ratio), is.finite(.data$road_length_m)) |>
    mutate(road_length_km = .data$road_length_m / 1000)

  n_cells <- nrow(grid_df)
  stats_caption <- sprintf(
    "n = %s  |  median = %s  |  mean = %s",
    comma(n_cells),
    format_stat(median_ratio),
    format_stat(mean_ratio)
  )

  p_hist <- ggplot(grid_df, aes(x = .data$svi_coverage_ratio)) +
    geom_histogram(
      bins = 28,
      fill = FILL_COLOUR,
      color = "#e9ecef",
      alpha = 0.65,
      position = "identity"
    ) +
    geom_vline(xintercept = median_ratio, color = MEDIAN_COLOUR, linewidth = 0.85, linetype = "solid") +
    geom_vline(xintercept = mean_ratio, color = MEAN_COLOUR, linewidth = 0.65, linetype = "22") +
    scale_x_continuous(
      labels = label_percent(accuracy = 1),
      breaks = seq(0, 1, by = 0.25),
      expand = expansion(mult = c(0.01, 0.04))
    ) +
    scale_y_continuous(labels = comma, expand = expansion(mult = c(0, 0.08))) +
    labs(
      title = "Coverage ratio distribution",
      subtitle = stats_caption,
      tag = "A",
      x = "SVI coverage ratio",
      y = "H3 cells"
    ) +
    panel_theme()

  # Spearman for caption
  rho <- suppressWarnings(cor(grid_df$road_length_km, grid_df$svi_coverage_ratio, method = "spearman"))
  p_scatter <- ggplot(grid_df, aes(x = .data$road_length_km, y = .data$svi_coverage_ratio)) +
    geom_point(alpha = 0.35, size = 1.6, color = FILL_COLOUR) +
    geom_smooth(
      method = "loess",
      formula = y ~ x,
      se = TRUE,
      linewidth = 0.7,
      color = MEAN_POINT_COLOUR,
      fill = alpha(MEAN_COLOUR, 0.25)
    ) +
    scale_x_continuous(labels = label_number(accuracy = 0.1), expand = expansion(mult = c(0.02, 0.06))) +
    scale_y_continuous(
      labels = label_percent(accuracy = 1),
      breaks = seq(0, 1, by = 0.25),
      expand = expansion(mult = c(0.02, 0.04))
    ) +
    labs(
      title = "Road length vs coverage",
      subtitle = sprintf("Spearman \u03C1 = %s  |  cells with road", format_stat(rho, digits = 2)),
      tag = "B",
      x = "Road length in cell (km)",
      y = "SVI coverage ratio"
    ) +
    panel_theme()

  analysis <- (p_hist + p_scatter) +
    plot_annotation(
      title = "H3 road-length SVI coverage",
      subtitle = sprintf(
        "Nairobi | H3 res %d | SVI buffer %dm | %s cells with road",
        args$h3_res,
        as.integer(args$svi_buffer),
        comma(n_cells)
      ),
      caption = "A: histogram of coverage ratio  |  B: road length vs coverage (loess)  |  Dark solid = median  |  Tan dashed = mean"
    )

  analysis_path <- file.path(out_dir, paste0("Nairobi_roadsvi_analysis_", h3_tag, ".png"))
  ggsave(
    filename = analysis_path,
    plot = analysis,
    width = 11,
    height = 5.2,
    dpi = 320,
    bg = "transparent"
  )
  message("  ", basename(analysis_path))
}

message("Done.")

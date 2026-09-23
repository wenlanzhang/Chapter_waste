#!/usr/bin/env Rscript
# Road → SVI figures:
#   2_Nairobi_roadsvi_uncovered_buf50m.png       road metres not covered by SVI buffers (+ _hires)
#   2_Nairobi_roadsvi_analysis_grid100m_buf50m.png   per-cell coverage ratio: distribution + road length vs ratio

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
source(file.path(script_dir, "..", "R", "chapter_arms.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

ARM <- parse_arm_arg()

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
INPUT_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
CRS_EA <- 32737
FILL_COLOUR <- "#8B5A3C"

parse_args <- function() {
  defaults <- list(svi_buffer = 50)
  args <- commandArgs(trailingOnly = TRUE)
  for (arg in args) {
    if (grepl("^--svi-buffer-m=", arg)) defaults$svi_buffer <- as.numeric(sub("^--svi-buffer-m=", "", arg))
  }
  defaults
}

file_tag <- function(svi_buffer) {
  sprintf("buf%dm", as.integer(svi_buffer))
}

args <- parse_args()
tag <- file_tag(args$svi_buffer)
# Data files carry the arm key; figure names keep legacy (gsvi) names
data_tag <- arm_tagged(tag, ARM)
fig_sfx <- arm_fig_suffix(ARM)
# Subtitle prefix identifies the arm on non-GSVI figures (GSVI figures keep legacy text)
arm_prefix <- if (ARM == "gsvi") "" else paste0(arm_label(ARM), " | ")
out_dir <- FIG_DIR
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

coverage <- st_read(
  file.path(DATA_DIR, paste0("2_Nairobi_roadsvi_coverage_", data_tag, ".gpkg")),
  quiet = TRUE
) |> st_transform(CRS_EA)

summary <- read.csv(file.path(DATA_DIR, paste0("2_Nairobi_roadsvi_summary_", data_tag, ".csv")))
boundary <- st_read(
  file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"),
  quiet = TRUE
) |> st_transform(CRS_EA)

uncovered <- coverage |> filter(.data$coverage_status == "uncovered")

subtitle <- sprintf(
  "%s%.1f km uncovered (%.1f%%) | %s coverage parts | SVI buffer %dm",
  arm_prefix,
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

report_path <- file.path(out_dir, paste0("2_Nairobi_roadsvi_uncovered_", tag, fig_sfx, ".png"))
hires_path <- file.path(out_dir, paste0("2_Nairobi_roadsvi_uncovered_", tag, fig_sfx, "_hires.png"))

save_map(p_uncovered, report_path, limits = boundary, base_size = 10, dpi = 300, bg = "transparent")
save_map(p_uncovered, hires_path, limits = boundary, base_size = 20, dpi = 600, bg = "transparent")

# --- Per-cell coverage ratio on the 100 m grid (2roadsvi.py grid output) ---
cells <- st_read(file.path(DATA_DIR, paste0("2_Nairobi_roadsvi_grid100m_", data_tag, ".gpkg")), quiet = TRUE) |>
  st_drop_geometry()
with_road <- cells |> filter(road_m_total > 0, !is.na(svi_road_coverage_ratio))
n_cells <- nrow(with_road)
FILL_COLOUR <- GSVI_COLOUR
MEDIAN_COLOUR <- WASTE_DARK_COLOUR
MEAN_COLOUR <- WASTE_COLOUR
OBS_NAME <- if (ARM == "gsvi") "GSVI" else "SVI"

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

median_ratio <- median(with_road$svi_road_coverage_ratio)
mean_ratio <- mean(with_road$svi_road_coverage_ratio)
p_hist <- ggplot(with_road, aes(x = svi_road_coverage_ratio)) +
  geom_histogram(bins = 40, fill = FILL_COLOUR, color = "white", linewidth = 0.2) +
  geom_vline(xintercept = median_ratio, color = MEDIAN_COLOUR, linewidth = 0.9) +
  geom_vline(xintercept = mean_ratio, color = MEAN_COLOUR, linewidth = 0.9, linetype = "dashed") +
  scale_x_continuous(labels = label_percent(accuracy = 1)) +
  scale_y_continuous(labels = comma) +
  labs(
    tag = "A",
    title = "Coverage ratio distribution",
    subtitle = sprintf("n = %s  |  median = %.2f  |  mean = %.2f  |  fully covered %.1f%%, uncovered %.1f%%",
                       comma(n_cells), median_ratio, mean_ratio,
                       summary$pct_cells_with_road_fully_covered, summary$pct_cells_with_road_uncovered),
    x = sprintf("%s coverage ratio (covered road m / road m in cell)", OBS_NAME),
    y = "100 m cells"
  ) +
  panel_theme()

rho_len <- suppressWarnings(cor(with_road$road_m_total, with_road$svi_road_coverage_ratio, method = "spearman"))
len_cap <- quantile(with_road$road_m_total, 0.995)
p_scatter <- ggplot(with_road |> filter(road_m_total <= len_cap), aes(x = road_m_total, y = svi_road_coverage_ratio)) +
  geom_bin2d(bins = 45) +
  scale_fill_gradientn(name = "Cells", colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR), trans = "log10", labels = comma) +
  geom_smooth(method = "gam", formula = y ~ s(x, bs = "cs"), color = MEDIAN_COLOUR, fill = alpha(MEDIAN_COLOUR, 0.25), linewidth = 0.9) +
  scale_x_continuous(labels = comma) +
  scale_y_continuous(labels = label_percent(accuracy = 1)) +
  labs(
    tag = "B",
    title = "Road length vs coverage",
    subtitle = sprintf("Spearman \u03C1 = %.2f  |  cells with road  (x capped at 99.5th pct)", rho_len),
    x = "Mapped road length in cell (m)",
    y = sprintf("%s coverage ratio", OBS_NAME)
  ) +
  panel_theme() +
  theme(legend.position = "right", legend.key.height = unit(0.7, "cm"),
        legend.title = element_text(size = 9, color = CHAPTER_AXIS_COLOUR),
        legend.text = element_text(size = 8, color = CHAPTER_SUBTITLE_COLOUR))

analysis <- (p_hist + p_scatter) +
  plot_annotation(
    title = sprintf("Road-length %s coverage on the 100 m grid", OBS_NAME),
    subtitle = sprintf("Nairobi | %s buffer %d m | %s cells with mapped road", OBS_NAME, as.integer(args$svi_buffer), comma(n_cells)),
    caption = "Solid = median | Dashed = mean | B: cell counts per bin (log scale), GAM smooth with 95% band",
    theme = theme(
      plot.title = element_text(size = 14, color = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 10, color = CHAPTER_SUBTITLE_COLOUR),
      plot.caption = element_text(size = 8, color = CHAPTER_SUBTITLE_COLOUR),
      plot.background = element_rect(fill = NA, color = NA)
    )
  )
save_map(analysis, file.path(out_dir, paste0("2_Nairobi_roadsvi_analysis_grid100m_", tag, fig_sfx, ".png")),
         width = 12, height = 5.5, dpi = 300, bg = "transparent")

message("Done.")

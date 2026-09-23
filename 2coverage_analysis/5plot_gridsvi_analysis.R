#!/usr/bin/env Rscript
# Cell-level correlation figures on the 100 m grid (from 5_gridsvi.py's cell table):
#   5_Nairobi_gridsvi_correlation_spearman_grid100m.png          Spearman matrix over
#       road density, road segments, GSVI panoramas, SVI road-coverage ratio
#   5_Nairobi_gridsvi_correlation_spearman_grid100m_scatter.png  binned pairwise panels
# Both use cells with mapped road (road_length_m > 0).

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
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

ARM <- parse_arm_arg()
OBS_NAME <- if (ARM == "gsvi") "GSVI" else "SVI"

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")
sfx <- arm_fig_suffix(ARM)

CORR_COLUMNS <- c(
  "road_density_km_per_km2",
  "n_road_segments",
  "n_panoramas",
  "svi_road_coverage_ratio"
)
CORR_LABELS <- c(
  road_density_km_per_km2 = "Road density",
  n_road_segments = "Road segments",
  n_panoramas = sprintf("%s panoramas", OBS_NAME),
  svi_road_coverage_ratio = "Road coverage ratio"
)

grid <- st_read(file.path(DATA_DIR, arm_filename("5_Nairobi_gridsvi_grid100m", ARM)), quiet = TRUE) |>
  st_drop_geometry()
with_road <- grid |> filter(road_length_m > 0, !is.na(svi_road_coverage_ratio))
n_cells <- nrow(with_road)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
message("Writing figures to ", FIG_DIR)

# ---------------------------------------------------------------------------
# (2) Spearman correlation heatmap
# ---------------------------------------------------------------------------
corr_mat <- cor(with_road[, CORR_COLUMNS, drop = FALSE], method = "spearman", use = "pairwise.complete.obs")
write.csv(corr_mat, file.path(DATA_DIR, arm_filename("5_Nairobi_gridsvi_correlation_spearman", ARM, suffix = "", ext = "csv")), row.names = TRUE)

n <- length(CORR_COLUMNS)
labels <- CORR_LABELS[CORR_COLUMNS]
rho_range <- range(corr_mat[lower.tri(corr_mat)], na.rm = TRUE)
fill_low <- min(0, floor(rho_range[1] * 20) / 20 - 0.02)
fill_high <- 1

corr_long <- data.frame(
  row_idx = rep(seq_len(n), each = n),
  col_idx = rep(seq_len(n), times = n),
  rho = as.vector(corr_mat)
) |>
  mutate(
    var_row = factor(row_idx, levels = seq_len(n), labels = labels),
    var_col = factor(col_idx, levels = seq_len(n), labels = labels),
    cell_type = case_when(row_idx < col_idx ~ "upper", row_idx == col_idx ~ "diag", TRUE ~ "lower"),
    fill_rho = if_else(cell_type == "lower", rho, NA_real_),
    label = case_when(
      cell_type == "lower" ~ sprintf("%.2f", rho),
      cell_type == "diag" ~ labels[row_idx],
      TRUE ~ ""
    ),
    text_color = chocolate_label_colour(fill_rho, limits = c(fill_low, fill_high))
  )

p_heat <- ggplot(corr_long) +
  geom_tile(aes(x = var_col, y = var_row), fill = CHOCOLATE_EMPTY, color = "white", linewidth = 1.0) +
  geom_tile(aes(x = var_col, y = var_row, fill = fill_rho), color = "white", linewidth = 1.0) +
  geom_text(data = corr_long |> filter(cell_type == "lower"),
            aes(x = var_col, y = var_row, label = label, color = text_color), size = 3.6, fontface = "bold") +
  geom_text(data = corr_long |> filter(cell_type == "diag"),
            aes(x = var_col, y = var_row, label = label), size = 3.1, color = CHAPTER_AXIS_COLOUR) +
  scale_fill_gradientn(
    colours = CHOCOLATE_PALETTE, limits = c(fill_low, fill_high), na.value = NA,
    name = expression(Spearman ~ rho), breaks = pretty(c(fill_low, fill_high), n = 4),
    labels = label_number(accuracy = 0.01),
    guide = guide_colorbar(barwidth = unit(0.55, "cm"), barheight = unit(3.2, "cm"),
                           frame.colour = "grey78", frame.linewidth = 0.35, title.position = "top", title.hjust = 0.5)
  ) +
  scale_color_identity() +
  scale_x_discrete(position = "top", expand = expansion(add = 0.6)) +
  scale_y_discrete(limits = rev(labels), expand = expansion(add = 0.6)) +
  coord_fixed(ratio = 1) +
  labs(
    title = "Spearman correlation matrix (100 m cell metrics)",
    subtitle = sprintf("Nairobi | n = %s cells with mapped road | lower triangle", comma(n_cells)),
    x = NULL, y = NULL,
    caption = sprintf("Diagonal = variable labels | Colour range scaled to observed ρ (%.2f–1.00)", fill_low)
  ) +
  theme_minimal(base_size = 11, base_family = "sans") +
  theme(
    plot.background = element_rect(fill = NA, color = NA),
    panel.background = element_rect(fill = NA, color = NA),
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 15, hjust = 0.5, color = CHAPTER_TITLE_COLOUR, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 10, hjust = 0.5, color = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 12)),
    plot.caption = element_text(size = 8.5, hjust = 0.5, color = CHAPTER_CAPTION_COLOUR, margin = margin(t = 10)),
    axis.text.x = element_text(angle = 30, hjust = 0, vjust = 0, color = CHAPTER_AXIS_COLOUR, size = 10, face = "bold", margin = margin(b = 4)),
    axis.text.y = element_text(color = CHAPTER_AXIS_COLOUR, size = 10, face = "bold", margin = margin(r = 4)),
    axis.ticks = element_blank(),
    legend.position = "right",
    legend.title = element_text(face = "bold", size = 9.5, color = CHAPTER_AXIS_COLOUR),
    legend.text = element_text(size = 8.5, color = CHAPTER_SUBTITLE_COLOUR),
    plot.margin = margin(16, 18, 14, 14)
  )
heat_path <- file.path(FIG_DIR, paste0("5_Nairobi_gridsvi_correlation_spearman_grid100m", sfx, ".png"))
ggsave(heat_path, plot = p_heat, width = 8.2, height = 7.4, dpi = 320, bg = "transparent")
message("  ", basename(heat_path))

# ---------------------------------------------------------------------------
# (3) Pairwise scatter matrix (upper triangle: 3-2-1 layout)
# ---------------------------------------------------------------------------
pair_theme <- function(show_x = TRUE, show_y = TRUE) {
  theme_minimal(base_size = 10, base_family = "sans") +
    theme(
      plot.background = element_rect(fill = NA, color = NA),
      panel.background = element_rect(fill = NA, color = NA),
      panel.grid.major = element_line(color = "#E6EAF0", linewidth = 0.3),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(color = "#D5DCE6", fill = NA, linewidth = 0.35),
      axis.title = element_text(size = 9, color = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8, color = CHAPTER_SUBTITLE_COLOUR),
      plot.margin = margin(4, 4, 4, 4),
      axis.title.x = if (show_x) element_text(margin = margin(t = 6)) else element_blank(),
      axis.title.y = if (show_y) element_text(margin = margin(r = 6)) else element_blank(),
      axis.text.x = if (show_x) element_text() else element_blank(),
      axis.text.y = if (show_y) element_text() else element_blank()
    )
}

# Cap heavy-tailed axes at the 99.5th percentile so the bulk of cells is readable.
# Counts (segments, panoramas) are integers, so binned densities read better than points.
cap <- function(x) pmin(x, quantile(x, 0.995, na.rm = TRUE))
n_bins_for <- function(x) if (all(x == round(x), na.rm = TRUE)) max(5L, min(30L, length(unique(x)))) else 40L
make_scatter <- function(x_col, y_col, rho, show_x = TRUE, show_y = TRUE) {
  df <- data.frame(x = cap(with_road[[x_col]]), y = cap(with_road[[y_col]]))
  ggplot(df, aes(x = x, y = y)) +
    geom_bin2d(bins = c(n_bins_for(df$x), n_bins_for(df$y)), show.legend = FALSE) +
    scale_fill_gradientn(colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR), trans = "log10") +
    annotate("label", x = -Inf, y = Inf, label = sprintf("ρ = %.2f", rho), hjust = -0.08, vjust = 1.15,
             size = 3.2, fontface = "bold", fill = alpha("white", 0.92), linewidth = 0.2, color = CHAPTER_TITLE_COLOUR) +
    scale_x_continuous(labels = label_number(accuracy = 0.1)) +
    scale_y_continuous(labels = label_number(accuracy = 0.1)) +
    labs(x = if (show_x) CORR_LABELS[[x_col]] else NULL, y = if (show_y) CORR_LABELS[[y_col]] else NULL) +
    pair_theme(show_x = show_x, show_y = show_y)
}

p12 <- make_scatter(CORR_COLUMNS[2], CORR_COLUMNS[1], corr_mat[1, 2], show_x = FALSE, show_y = TRUE)
p13 <- make_scatter(CORR_COLUMNS[3], CORR_COLUMNS[1], corr_mat[1, 3], show_x = FALSE, show_y = FALSE)
p14 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[1], corr_mat[1, 4], show_x = FALSE, show_y = FALSE)
p23 <- make_scatter(CORR_COLUMNS[3], CORR_COLUMNS[2], corr_mat[2, 3], show_x = FALSE, show_y = TRUE)
p24 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[2], corr_mat[2, 4], show_x = FALSE, show_y = FALSE)
p34 <- make_scatter(CORR_COLUMNS[4], CORR_COLUMNS[3], corr_mat[3, 4], show_x = TRUE, show_y = TRUE)

p_pairs <- wrap_plots(p12, p13, p14, p23, p24, p34, design = "
ABC
#DE
##F
") +
  plot_annotation(
    title = "Spearman correlation scatter matrix (100 m cell metrics)",
    subtitle = sprintf("Nairobi | n = %s cells with mapped road | axes capped at 99.5th pct | each panel = binned cell counts (log scale) with Spearman ρ", comma(n_cells)),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, color = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, color = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8))
    )
  )
pairs_path <- file.path(FIG_DIR, paste0("5_Nairobi_gridsvi_correlation_spearman_grid100m", sfx, "_scatter.png"))
ggsave(pairs_path, plot = p_pairs, width = 10, height = 9.5, dpi = 320, bg = "transparent")
message("  ", basename(pairs_path))

message("Done.")

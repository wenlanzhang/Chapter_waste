#!/usr/bin/env Rscript
# Stratified context maps for 100 m grid waste/SVI ratio (gsvi vs g+self)

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(patchwork)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "mitigation_map_theme.R"))

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
GRID_DIR <- file.path(DATA_ROOT, "3_100m")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")
THESIS_DIR <- file.path(GRID_DIR, "thesis_table")

WGS84 <- 4326
CONTEXT_GPKG <- file.path(GRID_DIR, "Nairobi_grid_waste_ratio_context_32737.gpkg")
STRATIFIED_CSV <- file.path(
  THESIS_DIR, "Nairobi_grid_waste_ratio_context_stratified.csv"
)

RESULT_PALETTE <- c(
  "0" = "#f0ede8",
  "1" = "#E5C8A9",
  "2" = "#C9A27F",
  "3" = "#6B4226"
)

RESULT_LABELS <- c(
  "0" = "No SVI data",
  "1" = "Low (0–2.4%)",
  "2" = "Medium (2.5–16.4%)",
  "3" = "High (>16.4%)"
)

IMPROVEMENT_FILL <- "#7B68EE"
IMPROVEMENT_EDGE <- "#4B0082"
SVI_OUTLINE <- "#2E86AB"

read_wgs84 <- function(path) {
  st_read(path, quiet = TRUE) |> st_transform(WGS84)
}

build_result_map <- function(
  grid,
  boundary,
  result_col,
  panel_title,
  subtitle_text,
  base_size = 9.5
) {
  grid <- grid |>
    mutate(result_chr = as.character(as.integer(.data[[result_col]])))

  cells_with_data <- grid |> filter(svi_gsvi > 0L)

  p <- ggplot() +
    geom_sf(data = grid, fill = "#fafafa", colour = NA) +
    geom_sf(
      data = cells_with_data,
      aes(fill = result_chr),
      colour = NA
    ) +
    geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.0) +
    scale_fill_manual(
      name = "Waste accumulation level",
      values = RESULT_PALETTE,
      labels = RESULT_LABELS,
      drop = FALSE
    ) +
    mitigation_coord(st_crs(WGS84), boundary) +
    labs(
      title = panel_title,
      subtitle = subtitle_text,
      x = "Longitude",
      y = "Latitude"
    ) +
    mitigation_map_theme(base_size) +
    theme(
      plot.subtitle = element_text(
        size = base_size - 1.5,
        hjust = 0.5,
        colour = "#5C6B7A",
        margin = margin(b = 6)
      )
    )

  mitigation_map_decorations(p)
}

message("Reading context layer and boundary...")
ctx <- read_wgs84(CONTEXT_GPKG)
boundary <- read_wgs84(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"))

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

# 1. Improvement area
message("Building improvement area map...")
n_imp <- sum(ctx$ctx_improvement == 1L, na.rm = TRUE)
imp_cells <- ctx |> filter(ctx_improvement == 1L)

p_imp <- ggplot() +
  geom_sf(data = ctx, fill = "#fafafa", colour = NA) +
  geom_sf(
    data = imp_cells,
    fill = alpha(IMPROVEMENT_FILL, 0.55),
    colour = IMPROVEMENT_EDGE,
    linewidth = 0.15
  ) +
  geom_sf(data = boundary, fill = NA, colour = "black", linewidth = 1.0) +
  mitigation_coord(st_crs(WGS84), boundary) +
  labs(
    title = "100 m cells with observed improvement (G+self vs GSVI)",
    subtitle = paste0(
      "Cells where self-collected arm adds SVI images or waste detections (n = ",
      format(n_imp, big.mark = ",", trim = TRUE),
      ")"
    ),
    x = "Longitude",
    y = "Latitude"
  ) +
  mitigation_map_theme(11) +
  theme(
    plot.subtitle = element_text(
      size = 9.5,
      hjust = 0.5,
      colour = "#5C6B7A",
      margin = margin(b = 6)
    )
  )

p_imp <- mitigation_map_decorations(p_imp)
save_mitigation_map(p_imp, file.path(FIG_DIR, "Grid_context_improvement_area.png"), boundary)
message("  Grid_context_improvement_area.png")

# 2. Changed cells — side-by-side result class
message("Building changed-cell comparison...")
n_chg <- sum(ctx$ctx_class_changed == 1L, na.rm = TRUE)
changed <- ctx |> filter(ctx_class_changed == 1L)

p_gsvi <- build_result_map(
  grid = changed,
  boundary = boundary,
  result_col = "result_gsvi",
  panel_title = "(A) GSVI arm — changed cells",
  subtitle_text = paste0("Fixed-band level within improvement area (n = ", format(n_chg, big.mark = ","), ")"),
  base_size = 9
)

p_sc <- build_result_map(
  grid = changed,
  boundary = boundary,
  result_col = "result_sc",
  panel_title = "(B) G+self arm — changed cells",
  subtitle_text = "Same cells as (A); compare class shift",
  base_size = 9
)

comparison_changed <- wrap_plots(p_gsvi, p_sc, ncol = 2) +
  plot_annotation(
    title = "Waste accumulation level comparison — changed cells",
    subtitle = "Cells with new observations and/or class change after adding self-collected data",
    theme = theme(
      plot.title = element_text(face = "bold", size = 13, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 8))
    )
  )

comparison_size <- mitigation_fig_size(boundary, width = 8, title_pad = 0.9)
ggsave(
  file.path(FIG_DIR, "Grid_context_changed_comparison.png"),
  plot = comparison_changed,
  width = 16,
  height = comparison_size$height,
  dpi = 600,
  bg = "white"
)
message("  Grid_context_changed_comparison.png")

# 3. SVI context — gsvi vs sc within ctx_svi
message("Building SVI-context comparison...")
n_svi <- sum(ctx$ctx_svi == 1L, na.rm = TRUE)
svi_cells <- ctx |> filter(ctx_svi == 1L)

p_svi_gsvi <- build_result_map(
  grid = svi_cells,
  boundary = boundary,
  result_col = "result_gsvi",
  panel_title = "(A) GSVI arm — SVI context",
  subtitle_text = paste0("Cells with ≥1 GSVI image (n = ", format(n_svi, big.mark = ","), ")"),
  base_size = 9
)

p_svi_sc <- build_result_map(
  grid = svi_cells,
  boundary = boundary,
  result_col = "result_sc",
  panel_title = "(B) G+self arm — SVI context",
  subtitle_text = "Same SVI-context cells as (A)",
  base_size = 9
)

comparison_svi <- wrap_plots(p_svi_gsvi, p_svi_sc, ncol = 2) +
  plot_annotation(
    title = "Waste accumulation level comparison — SVI context",
    subtitle = "Subset of grid where Google Street View imagery is present",
    theme = theme(
      plot.title = element_text(face = "bold", size = 13, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#5C6B7A", margin = margin(b = 8))
    )
  )

ggsave(
  file.path(FIG_DIR, "Grid_context_svi_comparison.png"),
  plot = comparison_svi,
  width = 16,
  height = comparison_size$height,
  dpi = 600,
  bg = "white"
)
message("  Grid_context_svi_comparison.png")

# 4. Summary bars — pooled ratio by context
message("Building context summary bars...")
summary_df <- read.csv(STRATIFIED_CSV, stringsAsFactors = FALSE) |>
  filter(label %in% c(
    "City-wide",
    "Road (≥25 m)",
    "SVI (≥1 GSVI image)",
    "Self-collected touch"
  )) |>
  mutate(
    context = factor(
      label,
      levels = c(
        "City-wide",
        "Road (≥25 m)",
        "SVI (≥1 GSVI image)",
        "Self-collected touch"
      )
    )
  )

bar_long <- summary_df |>
  select(context, pooled_ratio_gsvi_pct, pooled_ratio_sc_pct) |>
  pivot_longer(
    cols = c(pooled_ratio_gsvi_pct, pooled_ratio_sc_pct),
    names_to = "arm",
    values_to = "pooled_ratio_pct"
  ) |>
  mutate(
    pooled_ratio = pooled_ratio_pct / 100,
    arm = recode(arm,
      pooled_ratio_gsvi_pct = "GSVI only",
      pooled_ratio_sc_pct = "GSVI + self-collected"
    )
  )

p_bars <- ggplot(bar_long, aes(x = context, y = pooled_ratio, fill = arm)) +
  geom_col(position = position_dodge(width = 0.75), width = 0.65) +
  scale_fill_manual(
    name = "Data arm",
    values = c("GSVI only" = "#6B4226", "GSVI + self-collected" = "#7B68EE")
  ) +
  scale_y_continuous(
    labels = label_number(accuracy = 0.0001),
    expand = expansion(mult = c(0, 0.08))
  ) +
  labs(
    title = "Pooled waste/SVI ratio by analysis context",
    subtitle = "Sum(waste) / sum(SVI images) within each non-exclusive context",
    x = NULL,
    y = "Pooled waste/SVI ratio"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 13, hjust = 0.5),
    plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#5C6B7A"),
    legend.position = "bottom",
    axis.text.x = element_text(angle = 25, hjust = 1)
  )

ggsave(
  file.path(FIG_DIR, "Grid_context_summary_bars.png"),
  plot = p_bars,
  width = 10,
  height = 6,
  dpi = 600,
  bg = "white"
)
message("  Grid_context_summary_bars.png")

message("Done.")

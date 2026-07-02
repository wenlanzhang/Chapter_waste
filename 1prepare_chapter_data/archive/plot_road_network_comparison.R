#!/usr/bin/env Rscript
# Compare local vs OSMnx Nairobi road networks

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(readr)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "map_theme.R"))

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "1prepare_chapter_data")

summary_df <- read_csv(file.path(DATA_DIR, "Nairobi_road_comparison_summary.csv"), show_col_types = FALSE)
type_comp <- read_csv(file.path(DATA_DIR, "Nairobi_road_type_comparison.csv"), show_col_types = FALSE)
composition <- read_csv(
  file.path(DATA_DIR, "Nairobi_road_type_composition_comparison.csv"),
  show_col_types = FALSE
)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

# 1) Summary metrics
summary_long <- summary_df |>
  select(metric, local, osmnx) |>
  pivot_longer(c(local, osmnx), names_to = "source", values_to = "value") |>
  mutate(
    source = recode(source, local = "Local OSM file", osmnx = "OSMnx download"),
    metric_label = recode(
      metric,
      segment_count = "Road segments",
      total_length_km = "Total length (km)",
      road_type_count = "Road types"
    )
  )

p_summary <- ggplot(summary_long, aes(x = metric_label, y = value, fill = source)) +
  geom_col(position = position_dodge(width = 0.75), width = 0.65, color = "white", linewidth = 0.3) +
  geom_text(
    aes(label = comma(round(value, 1))),
    position = position_dodge(width = 0.75),
    vjust = -0.4,
    size = 3.2
  ) +
  scale_fill_manual(values = c("Local OSM file" = "#80b1d3", "OSMnx download" = "#fb8072"), name = NULL) +
  scale_y_continuous(labels = comma, expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "Nairobi road network comparison",
    subtitle = "Local cleaned extract vs OSMnx download",
    x = NULL,
    y = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", hjust = 0.5),
    plot.subtitle = element_text(hjust = 0.5, color = "grey35"),
    legend.position = c(0.98, 0.98),
    legend.justification = c(1, 1),
    legend.background = element_rect(fill = alpha("white", 0.9), color = NA)
  )

ggsave(
  file.path(FIG_DIR, "Nairobi_road_comparison_summary.png"),
  p_summary, width = 10, height = 6, dpi = 300, bg = "white"
)
message("  Nairobi_road_comparison_summary.png")

# 2) Top road types by length share
top_types <- composition |>
  group_by(type) |>
  summarise(max_pct = max(pct_length), .groups = "drop") |>
  arrange(desc(max_pct)) |>
  slice_head(n = 8) |>
  pull(type)

type_plot_df <- composition |>
  filter(type %in% top_types) |>
  mutate(
    source = recode(source, local = "Local OSM file", osmnx = "OSMnx download"),
    type = factor(type, levels = rev(top_types))
  )

p_types <- ggplot(type_plot_df, aes(x = pct_length, y = type, fill = source)) +
  geom_col(position = position_dodge(width = 0.75), width = 0.7, color = "white", linewidth = 0.25) +
  scale_fill_manual(values = c("Local OSM file" = "#80b1d3", "OSMnx download" = "#fb8072"), name = NULL) +
  scale_x_continuous(labels = function(x) paste0(x, "%"), expand = expansion(mult = c(0, 0.05))) +
  labs(
    title = "Road-type composition comparison",
    subtitle = "Share of total network length for top 8 types",
    x = "Percent of total length",
    y = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", hjust = 0.5),
    plot.subtitle = element_text(hjust = 0.5, color = "grey35"),
    legend.position = c(0.98, 0.03),
    legend.justification = c(1, 0),
    legend.background = element_rect(fill = alpha("white", 0.9), color = NA)
  )

ggsave(
  file.path(FIG_DIR, "Nairobi_road_comparison_types.png"),
  p_types, width = 10, height = 7, dpi = 300, bg = "white"
)
message("  Nairobi_road_comparison_types.png")

message("Road maps: Rscript 1prepare_chapter_data/plot_road_figures.R")
message("Done.")

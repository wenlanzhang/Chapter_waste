#!/usr/bin/env Rscript
# Road network composition by OSM highway type (Nairobi_road_line_32737.gpkg)

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(readr)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."

DATA_DIR <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/1prepare_chapter_data"
FIG_DIR <- file.path(script_dir, "..", "Figure", "1prepare_chapter_data")
CRS_EA <- 32737
GROUP_THRESHOLD_PCT <- 2.0

roads <- st_read(file.path(DATA_DIR, "Nairobi_road_line_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)

roads_df <- data.frame(
  type = roads$type,
  length_km = if ("length_m" %in% names(roads)) roads$length_m / 1000 else as.numeric(st_length(roads)) / 1000
)

composition <- roads_df |>
  group_by(type) |>
  summarise(
    segment_count = n(),
    length_km = sum(length_km),
    .groups = "drop"
  ) |>
  mutate(
    pct_length = 100 * length_km / sum(length_km),
    pct_count = 100 * segment_count / sum(segment_count)
  ) |>
  arrange(desc(length_km))

readr::write_csv(
  composition,
  file.path(DATA_DIR, "Nairobi_road_type_composition.csv")
)
message("Wrote Nairobi_road_type_composition.csv")

# Group minor types for a readable pie chart
major <- composition |> filter(pct_length >= GROUP_THRESHOLD_PCT)
minor <- composition |> filter(pct_length < GROUP_THRESHOLD_PCT)

plot_df <- bind_rows(
  major,
  tibble(
    type = "Other",
    segment_count = sum(minor$segment_count),
    length_km = sum(minor$length_km),
    pct_length = sum(minor$pct_length),
    pct_count = sum(minor$pct_count)
  )
) |>
  mutate(
    type = factor(type, levels = type[order(pct_length)]),
    label = if_else(
      pct_length >= 3,
      paste0(type, "\n", percent(pct_length / 100, accuracy = 0.1)),
      NA_character_
    )
  )

n_types <- nrow(plot_df)
palette_cols <- c(
  "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
  "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd",
  "#ccebc5", "#ffed6f", "#a6cee3", "#1f78b4", "#b2df8a"
)
fill_colors <- setNames(
  palette_cols[seq_len(n_types)],
  levels(plot_df$type)
)

total_km <- sum(composition$length_km)
total_segments <- sum(composition$segment_count)

p <- ggplot(plot_df, aes(x = 2, y = pct_length, fill = type)) +
  geom_col(width = 1, color = "white", linewidth = 0.45) +
  coord_polar(theta = "y", clip = "off") +
  xlim(0.5, 2.5) +
  geom_text(
    aes(label = label),
    position = position_stack(vjust = 0.5),
    size = 3.2,
    lineheight = 0.95,
    color = "grey15",
    fontface = "bold"
  ) +
  scale_fill_manual(values = fill_colors, name = "Road type") +
  labs(
    title = "Nairobi road network by OSM highway type",
    subtitle = sprintf(
      "%s km total | %s segments | share by road length",
      comma(round(total_km, 1)),
      comma(total_segments)
    ),
    caption = sprintf(
      "Types below %.1f%% of length grouped as Other | Source: Nairobi_road_line_32737.gpkg",
      GROUP_THRESHOLD_PCT
    )
  ) +
  theme_void(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", size = 15, hjust = 0.5, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 11, hjust = 0.5, color = "grey35", margin = margin(b = 10)),
    plot.caption = element_text(size = 8.5, color = "grey45", hjust = 0.5, margin = margin(t = 8)),
    legend.position = c(0.98, 0.03),
    legend.justification = c(1, 0),
    legend.background = element_rect(fill = alpha("white", 0.9), color = NA),
    legend.box.background = element_rect(fill = alpha("white", 0.9), color = "grey75", linewidth = 0.3),
    legend.key.height = unit(0.45, "cm"),
    legend.text = element_text(size = 8.5),
    plot.margin = margin(16, 16, 16, 16)
  )

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

report_path <- file.path(FIG_DIR, "Nairobi_road_type_composition.png")
ggsave(report_path, p, width = 10, height = 10, dpi = 300, bg = "white")
message("  ", basename(report_path))

message("Done.")

#!/usr/bin/env Rscript
# Optional SE analysis — admin choropleths (waste rate + key covariates)

# suppressWarnings: packages may be built under a newer R than this session
suppressWarnings(suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(ggspatial)
  library(scales)
  library(patchwork)
}))

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
repo_root <- normalizePath(file.path(script_dir, ".."))
source(file.path(repo_root, "R", "chapter_paths.R"))
source(file.path(repo_root, "R", "map_theme.R"))
source(file.path(repo_root, "R", "chapter_colours.R"))

year <- 2019
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1) {
  year <- as.integer(args[[1]])
}

DATA_DIR <- file.path(chapter_data_root, "99_optional_SE_analysis")
FIG_DIR <- file.path(repo_root, "Figure", "99_optional_SE_analysis")
PREP_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
GPKG <- file.path(DATA_DIR, sprintf("Nairobi_admin_se_waste_%d.gpkg", year))
BOUNDARY <- file.path(PREP_DIR, "Nairobi_boundary_polygon_32737.gpkg")

if (!file.exists(GPKG)) {
  stop("Missing ", GPKG, "\nRun: python 99_optional_SE_analysis/1_admin_se_waste_join.py")
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

admin <- st_read(GPKG, quiet = TRUE)
boundary <- st_read(BOUNDARY, quiet = TRUE)
admin_cov <- admin %>% filter(has_svi)

theme_se_map <- function() {
  map_theme(transparent_bg = FALSE, show_grid = FALSE) +
    theme(
      legend.position = "right",
      plot.title = element_text(size = 12),
      plot.subtitle = element_text(size = 9)
    )
}

plot_choropleth <- function(data, column, title, subtitle, palette = "YlOrBr", na_fill = "grey90") {
  vals <- data[[column]]
  vals <- vals[is.finite(vals)]
  if (!length(vals)) {
    stop("No finite values for ", column)
  }
  ggplot() +
    geom_sf(data = boundary, fill = "grey96", colour = "grey40", linewidth = 0.35) +
    geom_sf(
      data = data,
      aes(fill = .data[[column]]),
      colour = "grey50",
      linewidth = 0.15
    ) +
    scale_fill_distiller(
      name = NULL,
      palette = palette,
      direction = 1,
      na.value = na_fill,
      labels = label_number(accuracy = 0.01)
    ) +
    coord_map_limits(boundary) +
    map_elements() +
    labs(title = title, subtitle = subtitle) +
    theme_se_map()
}

message("Plotting waste-positive rate...")
p_rate <- plot_choropleth(
  admin_cov,
  "waste_positive_rate",
  "Waste-positive rate among GSVI panoids",
  sprintf("Admin units with ≥1 panoid · SE year %d", year),
  palette = "YlOrBr"
)
out_rate <- file.path(FIG_DIR, sprintf("SE_waste_positive_rate_%d.png", year))
ggsave(out_rate, p_rate, width = 8.5, height = 8, dpi = 300, bg = "white")
message("Wrote ", out_rate)

message("Plotting GRDI...")
p_grdi <- plot_choropleth(
  admin,
  "grdi",
  "Global gridded relative deprivation (GRDI)",
  sprintf("All admin units · SE year %d", year),
  palette = "RdPu"
)
out_grdi <- file.path(FIG_DIR, sprintf("SE_grdi_%d.png", year))
ggsave(out_grdi, p_grdi, width = 8.5, height = 8, dpi = 300, bg = "white")
message("Wrote ", out_grdi)

message("Plotting population density...")
p_pop <- plot_choropleth(
  admin,
  "density_pop",
  "Population density",
  sprintf("All admin units · SE year %d", year),
  palette = "Blues"
)
out_pop <- file.path(FIG_DIR, sprintf("SE_density_pop_%d.png", year))
ggsave(out_pop, p_pop, width = 8.5, height = 8, dpi = 300, bg = "white")
message("Wrote ", out_pop)

message("Plotting comparison panel...")
p_panel <- (p_rate + theme(plot.title = element_text(size = 10))) +
  (p_grdi + theme(plot.title = element_text(size = 10))) +
  (p_pop + theme(plot.title = element_text(size = 10))) +
  plot_layout(ncol = 3) +
  plot_annotation(
    title = "Admin-unit socio-economic context vs waste-positive rate",
    subtitle = sprintf("GSVI panoids · SE covariates %d", year)
  )
out_panel <- file.path(FIG_DIR, sprintf("SE_waste_covariate_panel_%d.png", year))
ggsave(out_panel, p_panel, width = 14, height = 5.5, dpi = 300, bg = "white")
message("Wrote ", out_panel)
message("Done.")

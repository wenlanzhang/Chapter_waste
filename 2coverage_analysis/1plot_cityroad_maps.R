#!/usr/bin/env Rscript
# City -> road on the 100 m grid: three maps from 1cityroad.py
#   (1) road access class: intersects road / within buffer / road-excluded
#   (2) road density (km/km²) for cells with road
#   (3) distance to nearest road for road-excluded cells

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
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

parse_args <- function() {
  defaults <- list(road_buffer = 50)
  for (arg in commandArgs(trailingOnly = TRUE)) {
    if (grepl("^--road-buffer-m=", arg)) defaults$road_buffer <- as.numeric(sub("^--road-buffer-m=", "", arg))
  }
  defaults
}

args <- parse_args()
buf <- as.integer(args$road_buffer)
tag <- sprintf("buf%dm", buf)

grid <- st_read(file.path(DATA_DIR, "1_Nairobi_cityroad_grid100m_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)
summary <- read.csv(file.path(DATA_DIR, sprintf("1_Nairobi_cityroad_summary_%s.csv", tag)))
boundary <- st_read(file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE) |>
  st_transform(CRS_EA)

n_cells <- nrow(grid)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
message("Writing figures to ", FIG_DIR)

# --- (1) Road access class ---------------------------------------------------
ACCESS_LEVELS <- c("intersects", "near", "excluded")
ACCESS_LABELS <- c(
  intersects = "Intersects a road",
  near = sprintf("Within %d m of a road", buf),
  excluded = sprintf("Road-excluded (>%d m)", buf)
)
# Light grey = baseline, tan = near, dark brown = road-excluded
ACCESS_COLOURS <- c(
  intersects = ROAD_BASELINE_COLOUR,
  near = GSVI_COLOUR,
  excluded = WASTE_DARK_COLOUR
)

grid <- grid |>
  mutate(
    access_class = case_when(
      intersects_road == 1 ~ "intersects",
      road_accessible == 1 ~ "near",
      TRUE ~ "excluded"
    ),
    access_class = factor(access_class, levels = ACCESS_LEVELS)
  )

share <- grid |>
  st_drop_geometry() |>
  count(access_class, .drop = FALSE) |>
  mutate(pct = 100 * n / sum(n))
pct_of <- function(cls) share$pct[share$access_class == cls]

p_access <- make_base_map(
  boundary,
  title = "Road access on the 100 m grid",
  subtitle = sprintf(
    "%s cells | intersects %.1f%% | within %d m %.1f%% | excluded %.1f%%",
    comma(n_cells), pct_of("intersects"), buf, pct_of("near"), pct_of("excluded")
  ),
  caption = "Cleaned local OSM segments (Step 1a) | cell edge distance to nearest road",
  transparent_bg = TRUE
) +
  geom_sf(data = grid, aes(fill = access_class), color = NA, linewidth = 0) +
  scale_fill_manual(name = "Road access", values = ACCESS_COLOURS, labels = ACCESS_LABELS, drop = FALSE) +
  theme(legend.key.size = unit(0.55, "cm"), legend.text = element_text(size = 7.5))

save_map(p_access, file.path(FIG_DIR, sprintf("1_Nairobi_cityroad_access_%s.png", tag)),
         limits = boundary, base_size = 10, bg = "transparent")

# --- (2) Road density (cells with road) -------------------------------------
with_road <- grid |> filter(intersects_road == 1)
p_density <- make_base_map(
  boundary,
  title = "Road density on the 100 m grid",
  subtitle = sprintf(
    "%s cells with road | mean %.1f km/km² | median road length %s m",
    comma(nrow(with_road)),
    summary$mean_road_density_with_road_km_per_km2,
    comma(round(summary$median_road_length_with_road_m))
  ),
  caption = "Mapped road length inside each cell / cell area | cells without road in grey",
  transparent_bg = TRUE
) +
  geom_sf(data = grid |> filter(intersects_road == 0), fill = ROAD_BASELINE_COLOUR, color = NA, linewidth = 0) +
  geom_sf(data = with_road, aes(fill = road_density_km_per_km2), color = NA, linewidth = 0) +
  scale_fill_gradientn(
    name = "Road density\n(km/km²)",
    colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR),
    limits = c(0, quantile(with_road$road_density_km_per_km2, 0.99)),
    oob = squish,
    labels = label_number(accuracy = 1)
  )

save_map(p_density, file.path(FIG_DIR, "1_Nairobi_cityroad_density_grid100m.png"),
         limits = boundary, base_size = 10, bg = "transparent")

# --- (3) Distance to nearest road (road-excluded cells) ---------------------
excluded <- grid |> filter(road_accessible == 0)
p_dist <- make_base_map(
  boundary,
  title = "Distance to nearest road, road-excluded cells",
  subtitle = sprintf(
    "%s excluded cells (%.1f%%) | median %s m | 90th pct %s m",
    comma(nrow(excluded)), summary$pct_cells_road_excluded,
    comma(round(summary$median_dist_road_edge_excluded_m)),
    comma(round(summary$p90_dist_road_edge_excluded_m))
  ),
  caption = sprintf("Cell edge to nearest mapped road | road-accessible cells (≤%d m) in grey", buf),
  transparent_bg = TRUE
) +
  # Accessible cells as the grey baseline; excluded cells on the same brown ramp as the density map
  geom_sf(data = grid |> filter(road_accessible == 1), fill = ROAD_BASELINE_COLOUR, color = NA, linewidth = 0) +
  geom_sf(data = excluded, aes(fill = dist_road_edge_m), color = NA, linewidth = 0) +
  scale_fill_gradientn(
    name = "Distance to\nroad (m)",
    colours = c(CHAPTER_SEQ_LOW, GSVI_COLOUR, WASTE_COLOUR),
    limits = c(buf, quantile(excluded$dist_road_edge_m, 0.99)),
    oob = squish,
    labels = label_number(accuracy = 1)
  )

save_map(p_dist, file.path(FIG_DIR, sprintf("1_Nairobi_cityroad_distance_%s.png", tag)),
         limits = boundary, base_size = 10, bg = "transparent")

message("Done.")

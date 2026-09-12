#!/usr/bin/env Rscript
# Indicator provenance choropleth — 100 m GSVI IDEAMaps grid

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

DATA_ROOT <- chapter_data_root
INPUT_DIR <- file.path(DATA_ROOT, "1prepare_chapter_data")
EXT_DIR <- file.path(DATA_ROOT, "0_extend_grid")
GRID_DIR <- file.path(DATA_ROOT, "3_100m", "grid")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")
CRS_EA <- 32737

# Prefer Mollweide-extended grid when present
extended_grid <- file.path(EXT_DIR, "Nairobi_grid_100m_extended_32737.gpkg")
angela_grid <- file.path(INPUT_DIR, "Nairobi_grid_100m_32737.gpkg")
GRID_GPKG <- if (file.exists(extended_grid)) extended_grid else angela_grid
BOUNDARY_GPKG <- file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg")
CELLS_CSV <- file.path(GRID_DIR, "Nairobi_indicator_provenance_cells.csv")
SUMMARY_CSV <- file.path(GRID_DIR, "Nairobi_indicator_provenance_summary.csv")

PROVENANCE_LEVELS <- c(
  "Direct observation",
  "Interpolated support",
  "Unsupported, platform-coded low"
)

# Chapter sequential browns: darker = stronger local evidence (matches coverage maps)
PROVENANCE_COLOURS <- c(
  "Direct observation" = CHAPTER_SEQ_HIGH,
  "Interpolated support" = CHAPTER_SEQ_MID,
  "Unsupported, platform-coded low" = CHAPTER_SEQ_LOW
)

PROVENANCE_LABELS <- c(
  "Direct observation" = "Directly observed",
  "Interpolated support" = "Interpolated",
  "Unsupported, platform-coded low" = "Unsupported (classified as low)"
)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(CELLS_CSV)) {
  stop(
    "Missing ", basename(CELLS_CSV),
    "\nRun first: python 3_100m/4_indicator_provenance.py"
  )
}

message("Reading grid and provenance labels...")
grid <- st_read(GRID_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
boundary <- st_read(BOUNDARY_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
cells <- read.csv(CELLS_CSV, stringsAsFactors = FALSE)

if (!"cell_id" %in% names(grid)) {
  stop(basename(GRID_GPKG), " must include a cell_id column")
}
if (anyDuplicated(cells$cell_id)) {
  stop("Duplicate cell_id in provenance cells CSV")
}

joined <- grid |>
  mutate(cell_id = as.integer(cell_id)) |>
  left_join(
    cells |>
      transmute(
        cell_id = as.integer(cell_id),
        indicator_provenance
      ),
    by = "cell_id"
  )

n_missing <- sum(is.na(joined$indicator_provenance))
if (n_missing > 0) {
  stop(n_missing, " grid cells lack provenance labels; re-run 4_indicator_provenance.py")
}

joined <- joined |>
  mutate(
    indicator_provenance = factor(indicator_provenance, levels = PROVENANCE_LEVELS)
  )

counts <- joined |>
  st_drop_geometry() |>
  count(indicator_provenance, name = "n") |>
  mutate(share = 100 * n / sum(n))

subtitle <- sprintf(
  "100 m grid | Direct %.1f%% | Interpolated %.1f%% | Unsupported %.1f%% (n = %s)",
  counts$share[counts$indicator_provenance == "Direct observation"],
  counts$share[counts$indicator_provenance == "Interpolated support"],
  counts$share[counts$indicator_provenance == "Unsupported, platform-coded low"],
  comma(nrow(joined))
)

p <- make_base_map(
  boundary,
  title = "Indicator provenance on the 100 m grid",
  subtitle = subtitle,
  caption = paste0(
    "GSVI arm IDEAMaps pipeline on Mollweide-extended 100 m grid | ",
    "Direct: \u22651 local image | Interpolated: spatial fill | ",
    "Unsupported: missing after fill, coded low"
  ),
  transparent_bg = TRUE
) +
  geom_sf(
    data = joined,
    aes(fill = indicator_provenance),
    color = NA,
    linewidth = 0
  ) +
  scale_fill_manual(
    name = "Provenance",
    values = PROVENANCE_COLOURS,
    labels = PROVENANCE_LABELS,
    drop = FALSE
  ) +
  guides(
    fill = guide_legend(
      override.aes = list(color = "grey70", linewidth = 0.2)
    )
  ) +
  theme(
    legend.key.size = unit(0.55, "cm"),
    legend.text = element_text(size = 7.5),
    legend.title = element_text(size = 8.5, face = "bold")
  )

out_path <- file.path(FIG_DIR, "Indicator_provenance_100m.png")
save_map(p, out_path, limits = boundary, base_size = 10, bg = "transparent")
message("Done: ", out_path)

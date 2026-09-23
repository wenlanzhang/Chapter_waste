#!/usr/bin/env Rscript
# Mollweide-extended grid maps: (1) Angela vs fill (2) provenance

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
FIG_DIR <- file.path(script_dir, "..", "Figure", "0_extend_grid")
CRS_EA <- 32737

BOUNDARY_GPKG <- file.path(INPUT_DIR, "Nairobi_boundary_polygon_32737.gpkg")
GRID_GPKG <- file.path(EXT_DIR, "Nairobi_grid_100m_extended_32737.gpkg")
# Per-arm provenance (keys match lib/arms.py)
ARMS <- c(gsvi = "GSVI only", gsvi_selfcollected = "GSVI + self-collected")
cells_csv <- function(arm) {
  file.path(EXT_DIR, sprintf("Nairobi_indicator_provenance_cells_extended_%s.csv", arm))
}
SUMMARY_CSV <- file.path(EXT_DIR, "Nairobi_grid_extension_summary.csv")

SOURCE_LEVELS <- c("angela_original", "extension_mollweide_100m")
SOURCE_LABELS <- c(
  angela_original = "Angela original",
  extension_mollweide_100m = "Extension (Mollweide 100 m)"
)
SOURCE_COLOURS <- c(
  angela_original = CHAPTER_SEQ_HIGH,
  extension_mollweide_100m = HIGHLIGHT_POSITIVE_COLOUR
)

PROVENANCE_LEVELS <- c(
  "Direct observation",
  "Interpolated support",
  "Unsupported, platform-coded low"
)
PROVENANCE_COLOURS <- c(
  "Direct observation" = CHAPTER_SEQ_HIGH,
  "Interpolated support" = CHAPTER_SEQ_MID,
  "Unsupported, platform-coded low" = CHAPTER_SEQ_LOW
)
PROVENANCE_LABELS <- c(
  "Direct observation" = "Direct observation",
  "Interpolated support" = "Interpolated support",
  "Unsupported, platform-coded low" = "Unsupported (coded low)"
)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

if (!file.exists(GRID_GPKG)) {
  stop("Missing extended grid. Run: python 0_extend_grid/1_extend_grid.py")
}

message("Reading Mollweide-extended grid...")
boundary <- st_read(BOUNDARY_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
grid <- st_read(GRID_GPKG, quiet = TRUE) |> st_transform(CRS_EA)
grid <- grid |>
  mutate(grid_source = factor(grid_source, levels = SOURCE_LEVELS))

n_angela <- sum(grid$grid_source == "angela_original", na.rm = TRUE)
n_ext <- sum(grid$grid_source == "extension_mollweide_100m", na.rm = TRUE)

ext_summary <- if (file.exists(SUMMARY_CSV)) {
  read.csv(SUMMARY_CSV, stringsAsFactors = FALSE)
} else {
  NULL
}
uncovered_before <- if (!is.null(ext_summary)) {
  as.numeric(ext_summary$value[ext_summary$item == "uncovered_before_pct"])
} else {
  NA_real_
}
uncovered_after <- if (!is.null(ext_summary)) {
  as.numeric(ext_summary$value[ext_summary$item == "uncovered_after_pct"])
} else {
  NA_real_
}

p_source <- make_base_map(
  boundary,
  title = "Extended 100 m grid (Mollweide ESRI:54009)",
  subtitle = sprintf(
    "Angela %s | Extension %s | uncovered before %.1f%% \u2192 after %.1f%%",
    comma(n_angela),
    comma(n_ext),
    uncovered_before,
    uncovered_after
  ),
  caption = paste0(
    "IDEAMaps/GHSL Mollweide 100 m fill | ",
    "standalone 0_extend_grid/ | existing cell_id values preserved"
  ),
  transparent_bg = TRUE
) +
  geom_sf(data = grid, aes(fill = grid_source), color = NA, linewidth = 0) +
  scale_fill_manual(
    name = "Grid source",
    values = SOURCE_COLOURS,
    labels = SOURCE_LABELS,
    drop = FALSE
  ) +
  theme(
    legend.key.size = unit(0.55, "cm"),
    legend.text = element_text(size = 7.5)
  )

source_path <- file.path(FIG_DIR, "Grid_extension_angela_vs_fill.png")
save_map(p_source, source_path, limits = boundary, base_size = 10, bg = "transparent")

plot_provenance <- function(arm) {
  path <- cells_csv(arm)
  if (!file.exists(path)) {
    message("Provenance CSV not found for arm ", arm, "; skip provenance map.")
    message("Run: python 0_extend_grid/2_provenance_extended.py")
    return(invisible(NULL))
  }

  cells <- read.csv(path, stringsAsFactors = FALSE)
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

  if (anyNA(joined$indicator_provenance)) {
    stop("Some extended-grid cells lack provenance labels (arm ", arm, ").")
  }

  joined <- joined |>
    mutate(
      indicator_provenance = factor(indicator_provenance, levels = PROVENANCE_LEVELS)
    )

  counts <- joined |>
    st_drop_geometry() |>
    count(indicator_provenance, name = "n") |>
    mutate(share = 100 * n / sum(n))

  prov_subtitle <- sprintf(
    "Extended grid n = %s | Direct %.1f%% | Interpolated %.1f%% | Unsupported %.1f%%",
    comma(nrow(joined)),
    counts$share[counts$indicator_provenance == "Direct observation"],
    counts$share[counts$indicator_provenance == "Interpolated support"],
    counts$share[counts$indicator_provenance == "Unsupported, platform-coded low"]
  )

  p_prov <- make_base_map(
    boundary,
    title = sprintf("Indicator provenance (Mollweide-extended 100 m grid, %s)", ARMS[[arm]]),
    subtitle = prov_subtitle,
    caption = paste0(
      ARMS[[arm]], " arm on Angela + Mollweide 100 m fill | Direct: \u22651 local image | ",
      "Interpolated: spatial fill | Unsupported: missing after fill, coded low"
    ),
    transparent_bg = TRUE
  ) +
    geom_sf(data = joined, aes(fill = indicator_provenance), color = NA, linewidth = 0) +
    scale_fill_manual(
      name = "Provenance",
      values = PROVENANCE_COLOURS,
      labels = PROVENANCE_LABELS,
      drop = FALSE
    ) +
    theme(
      legend.key.size = unit(0.55, "cm"),
      legend.text = element_text(size = 7.5)
    )

  prov_path <- file.path(FIG_DIR, sprintf("Indicator_provenance_100m_extended_%s.png", arm))
  save_map(p_prov, prov_path, limits = boundary, base_size = 10, bg = "transparent")
}

for (arm in names(ARMS)) plot_provenance(arm)

message("Done. Figures in ", FIG_DIR)

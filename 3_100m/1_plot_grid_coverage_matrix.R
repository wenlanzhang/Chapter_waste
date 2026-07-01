#!/usr/bin/env Rscript
# Grid coverage summary — cell-count bars + nested coverage heatmap

suppressPackageStartupMessages({
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

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
GRID_DIR <- file.path(DATA_ROOT, "3_100m")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_100m")
TABLE_DIR <- file.path(GRID_DIR, "thesis_table")

CELL_COUNTS_CSV <- file.path(TABLE_DIR, "Nairobi_grid_coverage_cell_counts.csv")
MATRIX_CSV <- file.path(TABLE_DIR, "Nairobi_grid_coverage_matrix_pct.csv")

CONTEXT_ORDER <- c(
  "City",
  "Road (>=25 m)",
  "SVI (>=1 image)",
  "Waste (>=1 detection)"
)

CHOCOLATE_PALETTE <- c("#fafafa", "#E5C8A9", "#C9A27F", "#8B5E3C", "#6B4226")

FIGURE_CAPTION <- paste0(
  "IDEAMaps 100 m grid, Nairobi (GSVI arm). ",
  "Road: >=25 m per cell | SVI: >=1 image | Waste: >=1 detection.\n",
  "Panel B: share of each column context (row / column x 100)."
)

normalize_context_label <- function(x) {
  x <- gsub("\u2265", ">=", x, fixed = TRUE)
  gsub("\u2192", "->", x, fixed = TRUE)
}

read_cell_counts <- function(path) {
  df <- read.csv(path, stringsAsFactors = FALSE)
  col_cells <- intersect(names(df), c("Grid.cells", "Grid cells"))[1]
  df |>
    mutate(
      Context = normalize_context_label(Context),
      Context = factor(Context, levels = CONTEXT_ORDER),
      n_cells = as.integer(gsub(",", "", .data[[col_cells]]))
    )
}

read_matrix <- function(path) {
  wide <- read.csv(path, stringsAsFactors = FALSE, check.names = FALSE)
  names(wide)[1] <- "Context"
  wide$Context <- normalize_context_label(wide$Context)
  names(wide)[-1] <- normalize_context_label(names(wide)[-1])
  wide |>
    pivot_longer(
      cols = -Context,
      names_to = "col_context",
      values_to = "pct_of_col"
    ) |>
    rename(row_context = Context) |>
    mutate(
      row_context = factor(row_context, levels = CONTEXT_ORDER),
      col_context = factor(col_context, levels = CONTEXT_ORDER),
      pct_of_col = as.numeric(pct_of_col),
      label = sprintf("%.1f%%", pct_of_col)
    )
}

build_count_panel <- function(counts) {
  ggplot(counts, aes(x = Context, y = n_cells, fill = Context)) +
    geom_col(width = 0.68, colour = "grey35", linewidth = 0.25) +
    geom_text(
      aes(label = format(n_cells, big.mark = ",", trim = TRUE)),
      vjust = -0.35,
      size = 3.4,
      fontface = "bold",
      colour = "#2f2f2f"
    ) +
    scale_fill_manual(values = CHOCOLATE_PALETTE[-1], guide = "none") +
    scale_y_continuous(
      labels = label_comma(),
      expand = expansion(mult = c(0, 0.12))
    ) +
    labs(
      title = "(A) Grid cells by coverage context",
      x = NULL,
      y = "Grid cells"
    ) +
    map_theme() +
    theme(
      plot.subtitle = element_blank(),
      panel.grid.major.x = element_blank(),
      axis.text.x = element_text(size = 8.5, angle = 18, hjust = 1)
    )
}

build_matrix_panel <- function(matrix_long) {
  ggplot(
    matrix_long,
    aes(x = col_context, y = row_context, fill = pct_of_col)
  ) +
    geom_tile(colour = "white", linewidth = 1.0) +
    geom_text(aes(label = label), size = 3.6, fontface = "bold", colour = "#2f2f2f") +
    scale_fill_gradientn(
      colours = CHOCOLATE_PALETTE,
      limits = c(0, 100),
      name = "% of column\ncontext",
      labels = function(x) paste0(x, "%")
    ) +
    labs(
      title = "(B) Nested coverage matrix",
      x = "Column context (denominator)",
      y = "Row context (numerator)"
    ) +
    map_theme() +
    theme(
      plot.subtitle = element_blank(),
      panel.grid = element_blank(),
      axis.text.x = element_text(size = 8.5, angle = 18, hjust = 1),
      axis.text.y = element_text(size = 8.5),
      legend.position = "right"
    )
}

annotation_theme <- theme(
  plot.title = element_text(face = "bold", size = 15, hjust = 0.5, colour = "#2f2f2f"),
  plot.subtitle = element_blank(),
  plot.caption = element_text(size = 8.5, colour = "grey45", hjust = 0.5, margin = margin(t = 8))
)

message("Reading tables...")
counts <- read_cell_counts(CELL_COUNTS_CSV)
matrix_long <- read_matrix(MATRIX_CSV)

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

panel_counts <- build_count_panel(counts)
panel_matrix <- build_matrix_panel(matrix_long)

combined <- panel_counts + panel_matrix +
  plot_layout(widths = c(1.05, 1.35)) +
  plot_annotation(
    title = "100 m Grid Coverage in Nairobi",
    caption = FIGURE_CAPTION,
    theme = annotation_theme
  )

out_path <- file.path(FIG_DIR, "Grid_coverage_summary.png")
ggsave(out_path, combined, width = 14, height = 6.0, dpi = 600, bg = "white")
message("Wrote ", out_path)
message("Done.")

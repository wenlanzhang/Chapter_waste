#!/usr/bin/env Rscript
# Step 2, figure 0 — the coverage cascade on one frame.
#   0_Nairobi_grid_coverage_funnel.png
#     (a) cells surviving each narrowing, city -> road -> GSVI -> waste
#     (b) the nested matrix: for each pair, the share of the column context
#         that also satisfies the row context
#
# Blocks 2a-2e each measure one narrowing on whichever unit suits it. This puts
# the whole chain back on the 100 m cell so it reads end to end, and is the
# figure companion to table_0_coverage_headline.csv.
#
# Panel (b) earns its place on the off-diagonal. "Road-accessible given
# GSVI-observed" is 99.99%, not 100%: three observed cells are road-excluded.
# That near-miss is the check on the assumption that Street View follows mapped
# roads, and a perfectly nested chain would be the suspicious result.
#
# Inputs (2coverage_analysis/, from 0_grid_coverage_funnel.py):
#   0_Nairobi_grid_coverage_funnel.csv
#   0_Nairobi_grid_coverage_matrix.csv

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "2coverage_analysis")
FIG_DIR <- file.path(script_dir, "..", "Figure", "2coverage_analysis")

FUNNEL_CSV <- file.path(DATA_DIR, "0_Nairobi_grid_coverage_funnel.csv")
MATRIX_CSV <- file.path(DATA_DIR, "0_Nairobi_grid_coverage_matrix.csv")
OUT_PATH <- file.path(FIG_DIR, "0_Nairobi_grid_coverage_funnel.png")

for (f in c(FUNNEL_CSV, MATRIX_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 2coverage_analysis/0_grid_coverage_funnel.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

funnel <- read.csv(FUNNEL_CSV, stringsAsFactors = FALSE)
matrix_long <- read.csv(MATRIX_CSV, stringsAsFactors = FALSE)

LEVELS <- funnel$label
funnel <- funnel |> mutate(label = factor(label, levels = LEVELS))
n_city <- funnel$n_cells[funnel$context == "city"]

# 99.99% must not print as 100.0% — the near-miss is the point of panel (b).
fmt_pct <- function(x) {
  ifelse(x > 99.9 & x < 100, sprintf("%.2f%%", x), sprintf("%.1f%%", x))
}

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      legend.position = "none"
    )
}

# --- (a) the funnel -----------------------------------------------------------
p_funnel <- ggplot(funnel, aes(label, n_cells, fill = label)) +
  geom_col(width = 0.66) +
  geom_text(aes(label = sprintf("%s\n%.1f%% of city", comma(n_cells), pct_of_city)),
            vjust = -0.3, size = 3, lineheight = 0.95,
            fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_fill_manual(values = setNames(
    c("#E8DFD5", "#C9A27F", "#8B5A3C", "#4D2D18"), LEVELS
  )) +
  scale_y_continuous(limits = c(0, n_city * 1.20),
                     expand = expansion(mult = c(0, 0.02)), labels = comma) +
  labs(
    title = "(a) Cells surviving each narrowing",
    subtitle = sprintf(
      "Of %s urban 100 m cells | each bar is a subset of the one to its left",
      comma(n_city)
    ),
    x = NULL, y = "100 m cells"
  ) +
  base_theme() +
  theme(panel.grid.major.x = element_blank(),
        axis.text.x = element_text(angle = 18, hjust = 1))

# --- (b) the nested matrix ----------------------------------------------------
mat <- matrix_long |>
  mutate(
    row_label = factor(row_label, levels = rev(LEVELS)),
    col_label = factor(col_label, levels = LEVELS),
    diagonal = as.character(row_label) == as.character(col_label)
  )

p_matrix <- ggplot(mat, aes(col_label, row_label)) +
  geom_tile(aes(fill = pct), colour = "white", linewidth = 1) +
  geom_text(aes(label = fmt_pct(pct), colour = pct > 55),
            size = 3.1, fontface = "bold", show.legend = FALSE) +
  scale_fill_gradient(name = NULL, low = "#F7F2ED", high = "#4D2D18",
                      limits = c(0, 100), labels = label_percent(scale = 1)) +
  scale_colour_manual(values = c("FALSE" = "#4D2D18", "TRUE" = "white")) +
  scale_x_discrete(position = "top", expand = expansion(0)) +
  scale_y_discrete(expand = expansion(0)) +
  labs(
    title = "(b) Nested coverage matrix",
    subtitle = "Share of the column context that also satisfies the row context",
    x = "Denominator (column context)", y = "Numerator (row context)"
  ) +
  base_theme() +
  theme(
    panel.grid = element_blank(),
    legend.position = "right",
    legend.key.width = unit(0.32, "cm"),
    legend.key.height = unit(1.1, "cm"),
    legend.text = element_text(size = 7.8, colour = CHAPTER_AXIS_COLOUR)
  )

fig <- (p_funnel | p_matrix) +
  plot_layout(widths = c(1, 1.25)) +
  plot_annotation(
    title = "Coverage of Nairobi's 100 m grid: city → road → GSVI → waste",
    subtitle = sprintf(
      "%s urban cells | %s road-accessible | %s with GSVI imagery | %s with a waste-positive panorama",
      comma(n_city),
      comma(funnel$n_cells[funnel$context == "road"]),
      comma(funnel$n_cells[funnel$context == "svi"]),
      comma(funnel$n_cells[funnel$context == "waste"])
    ),
    caption = paste0(
      "Road-accessible = Step 2a's 50 m rule (intersects a mapped road, or lies within 50 m). Waste-positive = at least one waste-positive panorama in the cell.\n",
      "GSVI-observed uses Step 2's cell-assignment rule, which snaps points in grid slivers to the nearest cell within 100 m; lib/ideamaps.py does not snap and counts 22,672 (see the README).\n",
      "Three GSVI-observed cells are road-excluded, so 'road-accessible given GSVI-observed' is 99.99%, not 100% — the chain is very nearly, but not exactly, nested."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 12, height = 5.6, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

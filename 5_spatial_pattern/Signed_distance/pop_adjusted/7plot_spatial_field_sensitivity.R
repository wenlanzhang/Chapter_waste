#!/usr/bin/env Rscript
# Spatial-field sensitivity (R1.3 / R3.2), from 7_spatial_field_sensitivity.py.
#   (a) distance curve relative to 2 km, P(d) / P(2 km): MDP against MDPS
#       (MDP + thin-plate spatial field), 2 km block bootstrap 95% bands
#   (b) settlement edge ÷ 2 km contrast under each model, with ΔAIC for distance
# Curves are compared relative to 2 km because the field shares part of the
# distance signal, so the level of the MDPS curve is poorly identified.
# Output: Figure/5_spatial_pattern/Signed_distance/pop_adjusted[/subdir]/Spatial_field_sensitivity.png
# Optional: --data-subdir=worldpop_2020 (the manuscript sample)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

if (!identical(Sys.getlocale("LC_CTYPE"), "en_US.UTF-8")) {
  invisible(suppressWarnings(Sys.setlocale("LC_CTYPE", "en_US.UTF-8")))
}

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
repo_root <- normalizePath(file.path(script_dir, "..", "..", ".."))
trailing <- commandArgs(trailingOnly = TRUE)
hit <- grep("^--data-subdir=", trailing, value = TRUE)
data_subdir <- if (length(hit)) sub("^--data-subdir=", "", hit[[1]]) else "worldpop_2020"

source(file.path(repo_root, "R", "chapter_paths.R"))
source(file.path(repo_root, "R", "chapter_colours.R"))

SF_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance", "pop_adjusted",
                    data_subdir, "spatial_field")
FIG_DIR <- file.path(repo_root, "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted",
                     data_subdir)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

summ_path <- file.path(SF_DIR, "Nairobi_spatial_field_summary.csv")
curve_path <- file.path(SF_DIR, "Nairobi_spatial_field_curves.csv")
if (!file.exists(summ_path) || !file.exists(curve_path)) {
  stop("Missing outputs in ", SF_DIR, ". Run 7_spatial_field_sensitivity.py")
}
summ <- read.csv(summ_path, stringsAsFactors = FALSE)
cur <- read.csv(curve_path, stringsAsFactors = FALSE)

AXIS <- CHAPTER_AXIS_COLOUR
base_theme <- theme_classic(base_size = 10) +
  theme(
    plot.title = element_text(colour = AXIS, face = "bold", size = 10),
    plot.subtitle = element_text(colour = AXIS, size = 8),
    plot.caption = element_text(colour = AXIS, size = 7.5, hjust = 0, lineheight = 1.1),
    axis.title = element_text(colour = AXIS, size = 9),
    axis.text = element_text(colour = AXIS, size = 8),
    axis.line = element_line(colour = AXIS, linewidth = 0.4),
    axis.ticks = element_line(colour = AXIS, linewidth = 0.35),
    legend.text = element_text(colour = AXIS, size = 8),
    plot.margin = margin(6, 10, 6, 6)
  )

model_lab <- c(
  MDP = "MDP: distance + population + year",
  MDPS = "MDPS: MDP + spatial field"
)
model_col <- setNames(c(WASTE_COLOUR, SLUM_FILL), model_lab)
cur$model_lab <- factor(model_lab[cur$model], levels = model_lab)
summ$model_lab <- factor(model_lab[summ$model], levels = model_lab)
MAX_M <- 5000
shown <- filter(cur, signed_distance_m <= MAX_M)
y_breaks <- c(0.25, 0.5, 1, 2, 4, 8)

# ---------------------------------------------------------------- (a) relative curve
p_a <- ggplot(shown, aes(signed_distance_m, rel_to_2km, colour = model_lab, fill = model_lab)) +
  geom_hline(yintercept = 1, colour = "#BDBDBD", linewidth = 0.3) +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35) +
  geom_ribbon(aes(ymin = rel_lo, ymax = rel_hi), alpha = 0.18, colour = NA) +
  geom_line(linewidth = 0.8) +
  scale_colour_manual(values = model_col, name = NULL) +
  scale_fill_manual(values = model_col, name = NULL) +
  scale_x_continuous(labels = comma, breaks = seq(0, MAX_M, 1000)) +
  scale_y_log10(breaks = y_breaks, labels = function(x) paste0(x, "×")) +
  coord_cartesian(ylim = range(c(shown$rel_lo, shown$rel_hi, y_breaks[2:5]))) +
  labs(
    title = "(a) Distance curve relative to 2 km",
    subtitle = "Adjusted P(waste-positive) at each distance ÷ at 2 km; log scale; shown to 5 km",
    x = "Signed distance to settlement (m; negative = inside)",
    y = "Relative to 2 km outside"
  ) +
  base_theme +
  theme(legend.position = c(0.68, 0.88))

# ---------------------------------------------------------------- (b) contrast
summ <- summ %>%
  mutate(lab = sprintf("%.2f (%.2f–%.2f)\nΔAIC for distance = %s",
                       edge_vs_2km, edge_vs_2km_lo, edge_vs_2km_hi,
                       comma(round(delta_aic_distance))))
p_b <- ggplot(summ, aes(edge_vs_2km, model_lab, colour = model_lab)) +
  geom_vline(xintercept = 1, colour = "#9C9C9C", linewidth = 0.4) +
  geom_errorbar(aes(xmin = edge_vs_2km_lo, xmax = edge_vs_2km_hi), width = 0.18,
                linewidth = 0.55, orientation = "y") +
  geom_point(size = 2.2) +
  geom_text(aes(label = lab), vjust = -0.75, size = 2.7, colour = AXIS, lineheight = 0.95) +
  scale_colour_manual(values = model_col, guide = "none") +
  scale_x_log10(breaks = c(1, 2, 4, 8), labels = function(x) paste0(x, "×")) +
  scale_y_discrete(limits = rev(levels(summ$model_lab)), labels = c("MDPS", "MDP"),
                   expand = expansion(add = c(0.6, 0.9))) +
  labs(
    title = "(b) Settlement edge ÷ 2 km",
    subtitle = "Point estimate and 95% interval; grey line = no gradient",
    x = "Adjusted P(waste) at the edge ÷ at 2 km", y = NULL
  ) +
  base_theme

caption <- paste(strwrap(sprintf(paste(
  "MDPS adds a thin-plate spatial field on panorama location to MDP. Its curve is averaged with every",
  "panorama keeping its own population, capture year and location. Curves are shown relative to 2 km",
  "because the field shares part of the distance signal, which leaves the level of the MDPS curve poorly",
  "identified but not its shape. Bands and intervals: 2.5th–97.5th percentiles over %d spatial block",
  "bootstrap draws (%s km blocks, random grid offset), both models refitted on each draw."
), summ$n_boot[1], format(summ$block_m[1] / 1000, trim = TRUE)), 185), collapse = "\n")

fig <- (p_a | p_b) +
  plot_layout(widths = c(1.6, 1)) +
  plot_annotation(caption = caption, theme = base_theme)

out <- file.path(FIG_DIR, "Spatial_field_sensitivity.png")
if (requireNamespace("ragg", quietly = TRUE)) {
  ggsave(out, fig, width = 10, height = 4.8, dpi = 300, bg = "white", device = ragg::agg_png)
} else {
  ggsave(out, fig, width = 10, height = 4.8, dpi = 300, bg = "white")
}
message("Wrote ", out)

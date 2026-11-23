#!/usr/bin/env Rscript
# Positional uncertainty near settlement boundaries (R1.4), from 5_boundary_exclusion.py.
#   (a) inside / outside prevalence ratio after excluding panoramas within d m of a
#       mapped boundary, with 2 km spatial block bootstrap 95% intervals
#   (b) MDP signed-distance curve refitted on each reduced sample (excluded band greyed)
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

POP_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance", "pop_adjusted")
FIG_DIR <- file.path(repo_root, "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted")
if (nzchar(data_subdir)) {
  POP_DIR <- file.path(POP_DIR, data_subdir)
  FIG_DIR <- file.path(FIG_DIR, data_subdir)
}
BE_DIR <- file.path(POP_DIR, "boundary_exclusion")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

summ_path <- file.path(BE_DIR, "Nairobi_boundary_exclusion_summary.csv")
curve_path <- file.path(BE_DIR, "Nairobi_boundary_exclusion_curves.csv")
if (!file.exists(summ_path) || !file.exists(curve_path)) {
  stop("Missing boundary-exclusion outputs in ", BE_DIR, ". Run 5_boundary_exclusion.py",
       if (nzchar(data_subdir)) paste0(" --data-subdir ", data_subdir) else "")
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
    legend.title = element_text(colour = AXIS, size = 8.5),
    plot.margin = margin(6, 10, 6, 6)
  )

lab <- function(d) ifelse(d == 0, "None", paste0("±", d, " m"))
levels_ex <- lab(sort(unique(summ$exclusion_m)))
pal <- setNames(c("#1F120C", colorRampPalette(c(CHAPTER_SEQ_MID, SLUM_FILL))(length(levels_ex) - 1)),
                levels_ex)

# ---------------------------------------------------------------- (a) ratio
sa <- summ %>%
  mutate(ex = factor(lab(exclusion_m), levels = levels_ex),
         counts = sprintf("inside %s (%s waste+)\noutside %s (%s waste+)",
                          comma(n_inside), comma(n_positive_inside),
                          comma(n_outside), comma(n_positive_outside)))
p_a <- ggplot(sa, aes(ex, prevalence_ratio, colour = ex)) +
  geom_hline(yintercept = sa$prevalence_ratio[sa$exclusion_m == 0], colour = "#BDBDBD", linewidth = 0.3) +
  geom_hline(yintercept = 1, colour = "#BDBDBD", linewidth = 0.3, linetype = "dashed") +
  geom_errorbar(aes(ymin = prevalence_ratio_lo, ymax = prevalence_ratio_hi), width = 0.18, linewidth = 0.5) +
  geom_point(size = 2.2) +
  geom_text(aes(y = prevalence_ratio_hi, label = sprintf("%.2f\n(%.2f–%.2f)", prevalence_ratio,
                                                          prevalence_ratio_lo, prevalence_ratio_hi)),
            vjust = -0.25, size = 2.5, colour = AXIS, lineheight = 0.9) +
  scale_colour_manual(values = pal, guide = "none") +
  scale_x_discrete(labels = setNames(sprintf("%s\nin %s / %s\nout %s / %s",
                                             as.character(sa$ex), comma(sa$n_inside),
                                             comma(sa$n_positive_inside), comma(sa$n_outside),
                                             comma(sa$n_positive_outside)),
                                     as.character(sa$ex))) +
  scale_y_continuous(limits = c(0, NA), expand = expansion(mult = c(0, 0.18))) +
  labs(title = "(a) Inside / outside prevalence ratio",
       subtitle = "Panoramas within the band of a mapped boundary removed (positives and negatives)",
       x = "Excluded band around settlement boundaries (panoramas / waste-positive kept)",
       y = "Prevalence ratio") +
  base_theme +
  theme(axis.text.x = element_text(size = 7.5, lineheight = 0.95))

# ---------------------------------------------------------------- (b) curves
cb <- cur %>%
  mutate(ex = factor(lab(exclusion_m), levels = levels_ex),
         prob = ifelse(in_excluded_band, NA, prob))
max_band <- max(summ$exclusion_m)
p_b <- ggplot(cb, aes(signed_distance_m, prob, colour = ex)) +
  annotate("rect", xmin = -max_band, xmax = max_band, ymin = -Inf, ymax = Inf,
           fill = "#EDEAE6", colour = NA) +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35) +
  geom_line(linewidth = 0.75, na.rm = TRUE) +
  scale_colour_manual(values = pal, name = "Excluded band") +
  scale_x_continuous(labels = comma, breaks = seq(0, 5000, 1000)) +
  scale_y_continuous(breaks = seq(0, 0.12, 0.02), labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.04))) +
  coord_cartesian(xlim = c(min(cb$signed_distance_m), 5000), ylim = c(0, NA)) +
  labs(title = "(b) Adjusted signed-distance curve",
       subtitle = sprintf("MDP refitted on each reduced sample; shaded = widest band (±%d m), lines omitted inside each band",
                          max_band),
       x = "Signed distance to settlement (m; negative = inside)", y = "Predicted P(waste-positive)") +
  base_theme +
  theme(legend.position = c(0.82, 0.70))

caption <- paste(strwrap(sprintf(paste(
  "Intervals: 2.5th–97.5th percentiles over %d spatial block bootstrap draws (2 km blocks, random grid offset).",
  "Removing near-boundary panoramas tests sensitivity to boundary and camera-position uncertainty;",
  "it does not identify where the photographed waste is."
), max(summ$n_boot_ratio)), 190), collapse = "\n")

fig <- (p_a | p_b) + plot_layout(widths = c(1.15, 1.2)) +
  plot_annotation(caption = caption, theme = base_theme)

out <- file.path(FIG_DIR, "Boundary_exclusion_sensitivity.png")
if (requireNamespace("ragg", quietly = TRUE)) {
  ggsave(out, fig, width = 11, height = 4.8, dpi = 300, bg = "white", device = ragg::agg_png)
} else {
  ggsave(out, fig, width = 11, height = 4.8, dpi = 300, bg = "white")
}
message("Wrote ", out)

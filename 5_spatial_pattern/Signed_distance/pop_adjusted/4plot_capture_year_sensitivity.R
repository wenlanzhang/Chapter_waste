#!/usr/bin/env Rscript
# Capture-year treatment and imagery-period sensitivity (R1 minor / R3.3),
# from 4_capture_year_sensitivity.py.
#   (a) MDP distance curve: main grouping (2015 → 2017, 2019 → 2018) vs 2015/2019 excluded
#   (b) MDP distance curve: early (2017–2018) vs late (2021–2022) imagery
#   (c) prevalence ratio and edge ÷ 2 km contrast by specification
# Bands and intervals: 2 km spatial block bootstrap, 2.5th–97.5th percentiles.
# Optional: --data-subdir=worldpop_2020 (the manuscript sample)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
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
CY_DIR <- file.path(POP_DIR, "capture_year")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

summ_path <- file.path(CY_DIR, "Nairobi_capture_year_summary.csv")
curve_path <- file.path(CY_DIR, "Nairobi_capture_year_curves.csv")
if (!file.exists(summ_path) || !file.exists(curve_path)) {
  stop("Missing capture-year outputs in ", CY_DIR, ". Run 4_capture_year_sensitivity.py",
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
    legend.key.width = unit(16, "pt"),
    plot.margin = margin(6, 10, 6, 6)
  )

short <- c(
  original = "Main (2015 → 2017, 2019 → 2018)",
  exclude_2015_2019 = "2015 and 2019 excluded",
  early_2017_2018 = "Early imagery, 2017–2018",
  late_2021_2022 = "Late imagery, 2021–2022"
)
cols <- c(
  "Main (2015 → 2017, 2019 → 2018)" = "#1F120C",
  "2015 and 2019 excluded" = GSVI_COLOUR,
  "Early imagery, 2017–2018" = WASTE_COLOUR,
  "Late imagery, 2021–2022" = SLUM_FILL
)
cur$name <- factor(short[cur$spec], levels = short)
summ$name <- factor(short[summ$spec], levels = short)
n_lab <- setNames(sprintf("n = %s", comma(summ$n_panoramas)), as.character(summ$name))

curve_panel <- function(keys, title, subtitle, bands) {
  d <- filter(cur, spec %in% keys)
  # Scale the y-axis to what is drawn (to 5 km). The bands widen in the sparse
  # tail beyond that and would otherwise stretch the axis over empty space.
  seen <- filter(d, signed_distance_m <= 5000)
  y_top <- max(seen$prob, if (bands) seen$prob_hi else NA_real_, na.rm = TRUE)
  p <- ggplot(d, aes(signed_distance_m, prob, colour = name, fill = name, linetype = name)) +
    geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35)
  if (bands) {
    p <- p + geom_ribbon(aes(ymin = prob_lo, ymax = prob_hi), alpha = 0.18, colour = NA)
  }
  p +
    geom_line(linewidth = 0.8) +
    scale_colour_manual(values = cols, labels = function(x) paste0(x, " (", n_lab[x], ")"), name = NULL) +
    scale_fill_manual(values = cols, guide = "none") +
    scale_linetype_manual(values = c("solid", "22", "solid", "solid") |> setNames(short), guide = "none") +
    scale_x_continuous(labels = comma, breaks = seq(0, 5000, 1000)) +
    scale_y_continuous(breaks = seq(0, 0.14, 0.02), labels = percent_format(accuracy = 1),
                       expand = expansion(mult = c(0, 0.04))) +
    coord_cartesian(xlim = c(min(d$signed_distance_m), 5000), ylim = c(0, y_top)) +
    labs(title = title, subtitle = subtitle,
         x = "Signed distance to settlement (m; negative = inside)",
         y = "Predicted P(waste-positive)") +
    base_theme +
    theme(legend.position = c(0.62, 0.82))
}

p_a <- curve_panel(c("original", "exclude_2015_2019"),
                   "(a) Grouping vs excluding 2015 and 2019",
                   "MDP, standardised over population and year", bands = FALSE)
p_b <- curve_panel(c("early_2017_2018", "late_2021_2022"),
                   "(b) Early vs late imagery",
                   "Each period fitted separately; band = 2 km block bootstrap 95%", bands = TRUE)

ci <- bind_rows(
  summ %>% transmute(name, measure = "Prevalence ratio, inside / outside settlements",
                     est = prevalence_ratio, lo = prevalence_ratio_lo, hi = prevalence_ratio_hi),
  summ %>% transmute(name, measure = "Adjusted P(waste), settlement edge ÷ 2 km",
                     est = curve_ratio_0m_vs_2000m, lo = curve_ratio_lo, hi = curve_ratio_hi)
) %>% mutate(name = factor(name, levels = rev(short)))

p_c <- ggplot(ci, aes(est, name, colour = name)) +
  geom_vline(xintercept = 1, colour = "#BDBDBD", linewidth = 0.3) +
  geom_errorbar(aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.5, orientation = "y") +
  geom_point(size = 1.9) +
  geom_text(aes(x = hi, label = sprintf("%.2f (%.2f–%.2f)", est, lo, hi)), hjust = -0.08,
            size = 2.5, colour = AXIS) +
  facet_wrap(~measure, nrow = 1, scales = "free_x") +
  scale_colour_manual(values = cols, guide = "none") +
  scale_x_continuous(limits = c(0, NA), expand = expansion(mult = c(0, 0.45))) +
  labs(title = "(c) Settlement contrast by specification",
       subtitle = "Point estimate and 2 km spatial block bootstrap 95% interval; grey line = no difference",
       x = NULL, y = NULL) +
  base_theme +
  theme(strip.background = element_blank(),
        strip.text = element_text(colour = AXIS, size = 8.5, face = "bold", hjust = 0))

n_boot <- max(summ$n_boot)
caption <- paste(strwrap(sprintf(paste(
  "Population: static WorldPop 2020, used as a common spatial reference, not matched to capture year.",
  "Bands and intervals: 2.5th–97.5th percentiles over %d spatial block bootstrap draws (2 km blocks, random grid offset)."
), n_boot), 190), collapse = "\n")

# wrap each row so the long row labels in (c) do not push panel (a) right
fig <- wrap_elements(full = p_a | p_b) / wrap_elements(full = p_c) +
  plot_layout(heights = c(1.15, 0.85)) +
  plot_annotation(caption = caption, theme = base_theme)

out <- file.path(FIG_DIR, "Capture_year_sensitivity.png")
if (requireNamespace("ragg", quietly = TRUE)) {
  ggsave(out, fig, width = 10.5, height = 7.4, dpi = 300, bg = "white", device = ragg::agg_png)
} else {
  ggsave(out, fig, width = 10.5, height = 7.4, dpi = 300, bg = "white")
}
message("Wrote ", out)

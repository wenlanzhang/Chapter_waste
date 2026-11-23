#!/usr/bin/env Rscript
# Spatial block bootstrap, from 3_spatial_block_bootstrap.py.
#   (a) residual correlogram of the MDP Pearson residuals, block sizes marked
#   (b) settlement prevalence ratio: 95% interval by method
#   (c) MDP signed-distance curve: panorama-level band vs 2 km and 4 km block bands
# Output: Figure/5_spatial_pattern/Signed_distance/pop_adjusted[/subdir]/Spatial_block_bootstrap.png
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
source(file.path(repo_root, "R", "pop_adjusted_paths.R"))
BB_DIR <- file.path(POP_DIR, "block_bootstrap")

need <- file.path(BB_DIR, c(
  "Nairobi_block_bootstrap_summary.csv",
  "Nairobi_block_bootstrap_curves.csv",
  "Nairobi_mdp_residual_correlogram.csv"
))
if (!all(file.exists(need))) {
  stop("Missing block-bootstrap outputs in ", BB_DIR,
       ". Run 3_spatial_block_bootstrap.py",
       " --data-subdir ", data_subdir)
}
summ <- read.csv(need[1], stringsAsFactors = FALSE)
curves <- read.csv(need[2], stringsAsFactors = FALSE)
corr <- read.csv(need[3], stringsAsFactors = FALSE)

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
    legend.title = element_text(colour = AXIS, size = 8.5),
    legend.text = element_text(colour = AXIS, size = 8),
    plot.margin = margin(6, 10, 6, 6)
  )

block_sizes <- sort(unique(summ$block_m[summ$scheme == "block"]))
largest <- max(block_sizes)
n_boot <- max(summ$n_reps[summ$scheme == "block"], na.rm = TRUE)

# ---------------------------------------------------------------- (a) correlogram
corr <- corr %>% mutate(mid = (dist_lo_m + dist_hi_m) / 2)
p_a <- ggplot(corr, aes(mid, residual_correlation)) +
  geom_hline(yintercept = 0, colour = "#BDBDBD", linewidth = 0.3) +
  geom_vline(xintercept = block_sizes, colour = SLUM_FILL, linetype = "dotted", linewidth = 0.4) +
  geom_line(colour = WASTE_COLOUR, linewidth = 0.6) +
  geom_point(colour = WASTE_COLOUR, size = 1.6) +
  scale_x_log10(breaks = c(25, 100, 250, 500, 1000, 2000, 4000), labels = comma) +
  labs(
    title = "(a) Residual correlation by distance",
    subtitle = "MDP Pearson residuals; dotted = block sizes tested",
    x = "Distance between panoramas (m, log scale)",
    y = "Residual correlation"
  ) +
  base_theme

# ---------------------------------------------------------------- (b) ratio intervals
method_label <- function(scheme, block_m) {
  ifelse(scheme == "analytic", "Analytic (independence)",
  ifelse(scheme == "iid", "Panorama bootstrap",
         paste0(comma(block_m), " m blocks")))
}
pr <- summ %>%
  filter(metric == "prevalence_ratio", scheme %in% c("analytic", "iid", "block")) %>%
  mutate(
    method = method_label(scheme, block_m),
    kind = ifelse(scheme == "block", "Spatial block bootstrap", "Assumes independence")
  )
pr$method <- factor(pr$method, levels = rev(pr$method))
p_b <- ggplot(pr, aes(estimate, method, colour = kind)) +
  geom_vline(xintercept = pr$estimate[1], colour = "#BDBDBD", linewidth = 0.3) +
  geom_errorbar(aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.5, orientation = "y") +
  geom_point(size = 1.8) +
  geom_text(aes(x = hi, label = sprintf("%.2f–%.2f", lo, hi)), hjust = -0.12,
            size = 2.6, colour = AXIS) +
  scale_colour_manual(values = c("Assumes independence" = "#9C9C9C",
                                 "Spatial block bootstrap" = WASTE_COLOUR), name = NULL) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.35))) +
  labs(
    title = "(b) Settlement prevalence ratio",
    subtitle = "Inside / outside; 95% interval by method",
    x = "Prevalence ratio", y = NULL
  ) +
  base_theme +
  theme(legend.position = "bottom")

# ---------------------------------------------------------------- (c) curve bands
# All bands are drawn around the same full-sample curve. The 2 km band is the
# one used for the main figure (Pop_adjusted_gam_effects.png, same replicates).
MAIN_BLOCK_M <- 2000
shown <- data.frame(
  scheme = c("iid", "block", "block"),
  block_m = c(0, MAIN_BLOCK_M, largest),
  band = c(
    "Panorama bootstrap (assumes independence)",
    paste0("Spatial block bootstrap, ", comma(MAIN_BLOCK_M), " m (main figure)"),
    paste0("Spatial block bootstrap, ", comma(largest), " m")
  )
)
shown <- shown[!duplicated(shown[c("scheme", "block_m")]), ]
cb <- inner_join(curves, shown, by = c("scheme", "block_m")) %>%
  mutate(band = factor(band, levels = rev(shown$band)))
fs <- filter(curves, scheme == "full_sample")
band_cols <- setNames(c("#4D4D4D", WASTE_COLOUR, GSVI_COLOUR)[seq_len(nrow(shown))], shown$band)
p_c <- ggplot() +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35) +
  # widest first, so the narrower bands sit on top
  geom_ribbon(data = arrange(cb, band),
              aes(signed_distance_m, ymin = prob_lo, ymax = prob_hi, fill = band),
              alpha = 0.45) +
  geom_line(data = fs, aes(signed_distance_m, prob), colour = "#1F120C", linewidth = 0.8) +
  scale_fill_manual(values = band_cols, breaks = shown$band, name = NULL) +
  scale_x_continuous(labels = comma, breaks = seq(0, 5000, 1000)) +
  scale_y_continuous(breaks = seq(0, 0.12, 0.02), labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.04))) +
  coord_cartesian(xlim = c(min(fs$signed_distance_m), 5000), ylim = c(0, NA)) +
  labs(
    title = "(c) Adjusted signed-distance curve",
    subtitle = "MDP, standardised over population and year; 95% bands around the same curve; shown to 5 km",
    x = "Signed distance to settlement (m; negative = inside)",
    y = "Predicted P(waste-positive)"
  ) +
  base_theme +
  theme(legend.position = c(0.68, 0.80))

caption <- paste(strwrap(sprintf(paste(
  "Spatial block bootstrap: square blocks with a random grid offset per draw; occupied blocks resampled",
  "with replacement and the GAM refitted (%d draws per block size). Intervals are 2.5th–97.5th bootstrap",
  "percentiles. The analytic interval and the panorama bootstrap treat panoramas as independent."
), n_boot), 185), collapse = "\n")

fig <- (p_a | p_b) / p_c +
  plot_layout(heights = c(1, 1.1)) +
  plot_annotation(caption = caption, theme = base_theme)

out <- file.path(FIG_DIR, "Spatial_block_bootstrap.png")
if (requireNamespace("ragg", quietly = TRUE)) {
  ggsave(out, fig, width = 9.5, height = 7.4, dpi = 300, bg = "white", device = ragg::agg_png)
} else {
  ggsave(out, fig, width = 9.5, height = 7.4, dpi = 300, bg = "white")
}
message("Wrote ", out)

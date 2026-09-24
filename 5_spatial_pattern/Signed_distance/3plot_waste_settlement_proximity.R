#!/usr/bin/env Rscript
# Step 5 — relationship between visible waste and urban-poor settlements.
#   Waste_settlement_proximity.png
#     (a) empirical waste-positive rate by distance band (no model)
#     (b) year-adjusted signed-distance GAM (the fitted version of the same thing)
#
# Panel (a) is the point of the figure: the gradient is visible in the raw
# counts, so the smooth in (b) is describing the data rather than imposing a
# shape on it. Both panels share a y-axis so they can be read against each other.
#
# Inputs (Signed_distance/):
#   Nairobi_proximity_rate_by_band.csv       (3_proximity_descriptives.py)
#   Nairobi_signed_distance_gam_curve.csv    (1_signed_distance_gam.py)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance")
BAND_CSV <- file.path(DATA_DIR, "Nairobi_proximity_rate_by_band.csv")
CURVE_CSV <- file.path(DATA_DIR, "Nairobi_signed_distance_gam_curve.csv")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "5_spatial_pattern", "Signed_distance")

for (f in c(BAND_CSV, CURVE_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 3_proximity_descriptives.py and 1_signed_distance_gam.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

bands <- read.csv(BAND_CSV, stringsAsFactors = FALSE) |>
  arrange(band_low_m) |>
  mutate(band = factor(band, levels = band))
curve <- read.csv(CURVE_CSV, stringsAsFactors = FALSE)

n_total <- sum(bands$n_panoramas)
n_pos <- sum(bands$n_waste_positive)
base_rate <- 100 * n_pos / n_total

# Both panels on one scale so the eye can move between them.
y_max <- max(bands$rate_ci95_high_pct, 100 * curve$prob_ci_high, na.rm = TRUE)

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      legend.position = "none"
    )
}

# --- (a) empirical rate by band ----------------------------------------------
p_bands <- ggplot(bands, aes(band, rate_pct)) +
  geom_hline(yintercept = base_rate, linetype = "22", colour = "grey55", linewidth = 0.4) +
  annotate("text", x = Inf, y = base_rate, label = sprintf("citywide %.1f%%", base_rate),
           hjust = 1.05, vjust = -0.6, size = 2.7, colour = "grey40") +
  geom_col(fill = WASTE_COLOUR, width = 0.68) +
  geom_errorbar(aes(ymin = rate_ci95_low_pct, ymax = rate_ci95_high_pct),
                width = 0.18, linewidth = 0.4, colour = "#3a3a3a") +
  geom_text(aes(label = sprintf("%.1f", rate_pct), y = rate_ci95_high_pct),
            vjust = -0.6, size = 2.7, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_y_continuous(limits = c(0, y_max * 1.12), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(a) Observed rate by distance band",
    subtitle = "Raw counts, no model | Wilson 95% CI",
    x = "Distance to nearest urban-poor settlement", y = "Waste-positive panoramas (%)"
  ) +
  base_theme() +
  theme(axis.text.x = element_text(angle = 30, hjust = 1), panel.grid.major.x = element_blank())

# --- (b) fitted GAM curve ----------------------------------------------------
p_curve <- ggplot(curve, aes(signed_distance_m, 100 * prob_waste_positive)) +
  geom_hline(yintercept = base_rate, linetype = "22", colour = "grey55", linewidth = 0.4) +
  geom_vline(xintercept = 0, linetype = "22", colour = SELF_COLLECTED_COLOUR, linewidth = 0.4) +
  geom_ribbon(aes(ymin = 100 * prob_ci_low, ymax = 100 * prob_ci_high),
              fill = WASTE_COLOUR, alpha = 0.18) +
  geom_line(colour = WASTE_COLOUR, linewidth = 1) +
  annotate("text", x = 0, y = y_max * 1.08, label = "settlement boundary",
           hjust = -0.06, size = 2.7, colour = SELF_COLLECTED_COLOUR) +
  scale_x_continuous(labels = label_comma(), limits = c(min(curve$signed_distance_m), 5000)) +
  scale_y_continuous(limits = c(0, y_max * 1.12), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(b) Year-adjusted signed-distance GAM",
    subtitle = "logit P(waste) = α + s(signed distance) + year | bootstrap 95% CI",
    x = "Signed distance (m; negative = inside a settlement)", y = NULL
  ) +
  base_theme()

fig <- (p_bands | p_curve) +
  plot_layout(widths = c(1, 1.1)) +
  plot_annotation(
    title = "Visible waste and urban-poor settlements",
    subtitle = sprintf(
      "Nairobi | %s GSVI panoramas, %s waste-positive (%.1f%%) | panorama unit",
      comma(n_total), comma(n_pos), base_rate
    ),
    caption = paste0(
      "Panel (a) is the gradient in the raw data; panel (b) is the same relationship fitted as a smooth and adjusted for capture year.\n",
      "The x-axis in (b) is truncated at 5 km for readability; the model is estimated over the full range. ",
      "Dashed horizontal line = citywide waste-positive rate."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

out <- file.path(FIG_DIR, "Waste_settlement_proximity.png")
ggsave(out, fig, width = 11.5, height = 5.4, dpi = 400, bg = "white")
message("Wrote ", out)
message("Done.")

#!/usr/bin/env Rscript
# Step 6.4c — does the distance gradient survive self-collected imagery?
#   1_SC_gam_comparison.png
#     (a) observed waste-positive rate by distance band, both arms (no model)
#     (b) the year-adjusted signed-distance GAM curve, both arms
#
# Panel (a) first, deliberately: if the raw band rates are unchanged, the fitted
# curves in (b) cannot be doing anything the data does not already say.
#
# Inputs (6_selfcollected/4_pattern/Signed_distance/, from 1_sc_signed_distance_gam.py):
#   1_Nairobi_sc_rate_by_band.csv
#   1_Nairobi_sc_gam_curve.csv
#   thesis_table/table_6_4_gam_comparison.csv

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "4_pattern", "Signed_distance")
FIG_DIR <- file.path(script_dir, "../../..", "Figure", "6_selfcollected", "4_pattern", "Signed_distance")

BAND_CSV <- file.path(DATA_DIR, "1_Nairobi_sc_rate_by_band.csv")
CURVE_CSV <- file.path(DATA_DIR, "1_Nairobi_sc_gam_curve.csv")
TABLE_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_gam_comparison.csv")
OUT_PATH <- file.path(FIG_DIR, "1_SC_gam_comparison.png")

ARM_COLOURS <- c("GSVI" = "#BDB3A8", "GSVI + SC" = "#6B4226")
ARM_LEVELS <- c("GSVI", "GSVI + SC")

for (f in c(BAND_CSV, CURVE_CSV, TABLE_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f,
         " — run 6_selfcollected/4_pattern/Signed_distance/1_sc_signed_distance_gam.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

arm_factor <- function(x) factor(if_else(x == "gsvi", "GSVI", "GSVI + SC"), levels = ARM_LEVELS)

bands <- read.csv(BAND_CSV, stringsAsFactors = FALSE) |>
  arrange(band_low_m) |>
  mutate(Arm = arm_factor(arm), band = factor(band, levels = unique(band)))
curve <- read.csv(CURVE_CSV, stringsAsFactors = FALSE) |>
  mutate(Arm = arm_factor(arm)) |>
  filter(signed_distance_m <= 5000)
tbl <- read.csv(TABLE_CSV, stringsAsFactors = FALSE, check.names = FALSE)

get_row <- function(measure, col) tbl[[col]][tbl$Measure == measure]

y_max <- max(bands$rate_ci95_high_pct, 100 * curve$prob_waste_positive)

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      legend.position = "bottom"
    )
}

# --- (a) observed rate by band ------------------------------------------------
p_bands <- ggplot(bands, aes(band, rate_pct, fill = Arm)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.64) +
  geom_errorbar(aes(ymin = rate_ci95_low_pct, ymax = rate_ci95_high_pct),
                position = position_dodge(width = 0.72), width = 0.16,
                linewidth = 0.35, colour = "#3a3a3a") +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, y_max * 1.1), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(a) Observed rate by distance band",
    subtitle = "Raw counts, no model | Wilson 95% CI",
    x = "Distance to nearest urban-poor settlement", y = "Waste-positive locations (%)"
  ) +
  base_theme() +
  theme(axis.text.x = element_text(angle = 30, hjust = 1), panel.grid.major.x = element_blank())

# --- (b) fitted curves --------------------------------------------------------
p_curve <- ggplot(curve, aes(signed_distance_m, 100 * prob_waste_positive, colour = Arm)) +
  geom_vline(xintercept = 0, linetype = "22", colour = "grey55", linewidth = 0.4) +
  geom_line(linewidth = 1) +
  annotate("text", x = 0, y = y_max * 1.05, label = "settlement boundary",
           hjust = -0.06, size = 2.7, colour = "grey40") +
  scale_colour_manual(name = NULL, values = ARM_COLOURS) +
  scale_x_continuous(labels = label_comma()) +
  scale_y_continuous(limits = c(0, y_max * 1.1), expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(b) Year-adjusted signed-distance GAM",
    subtitle = sprintf("Pseudo-R² %s → %s | LRT vs year-only χ² %s → %s",
                       get_row("Pseudo-R², year + s(distance)", "GSVI"),
                       get_row("Pseudo-R², year + s(distance)", "GSVI + SC"),
                       get_row("LRT vs year-only, χ² (df)", "GSVI"),
                       get_row("LRT vs year-only, χ² (df)", "GSVI + SC")),
    x = "Signed distance (m; negative = inside a settlement)", y = NULL
  ) +
  base_theme()

fig <- (p_bands | p_curve) +
  plot_layout(widths = c(1, 1.1)) +
  plot_annotation(
    title = "The distance gradient, with and without self-collected imagery",
    subtitle = sprintf(
      "%s → %s observation locations | %s → %s waste-positive | identical spline specification and year fixed effect",
      get_row("Observation locations", "GSVI"), get_row("Observation locations", "GSVI + SC"),
      get_row("Waste-positive", "GSVI"), get_row("Waste-positive", "GSVI + SC")
    ),
    caption = paste0(
      "The x-axis in (b) is truncated at 5 km for readability; both models are estimated over the full range. The combined frame gains 2015, 2016 and 2023 year levels.\n",
      "Every band beyond the settlement boundary is unchanged to within 0.1 pp, so the gradient is not an artefact of where Street View drove. ",
      "Only the inside-settlement bar moves, and it moves partly by construction."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 12, height = 5.6, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

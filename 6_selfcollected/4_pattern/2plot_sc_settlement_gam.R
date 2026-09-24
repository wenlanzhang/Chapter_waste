#!/usr/bin/env Rscript
# Step 6.4b/c — does the settlement result survive self-collected imagery?
#   2_SC_settlement_gam_comparison.png
#     (a) waste-positive rate inside vs outside settlements, both arms
#     (b) the year-adjusted signed-distance GAM curve, both arms
#
# The two panels answer the same question at different resolutions. If the
# outside rate is unchanged and the curves lie on top of each other, the
# settlement gradient is not an artefact of where Street View happened to drive.
#
# Inputs (6_selfcollected/4_pattern/, from 2_sc_settlement_gam.py):
#   2_sc_settlement_contingency.csv
#   2_Nairobi_sc_gam_curve.csv
#   thesis_table/table_6_4_{settlement,gam}_comparison.csv

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "4_pattern")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "4_pattern")

CONTINGENCY_CSV <- file.path(DATA_DIR, "2_sc_settlement_contingency.csv")
CURVE_CSV <- file.path(DATA_DIR, "2_Nairobi_sc_gam_curve.csv")
SETTLEMENT_TABLE <- file.path(DATA_DIR, "thesis_table", "table_6_4_settlement_comparison.csv")
GAM_TABLE <- file.path(DATA_DIR, "thesis_table", "table_6_4_gam_comparison.csv")
OUT_PATH <- file.path(FIG_DIR, "2_SC_settlement_gam_comparison.png")

ARM_COLOURS <- c("GSVI" = "#BDB3A8", "GSVI + SC" = "#6B4226")

for (f in c(CONTINGENCY_CSV, CURVE_CSV, SETTLEMENT_TABLE, GAM_TABLE)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 6_selfcollected/4_pattern/2_sc_settlement_gam.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cont <- read.csv(CONTINGENCY_CSV, stringsAsFactors = FALSE)
curve <- read.csv(CURVE_CSV, stringsAsFactors = FALSE)
set_tbl <- read.csv(SETTLEMENT_TABLE, stringsAsFactors = FALSE, check.names = FALSE)
gam_tbl <- read.csv(GAM_TABLE, stringsAsFactors = FALSE, check.names = FALSE)

get_row <- function(tbl, measure, col) tbl[[col]][tbl$Measure == measure]

# Wilson 95% CI on each rate, so the panels carry their own uncertainty.
wilson <- function(k, n, z = 1.96) {
  p <- k / n
  den <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / den
  margin <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / den
  c(low = max(0, centre - margin), high = min(1, centre + margin))
}

rates <- cont |>
  mutate(
    n = `Waste.positive` + `Non.positive`,
    rate_pct = 100 * `Waste.positive` / n,
    ci_low = 100 * mapply(function(k, nn) wilson(k, nn)["low"], `Waste.positive`, n),
    ci_high = 100 * mapply(function(k, nn) wilson(k, nn)["high"], `Waste.positive`, n),
    Zone = factor(Zone, levels = c("Inside settlement", "Outside settlement")),
    Arm = factor(Arm, levels = c("GSVI", "GSVI + SC"))
  )

# --- (a) rate inside vs outside ----------------------------------------------
p_rates <- ggplot(rates, aes(Zone, rate_pct, fill = Arm)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.6) +
  geom_errorbar(aes(ymin = ci_low, ymax = ci_high),
                position = position_dodge(width = 0.7), width = 0.14,
                linewidth = 0.4, colour = "#3a3a3a") +
  geom_text(aes(label = sprintf("%.1f%%", rate_pct), y = ci_high),
            position = position_dodge(width = 0.7), vjust = -0.6,
            size = 3, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, max(rates$ci_high) * 1.16),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(a) Waste-positive rate by zone",
    subtitle = sprintf(
      "Prevalence ratio %s → %s | Wilson 95%% CI",
      get_row(set_tbl, "Prevalence ratio (inside / outside)", "GSVI"),
      get_row(set_tbl, "Prevalence ratio (inside / outside)", "GSVI + SC")
    ),
    x = NULL, y = "Waste-positive locations (%)"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 9, colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_blank(),
    legend.position = "bottom"
  )

# --- (b) the two fitted curves ------------------------------------------------
curve_plot <- curve |>
  mutate(Arm = factor(
    if_else(arm == "gsvi", "GSVI", "GSVI + SC"),
    levels = c("GSVI", "GSVI + SC")
  )) |>
  filter(signed_distance_m <= 5000)

p_curve <- ggplot(curve_plot, aes(signed_distance_m, 100 * prob_waste_positive, colour = Arm)) +
  geom_vline(xintercept = 0, linetype = "22", colour = "grey55", linewidth = 0.4) +
  geom_line(linewidth = 1) +
  annotate("text", x = 0, y = max(100 * curve_plot$prob_waste_positive) * 1.04,
           label = "settlement boundary", hjust = -0.06, size = 2.7, colour = "grey40") +
  scale_colour_manual(name = NULL, values = ARM_COLOURS) +
  scale_x_continuous(labels = label_comma()) +
  scale_y_continuous(limits = c(0, max(100 * curve_plot$prob_waste_positive) * 1.12),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(b) Year-adjusted signed-distance GAM",
    subtitle = sprintf(
      "Pseudo-R² %s → %s | LRT vs year-only χ² %s → %s",
      get_row(gam_tbl, "Pseudo-R², year + s(distance)", "GSVI"),
      get_row(gam_tbl, "Pseudo-R², year + s(distance)", "GSVI + SC"),
      get_row(gam_tbl, "LRT vs year-only, χ² (df)", "GSVI"),
      get_row(gam_tbl, "LRT vs year-only, χ² (df)", "GSVI + SC")
    ),
    x = "Signed distance (m; negative = inside a settlement)",
    y = "P(waste-positive) (%)"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank(),
    legend.position = "bottom"
  )

fig <- (p_rates | p_curve) +
  plot_layout(widths = c(1, 1.25)) +
  plot_annotation(
    title = "The settlement association, with and without self-collected imagery",
    subtitle = sprintf(
      "%s → %s observation locations | %s → %s waste-positive",
      get_row(gam_tbl, "Locations", "GSVI"), get_row(gam_tbl, "Locations", "GSVI + SC"),
      get_row(gam_tbl, "Waste-positive", "GSVI"), get_row(gam_tbl, "Waste-positive", "GSVI + SC")
    ),
    caption = paste0(
      "Both arms use the same settlement polygons, the same spline specification and a year fixed effect; the combined frame gains 2015, 2016 and 2023 year levels.\n",
      "The rate outside settlements is unchanged and the curves lie close together, so the gradient is not an artefact of where Street View drove.\n",
      "The inside rate rises partly by construction: self-collected imagery was gathered near settlements on purpose."
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

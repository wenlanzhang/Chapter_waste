#!/usr/bin/env Rscript
# Experiment 5: temporal robustness — settlement prevalence ratio by year

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

DATA_ROOT <- "/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste"
SETTLE_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "settlement")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "settlement")

WASTE_COLOUR <- "#6B4226"
AXIS_COLOUR <- "#4D2D18"
INSIDE_COLOUR <- "#496142"
OUTSIDE_COLOUR <- "#A67B5B"

path <- file.path(SETTLE_DIR, "Nairobi_temporal_robustness_by_year.csv")
if (!file.exists(path)) {
  stop(
    "Missing temporal outputs. Run:\n",
    "  python 5_spatial_pattern/settlement/5_temporal_robustness.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
dat <- read.csv(path) %>%
  filter(year_period != "all", is.finite(prevalence_ratio), n_waste_positive > 0)

rate_long <- dat %>%
  transmute(
    year_period,
    n_panoids,
    Inside = positive_rate_inside,
    Outside = positive_rate_outside
  ) %>%
  tidyr::pivot_longer(c(Inside, Outside), names_to = "zone", values_to = "rate")

p_rates <- ggplot(rate_long, aes(x = year_period, y = rate, fill = zone)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.65) +
  scale_fill_manual(values = c(Inside = INSIDE_COLOUR, Outside = OUTSIDE_COLOUR)) +
  scale_y_continuous(labels = percent_format(accuracy = 0.1)) +
  labs(
    title = "Temporal robustness: waste-positive rate by year",
    subtitle = "Denominators = GSVI panoramas in each year × zone",
    x = "Capture year",
    y = "P(waste-positive panorama)",
    fill = NULL
  ) +
  theme_classic(base_size = 12) +
  theme(
    plot.title = element_text(colour = AXIS_COLOUR, face = "bold"),
    legend.position = "bottom"
  )

ggsave(
  file.path(FIG_DIR, "Temporal_waste_positive_rate_by_year.png"),
  p_rates,
  width = 8.5,
  height = 5.0,
  dpi = 300
)

p_pr <- ggplot(dat, aes(x = year_period, y = prevalence_ratio)) +
  geom_hline(yintercept = 1, linetype = "dashed", colour = "#8C7355") +
  geom_col(fill = WASTE_COLOUR, width = 0.65) +
  labs(
    title = "Temporal robustness: prevalence ratio (inside / outside)",
    subtitle = "Panorama unit; rare years pooled as 'other' when n < 200",
    x = "Capture year",
    y = "Prevalence ratio"
  ) +
  theme_classic(base_size = 12) +
  theme(plot.title = element_text(colour = AXIS_COLOUR, face = "bold"))

ggsave(
  file.path(FIG_DIR, "Temporal_prevalence_ratio_by_year.png"),
  p_pr,
  width = 8.0,
  height = 4.8,
  dpi = 300
)

message("Wrote Temporal_waste_positive_rate_by_year.png")
message("Wrote Temporal_prevalence_ratio_by_year.png")

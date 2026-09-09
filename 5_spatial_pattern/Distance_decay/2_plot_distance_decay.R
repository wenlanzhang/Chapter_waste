#!/usr/bin/env Rscript
# Distance-decay figures: ECDF (positive vs non+) and NegExp fits

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
DECAY_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "Distance_decay")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "Distance_decay")

WASTE_COLOUR <- "#6B4226"
GSVI_COLOUR <- "#C9A27F"

cdf_path <- file.path(DECAY_DIR, "Nairobi_distance_decay_cdf.csv")
negexp_path <- file.path(DECAY_DIR, "Nairobi_negexp_params.csv")
ks_path <- file.path(DECAY_DIR, "Nairobi_ks_distance.csv")

required <- c(cdf_path, negexp_path)
missing <- required[!file.exists(required)]
if (length(missing)) {
  stop(
    "Missing distance-decay outputs. Run:\n",
    "  python 5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py\n",
    paste(missing, collapse = "\n")
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cdf <- read.csv(cdf_path)
negexp <- read.csv(negexp_path)

theme_chapter <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "sans") +
    theme(
      plot.title = element_text(face = "bold", hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(hjust = 0.5, colour = "#5C6B7A"),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      legend.title = element_blank()
    )
}

# --- Main ECDF: positive vs non-positive panoramas ---
has_nonpos <- "emp_non_positive" %in% names(cdf)
if (has_nonpos) {
  ecdf_long <- bind_rows(
    cdf |>
      transmute(
        distance_m,
        share = emp_waste_positive,
        series = "Waste-positive panoramas"
      ),
    cdf |>
      transmute(
        distance_m,
        share = emp_non_positive,
        series = "Non-positive panoramas"
      )
  )

  ks_sub <- if (file.exists(ks_path)) {
    ks <- read.csv(ks_path)
    p_txt <- if (isTRUE(ks$p_value[1] < 0.001)) {
      "< 0.001"
    } else {
      sprintf("= %.4g", ks$p_value[1])
    }
    sprintf("Two-sample KS D = %.3f | p %s", ks$ks_statistic_D[1], p_txt)
  } else {
    "Panorama-level distances to nearest mapped urban-poor settlement"
  }

  p_ecdf <- ggplot(ecdf_long, aes(x = distance_m, y = share, colour = series)) +
    geom_vline(xintercept = 500, linetype = "dashed", colour = "#8A8A8A", linewidth = 0.45) +
    geom_line(linewidth = 0.95) +
    scale_colour_manual(
      values = c(
        "Waste-positive panoramas" = WASTE_COLOUR,
        "Non-positive panoramas" = GSVI_COLOUR
      )
    ) +
    scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 1)) +
    scale_x_continuous(labels = comma, limits = c(0, 3000)) +
    labs(
      title = "Distance to Urban-Poor Settlements",
      subtitle = ks_sub,
      x = "Distance to nearest mapped urban-poor settlement (m)",
      y = "Cumulative share of panoramas"
    ) +
    theme_chapter()

  ggsave(
    file.path(FIG_DIR, "Distance_ecdf.png"),
    p_ecdf,
    width = 9,
    height = 5.5,
    dpi = 600,
    bg = "white"
  )
  message("Wrote ", file.path(FIG_DIR, "Distance_ecdf.png"))
}

# --- NegExp fits vs all GSVI ---
decay_long <- bind_rows(
  cdf |>
    transmute(
      distance_m,
      share = emp_waste_positive,
      series = "Waste-positive panoids (empirical)"
    ),
  cdf |>
    transmute(
      distance_m,
      share = emp_all_gsvi,
      series = "All GSVI panoids (empirical)"
    ),
  cdf |>
    transmute(
      distance_m,
      share = fit_waste_positive,
      series = "Waste-positive NegExp fit"
    ),
  cdf |>
    transmute(
      distance_m,
      share = fit_all_gsvi,
      series = "All GSVI NegExp fit"
    )
)

half_waste <- negexp$half_distance_m[negexp$series == "waste_positive"][1]
half_all <- negexp$half_distance_m[negexp$series == "all_gsvi"][1]

p_decay <- ggplot(decay_long, aes(x = distance_m, y = share, colour = series, linetype = series)) +
  geom_line(linewidth = 0.85) +
  scale_colour_manual(
    values = c(
      "Waste-positive panoids (empirical)" = WASTE_COLOUR,
      "All GSVI panoids (empirical)" = GSVI_COLOUR,
      "Waste-positive NegExp fit" = WASTE_COLOUR,
      "All GSVI NegExp fit" = GSVI_COLOUR
    )
  ) +
  scale_linetype_manual(
    values = c(
      "Waste-positive panoids (empirical)" = "solid",
      "All GSVI panoids (empirical)" = "solid",
      "Waste-positive NegExp fit" = "dashed",
      "All GSVI NegExp fit" = "dashed"
    )
  ) +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 1)) +
  scale_x_continuous(labels = comma) +
  labs(
    title = "Distance-Decay to Urban Poor Settlements",
    subtitle = sprintf(
      "NegExp half-distance: waste-positive = %s m | all GSVI = %s m",
      format(round(half_waste), big.mark = ","),
      format(round(half_all), big.mark = ",")
    ),
    x = "Distance to settlement (m)",
    y = "Cumulative share of panoids"
  ) +
  theme_chapter()

ggsave(
  file.path(FIG_DIR, "Distance_decay_negexp.png"),
  p_decay,
  width = 9,
  height = 5.5,
  dpi = 600,
  bg = "white"
)
message("Wrote ", file.path(FIG_DIR, "Distance_decay_negexp.png"))
message("Done.")

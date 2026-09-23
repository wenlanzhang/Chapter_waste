#!/usr/bin/env Rscript
# Two-panel supplementary figure: population-adjusted MDP effects
# (a) waste probability vs signed distance (standardised over pop + year)
# (b) waste probability vs population density (standardised over distance + year)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

# Rscript starts in the C locale, which mangles Δ / km²; quartz also drops them.
if (!identical(Sys.getlocale("LC_CTYPE"), "en_US.UTF-8")) {
  invisible(suppressWarnings(Sys.setlocale("LC_CTYPE", "en_US.UTF-8")))
}

save_png <- function(path, plot, width, height, dpi = 300) {
  if (requireNamespace("ragg", quietly = TRUE)) {
    ggsave(
      path, plot,
      width = width, height = height, dpi = dpi, bg = "white",
      device = ragg::agg_png
    )
  } else {
    ggsave(path, plot, width = width, height = height, dpi = dpi, bg = "white")
  }
}

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
# Optional trailing args: --data-subdir=worldpop_2020 --fig-subdir=worldpop_2020
#                        --pop-caption="..." --run-hint="python ..."
trailing <- commandArgs(trailingOnly = TRUE)
get_opt <- function(name, default = NULL) {
  hit <- grep(paste0("^--", name, "="), trailing, value = TRUE)
  if (length(hit)) sub(paste0("^--", name, "="), "", hit[[1]]) else default
}

data_subdir <- get_opt("data-subdir", "")
fig_subdir <- get_opt("fig-subdir", data_subdir)
pop_caption <- get_opt(
  "pop-caption",
  "WorldPop Constrained Kenya 2024 (100 m), used as a static density covariate (not matched to panorama year)."
)
run_hint <- get_opt(
  "run-hint",
  "python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py"
)

DATA_ROOT <- chapter_data_root
POP_DIR <- if (nzchar(data_subdir)) {
  file.path(DATA_ROOT, "5_spatial_pattern", "Signed_distance", "pop_adjusted", data_subdir)
} else {
  file.path(DATA_ROOT, "5_spatial_pattern", "Signed_distance", "pop_adjusted")
}
# Figure root is always repo Figure/5_spatial_pattern/pop_adjusted[/subdir]
fig_root <- normalizePath(
  file.path(script_dir, "..", "..", "..", "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted"),
  mustWork = FALSE
)
# If this script lives in worldpop_2020/, climb one extra level to repo Figure/
if (basename(normalizePath(script_dir)) == "worldpop_2020") {
  fig_root <- normalizePath(
    file.path(script_dir, "..", "..", "..", "..", "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted"),
    mustWork = FALSE
  )
}
FIG_DIR <- if (nzchar(fig_subdir)) {
  file.path(fig_root, fig_subdir)
} else {
  fig_root
}

WASTE_COLOUR <- "#6B4226"
GSVI_COLOUR <- "#C9A27F"
AXIS_COLOUR <- "#1F120C"

resolve_input <- function(filename) {
  candidates <- c(
    file.path(POP_DIR, filename),
    file.path(script_dir, filename)
  )
  for (p in candidates) {
    if (file.exists(p)) return(p)
  }
  candidates[[1]]
}

curve_d_path <- resolve_input("Nairobi_pop_adjusted_curve_distance.csv")
curve_p_path <- resolve_input("Nairobi_pop_adjusted_curve_population.csv")
frame_path <- resolve_input("Nairobi_pop_adjusted_gam_frame.csv")
summary_path <- resolve_input("Nairobi_pop_adjusted_summary.csv")

if (!file.exists(curve_d_path) || !file.exists(curve_p_path)) {
  stop("Missing MDP curves. Run:\n  ", run_hint)
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

curve_d <- read.csv(curve_d_path, stringsAsFactors = FALSE)
curve_p <- read.csv(curve_p_path, stringsAsFactors = FALSE)
frame <- if (file.exists(frame_path)) read.csv(frame_path, stringsAsFactors = FALSE) else NULL
summary <- if (file.exists(summary_path)) read.csv(summary_path, stringsAsFactors = FALSE) else NULL

has_ci_d <- all(c("prob_ci_low", "prob_ci_high") %in% names(curve_d)) &&
  any(is.finite(curve_d$prob_ci_low) & is.finite(curve_d$prob_ci_high))
has_ci_p <- all(c("prob_ci_low", "prob_ci_high") %in% names(curve_p)) &&
  any(is.finite(curve_p$prob_ci_low) & is.finite(curve_p$prob_ci_high))

subtitle_extra <- NULL
if (!is.null(summary) && "delta_aic_MP_minus_MDP" %in% names(summary)) {
  subtitle_extra <- sprintf(
    "Central test MP vs MDP: \u0394AIC = %.1f",
    summary$delta_aic_MP_minus_MDP[1]
  )
}

base_theme <- theme_classic(base_size = 11) +
  theme(
    plot.title = element_text(colour = AXIS_COLOUR, face = "bold", size = 11),
    plot.subtitle = element_text(colour = AXIS_COLOUR, size = 8.5),
    axis.title = element_text(colour = AXIS_COLOUR),
    axis.text = element_text(colour = AXIS_COLOUR),
    axis.line = element_line(colour = AXIS_COLOUR, linewidth = 0.45),
    axis.ticks = element_line(colour = AXIS_COLOUR, linewidth = 0.4),
    plot.margin = margin(8, 14, 8, 8)
  )

# Optional rugs
set.seed(42)
rug_d <- NULL
rug_p <- NULL
if (!is.null(frame)) {
  n_rug <- min(nrow(frame), 4000L)
  idx <- sample.int(nrow(frame), n_rug)
  if ("signed_distance_m" %in% names(frame)) {
    rug_d <- frame[idx, , drop = FALSE]
  }
  if ("pop_density_km2" %in% names(frame)) {
    rug_p <- frame[idx, , drop = FALSE]
  }
}

y_hi <- max(
  curve_d$prob_waste_positive,
  curve_p$prob_waste_positive,
  if (has_ci_d) curve_d$prob_ci_high else NA_real_,
  if (has_ci_p) curve_p$prob_ci_high else NA_real_,
  na.rm = TRUE
)
ylim <- c(0, max(y_hi, 0.075) * 1.10)
y_breaks <- c(0, 0.025, 0.05, 0.075)

p_a <- ggplot(curve_d, aes(x = signed_distance_m, y = prob_waste_positive)) +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.4)

if (has_ci_d) {
  p_a <- p_a +
    geom_ribbon(
      aes(ymin = prob_ci_low, ymax = prob_ci_high),
      fill = alpha(WASTE_COLOUR, 0.22),
      colour = NA
    )
}

p_a <- p_a +
  geom_line(colour = WASTE_COLOUR, linewidth = 1.0) +
  scale_x_continuous(
    labels = comma,
    breaks = c(0, 5000, 10000),
    expand = expansion(mult = c(0.04, 0.05))
  ) +
  scale_y_continuous(
    breaks = y_breaks,
    labels = percent_format(accuracy = 0.1),
    limits = ylim,
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(
    title = "(a) Adjusted effect of signed distance",
    subtitle = "Standardised over population density and capture year",
    x = "Signed distance to settlement (m)\n(negative = inside, positive = outside)",
    y = "Predicted P(waste-positive)"
  ) +
  base_theme

if (!is.null(rug_d)) {
  p_a <- p_a +
    geom_rug(
      data = rug_d,
      aes(x = signed_distance_m),
      inherit.aes = FALSE,
      colour = GSVI_COLOUR,
      alpha = 0.12,
      length = unit(0.03, "npc")
    )
}

# Panel b: use pop_density on a log-ish axis via log1p scale labels
p_b <- ggplot(curve_p, aes(x = pop_density_km2, y = prob_waste_positive))

if (has_ci_p) {
  p_b <- p_b +
    geom_ribbon(
      aes(ymin = prob_ci_low, ymax = prob_ci_high),
      fill = alpha(WASTE_COLOUR, 0.22),
      colour = NA
    )
}

p_b <- p_b +
  geom_line(colour = WASTE_COLOUR, linewidth = 1.0) +
  scale_x_continuous(
    trans = "log1p",
    breaks = c(100, 1000, 10000, 50000),
    labels = c("100", "1,000", "10,000", "50,000"),
    expand = expansion(mult = c(0.03, 0.08))
  ) +
  scale_y_continuous(
    breaks = y_breaks,
    labels = percent_format(accuracy = 0.1),
    limits = ylim,
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(
    title = "(b) Adjusted effect of population density",
    subtitle = "Standardised over signed distance and capture year",
    x = "WorldPop density (people / km\u00B2)",
    y = NULL
  ) +
  base_theme +
  theme(axis.text.x = element_text(colour = AXIS_COLOUR, size = 9))

if (!is.null(rug_p)) {
  p_b <- p_b +
    geom_rug(
      data = rug_p,
      aes(x = pop_density_km2),
      inherit.aes = FALSE,
      colour = GSVI_COLOUR,
      alpha = 0.12,
      length = unit(0.03, "npc")
    )
}

combined <- (p_a + p_b) +
  plot_annotation(
    title = "Population-adjusted signed-distance GAM (MDP)",
    subtitle = paste(
      c(
        "Panorama-level logistic GAM; bootstrap 95% CI",
        subtitle_extra
      ),
      collapse = "  |  "
    ),
    caption = paste0(
      pop_caption,
      " Shaded bands = bootstrap 95% CI."
    ),
    theme = theme(
      plot.title = element_text(colour = AXIS_COLOUR, face = "bold", size = 13),
      plot.subtitle = element_text(colour = AXIS_COLOUR, size = 9),
      plot.caption = element_text(colour = AXIS_COLOUR, size = 8, hjust = 0)
    )
  )

out <- file.path(FIG_DIR, "Pop_adjusted_gam_effects.png")
save_png(out, combined, width = 11.6, height = 5.4, dpi = 300)
message("Wrote ", out)

# Also save separate panels for flexible insertion
save_png(
  file.path(FIG_DIR, "Pop_adjusted_gam_distance.png"),
  p_a + labs(title = "Adjusted effect of signed distance (MDP)"),
  width = 6.2, height = 4.8, dpi = 300
)
save_png(
  file.path(FIG_DIR, "Pop_adjusted_gam_population.png"),
  p_b + labs(
    title = "Adjusted effect of population density (MDP)",
    y = "Predicted P(waste-positive)"
  ),
  width = 6.4, height = 4.8, dpi = 300
)
message("Wrote single-panel PNGs in ", FIG_DIR)

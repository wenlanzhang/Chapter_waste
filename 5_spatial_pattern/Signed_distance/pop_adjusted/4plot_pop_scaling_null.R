#!/usr/bin/env Rscript
# Step 5c sensitivity — the proportional-growth null for the population effect.
#   Pop_scaling_null.png
#     (a) linear probability against log density — the axes panel (b) of
#         Pop_adjusted_gam_effects.png uses
#     (b) log probability against log density — the diagnostic view
#
# Reads the fitted population curve against an explicit null: what if visible
# waste simply scaled with population? That means the probability a panorama
# shows waste is proportional to density, P = k * D, i.e. an elasticity
# dlog(P)/dlog(D) of exactly 1. On log-log axes that is a straight line of
# slope 1; the fitted curve's slope (computed below) is about 0.46 on the manuscript sample.
#
# The pairing is the point. Panel (b) is where the comparison can actually be
# read, because a constant elasticity is a straight line only on log-log axes.
# Panel (a) shows the same two curves on the axes the main figure uses, where
# the null accelerates off the panel and the gap is easy to misjudge.
#
# Sub-proportional growth means waste prevalence rises more slowly than
# population density. Read it with care: the outcome is a binary per-panorama
# indicator, so it saturates, and part of the shortfall from 1 may be that
# ceiling rather than less waste per person.
#
# Input (pop_adjusted/worldpop_2020/): Nairobi_pop_adjusted_curve_population.csv (1_pop_adjusted_gam.py)

suppressPackageStartupMessages({library(ggplot2); library(dplyr); library(scales); library(patchwork)})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../../..", "R", "chapter_colours.R"))

# Manuscript sample (WorldPop unconstrained 2020).
CURVE <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance",
                   "pop_adjusted", "worldpop_2020", "Nairobi_pop_adjusted_curve_population.csv")
if (!file.exists(CURVE)) {
  stop("Missing ", CURVE,
       "\nRun 5_spatial_pattern/Signed_distance/pop_adjusted/1_pop_adjusted_gam.py first")
}
obs <- read.csv(CURVE) |>
  filter(prob_waste_positive > 0, pop_density_km2 >= 1000, pop_density_km2 <= 70000)

# Anchor the proportional null on the observed curve at the low end, so the two
# agree where the data starts and the question is only how fast each grows.
anchor_d <- min(obs$pop_density_km2)
anchor_p <- obs$prob_waste_positive[which.min(obs$pop_density_km2)]
obs <- obs |> mutate(proportional = anchor_p * (pop_density_km2 / anchor_d))

# Elasticity = slope of log P on log density over the plotted range.
elasticity <- unname(coef(lm(log(prob_waste_positive) ~ log(pop_density_km2), data = obs))[2])
# Its interval comes from the spatial block bootstrap in 1_pop_adjusted_gam.py
# (same definition, same replicates as the band in Pop_adjusted_gam_effects.png).
SUMMARY <- file.path(dirname(CURVE), "Nairobi_pop_adjusted_summary.csv")
smry <- if (file.exists(SUMMARY)) read.csv(SUMMARY) else NULL
has_ci <- !is.null(smry) && all(c("pop_elasticity_ci_low", "pop_elasticity_ci_high") %in% names(smry))
ci_txt <- if (has_ci) {
  sprintf(" (95%% interval %.2f–%.2f)", smry$pop_elasticity_ci_low[1], smry$pop_elasticity_ci_high[1])
} else {
  ""
}
ci_note <- if (has_ci) {
  sprintf("The interval is from %s spatial block bootstrap draws (2 km blocks), allowing for residual spatial dependence.\n",
          sub(".*_B", "", smry$pop_elasticity_ci_method[1]))
} else {
  ""
}
LAB_FIT <- sprintf("Fitted (elasticity %.2f)", elasticity)
LAB_NULL <- "If waste scaled with population (elasticity 1)"

long <- bind_rows(
  obs |> transmute(pop_density_km2, p = prob_waste_positive, series = LAB_FIT),
  obs |> transmute(pop_density_km2, p = proportional,        series = LAB_NULL)
) |>
  mutate(series = factor(series, levels = c(LAB_NULL, LAB_FIT)))

# Green = the hypothetical null, brown = the fitted result, matching the
# convention used across Step 6's comparison figures.
COLS <- setNames(c("#496142", WASTE_COLOUR), c(LAB_NULL, LAB_FIT))

base <- function(p) p +
  scale_colour_manual(values = COLS, name = NULL) +
  scale_x_log10(labels = label_comma()) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    legend.position = "bottom", panel.grid.minor = element_blank(),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR)
  )

p_lin <- base(ggplot(long, aes(pop_density_km2, p, colour = series)) + geom_line(linewidth = 1)) +
  scale_y_continuous(labels = percent_format(accuracy = 1)) +
  labs(title = "(a) As panel (b) is drawn: linear probability, log density",
       subtitle = "Proportional growth is not a straight line here — it accelerates off the panel",
       x = "WorldPop density (people / km²)", y = "P(waste-positive)")

p_log <- base(ggplot(long, aes(pop_density_km2, p, colour = series)) + geom_line(linewidth = 1)) +
  scale_y_log10(labels = percent_format(accuracy = 0.1)) +
  labs(title = "(b) The diagnostic view: log probability, log density",
       subtitle = sprintf("Proportional growth is a straight line of slope 1; the fitted curve's slope is about %.2f", elasticity),
       x = "WorldPop density (people / km²)", y = "P(waste-positive), log scale")

fig <- (p_lin | p_log) +
  plot_layout(guides = "collect") +
  plot_annotation(
    caption = paste0(
      "The null is anchored to the fitted curve at the lowest density shown, so the two agree where the data starts and the only question is how fast each grows.\n",
      sprintf("An elasticity of %.2f%s means waste prevalence rises far more slowly than density: a tenfold denser cell carries about %.1f times the prevalence, not 10 times.\n",
            elasticity, ci_txt, 10^elasticity),
      ci_note,
      "The outcome is a binary per-panorama indicator and therefore saturates, so part of the shortfall from 1 may be that ceiling rather than less waste per person."
    ),
    theme = theme(plot.caption = element_text(size = 8, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                              lineheight = 1.3, margin = margin(t = 8)))
  ) &
  theme(legend.position = "bottom")

FIG_DIR <- file.path(script_dir, "../../..", "Figure", "5_spatial_pattern",
                     "Signed_distance", "pop_adjusted", "worldpop_2020")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
out <- file.path(FIG_DIR, "Pop_scaling_null.png")
ggsave(out, fig, width = 11, height = 5.4, dpi = 400, bg = "white")
message("Wrote ", out)

cat(sprintf("\nAnchored at %s people/km2 = %.2f%%\n", comma(round(anchor_d)), 100 * anchor_p))
for (d in c(5000, 10000, 30000, 50000)) {
  i <- which.min(abs(obs$pop_density_km2 - d))
  cat(sprintf("  %6s /km2   fitted %5.2f%%   proportional %6.2f%%   ratio %.1fx\n",
              comma(d), 100 * obs$prob_waste_positive[i], 100 * obs$proportional[i],
              obs$proportional[i] / obs$prob_waste_positive[i]))
}

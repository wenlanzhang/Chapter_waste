#!/usr/bin/env Rscript
# Scratch (not in the pipeline): what would panel (b) of Pop_adjusted_gam_effects.png
# look like if visible waste simply scaled with population?
#
# "Waste grows the same as population" means the probability that a panorama shows
# waste is proportional to density: P = k * D, i.e. elasticity dlog(P)/dlog(D) = 1.
# On log-log axes that is a straight line of slope 1. The fitted curve has slope ~0.52.

suppressPackageStartupMessages({library(ggplot2); library(dplyr); library(scales); library(patchwork)})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "..", "R", "chapter_colours.R"))

CURVE <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance",
                   "pop_adjusted", "Nairobi_pop_adjusted_curve_population.csv")
obs <- read.csv(CURVE) |>
  filter(prob_waste_positive > 0, pop_density_km2 >= 1000, pop_density_km2 <= 70000)

# Anchor the proportional null on the observed curve at the low end, so the two
# agree where the data starts and the question is only how fast each grows.
anchor_d <- min(obs$pop_density_km2)
anchor_p <- obs$prob_waste_positive[which.min(obs$pop_density_km2)]
obs <- obs |> mutate(proportional = anchor_p * (pop_density_km2 / anchor_d))

long <- bind_rows(
  obs |> transmute(pop_density_km2, p = prob_waste_positive, series = "Fitted (elasticity 0.52)"),
  obs |> transmute(pop_density_km2, p = proportional,        series = "If waste scaled with population (elasticity 1)")
) |>
  mutate(series = factor(series, levels = c("If waste scaled with population (elasticity 1)",
                                            "Fitted (elasticity 0.52)")))

COLS <- c("If waste scaled with population (elasticity 1)" = "#B03A2E",
          "Fitted (elasticity 0.52)" = WASTE_COLOUR)

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
       subtitle = "Proportional growth is a straight line of slope 1; the fitted curve is about half that",
       x = "WorldPop density (people / km²)", y = "P(waste-positive), log scale")

fig <- (p_lin | p_log) + plot_layout(guides = "collect") &
  theme(legend.position = "bottom")

out <- file.path(script_dir, "Pop_scaling_null.png")
ggsave(out, fig, width = 11, height = 4.8, dpi = 300, bg = "white")
message("Wrote ", out)

cat(sprintf("\nAnchored at %s people/km2 = %.2f%%\n", comma(round(anchor_d)), 100 * anchor_p))
for (d in c(5000, 10000, 30000, 50000)) {
  i <- which.min(abs(obs$pop_density_km2 - d))
  cat(sprintf("  %6s /km2   fitted %5.2f%%   proportional %6.2f%%   ratio %.1fx\n",
              comma(d), 100 * obs$prob_waste_positive[i], 100 * obs$proportional[i],
              obs$proportional[i] / obs$prob_waste_positive[i]))
}

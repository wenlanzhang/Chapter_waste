#!/usr/bin/env Rscript
# Step 6.4b — does the settlement association survive self-collected imagery?
#   1_SC_settlement_comparison.png
#     (a) waste-positive rate inside vs outside, both arms
#     (b) the same association area-normalised (positives per km²)
#     (c) observation-frame NNR: observed mean 1-NN distance against the null
#
# Three claims, three panels. (a) is the rate, (b) is what the rate means once
# settlements are only 2.9% of the city, and (c) is the control that matters —
# the null is drawn from the panoramas that were actually available, so it moves
# when the observation frame moves.
#
# Inputs (6_selfcollected/4_pattern/settlement/, from 1_sc_settlement_association.py):
#   1_sc_settlement_contingency.csv
#   1_sc_settlement_zone_summary.csv
#   1_sc_settlement_nnr.csv
#   thesis_table/table_6_4_settlement_comparison.csv

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
source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "4_pattern", "settlement")
FIG_DIR <- file.path(script_dir, "../../..", "Figure", "6_selfcollected", "4_pattern", "settlement")

CONTINGENCY_CSV <- file.path(DATA_DIR, "1_sc_settlement_contingency.csv")
ZONE_CSV <- file.path(DATA_DIR, "1_sc_settlement_zone_summary.csv")
NNR_CSV <- file.path(DATA_DIR, "1_sc_settlement_nnr.csv")
TABLE_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_settlement_comparison.csv")
OUT_PATH <- file.path(FIG_DIR, "1_SC_settlement_comparison.png")

ARM_COLOURS <- c("GSVI" = "#BDB3A8", "GSVI + SC" = "#6B4226")
ARM_LEVELS <- c("GSVI", "GSVI + SC")

for (f in c(CONTINGENCY_CSV, ZONE_CSV, NNR_CSV, TABLE_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f,
         " — run 6_selfcollected/4_pattern/settlement/1_sc_settlement_association.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

cont <- read.csv(CONTINGENCY_CSV, stringsAsFactors = FALSE)
zones <- read.csv(ZONE_CSV, stringsAsFactors = FALSE, check.names = FALSE)
nnr <- read.csv(NNR_CSV, stringsAsFactors = FALSE)
tbl <- read.csv(TABLE_CSV, stringsAsFactors = FALSE, check.names = FALSE)

get_row <- function(measure, col) tbl[[col]][tbl$Measure == measure]

wilson <- function(k, n, z = 1.96) {
  p <- k / n
  den <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / den
  margin <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / den
  c(low = max(0, centre - margin), high = min(1, centre + margin))
}

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      legend.position = "bottom"
    )
}

# --- (a) rate by zone ---------------------------------------------------------
rates <- cont |>
  mutate(
    n = `Waste.positive` + `Non.positive`,
    rate_pct = 100 * `Waste.positive` / n,
    ci_low = 100 * mapply(function(k, nn) wilson(k, nn)["low"], `Waste.positive`, n),
    ci_high = 100 * mapply(function(k, nn) wilson(k, nn)["high"], `Waste.positive`, n),
    Zone = factor(Zone, levels = c("Inside settlement", "Outside settlement")),
    Arm = factor(Arm, levels = ARM_LEVELS)
  )

p_rate <- ggplot(rates, aes(Zone, rate_pct, fill = Arm)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.6) +
  geom_errorbar(aes(ymin = ci_low, ymax = ci_high), position = position_dodge(width = 0.7),
                width = 0.14, linewidth = 0.4, colour = "#3a3a3a") +
  geom_text(aes(label = sprintf("%.1f%%", rate_pct), y = ci_high),
            position = position_dodge(width = 0.7), vjust = -0.6,
            size = 2.9, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, max(rates$ci_high) * 1.18),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(a) Waste-positive rate by zone",
    subtitle = sprintf("Prevalence ratio %s → %s | Wilson 95%% CI",
                       get_row("Prevalence ratio (inside / outside)", "GSVI"),
                       get_row("Prevalence ratio (inside / outside)", "GSVI + SC")),
    x = NULL, y = "Waste-positive locations (%)"
  ) +
  base_theme()

# --- (b) area-normalised density ---------------------------------------------
dens <- zones |>
  mutate(
    Zone = factor(Zone, levels = c("Urban poor", "Non-urban-poor")),
    Arm = factor(Arm, levels = ARM_LEVELS)
  )

p_dens <- ggplot(dens, aes(Zone, `Positive density (per km²)`, fill = Arm)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.6) +
  geom_text(aes(label = sprintf("%.1f", `Positive density (per km²)`)),
            position = position_dodge(width = 0.7), vjust = -0.5,
            size = 2.9, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_fill_manual(name = NULL, values = ARM_COLOURS) +
  scale_y_continuous(limits = c(0, max(dens$`Positive density (per km²)`) * 1.18),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(b) Positive density per km²",
    subtitle = sprintf("Density ratio %s → %s | settlements are 2.9%% of the city",
                       get_row("Density ratio", "GSVI"), get_row("Density ratio", "GSVI + SC")),
    x = NULL, y = "Waste-positive locations per km²"
  ) +
  base_theme()

# --- (c) observation-frame NNR -----------------------------------------------
nnr_long <- nnr |>
  mutate(Arm = factor(if_else(arm == "gsvi", "GSVI", "GSVI + SC"), levels = ARM_LEVELS)) |>
  select(Arm, Observed = observed_mean_nn_m, Null = null_mean_nn_m, nnr = nnr_observation_frame) |>
  pivot_longer(c(Observed, Null), names_to = "kind", values_to = "dist_m") |>
  mutate(kind = factor(kind, levels = c("Observed", "Null")))

nnr_labels <- nnr |>
  mutate(Arm = factor(if_else(arm == "gsvi", "GSVI", "GSVI + SC"), levels = ARM_LEVELS),
         label = sprintf("NNR %.3f\np = %.3f", nnr_observation_frame, p_value))

p_nnr <- ggplot(nnr_long, aes(Arm, dist_m, fill = kind)) +
  geom_col(position = position_dodge(width = 0.7), width = 0.6) +
  geom_text(aes(label = sprintf("%.0f m", dist_m)), position = position_dodge(width = 0.7),
            vjust = -0.5, size = 2.9, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  geom_text(data = nnr_labels, aes(x = Arm, y = null_mean_nn_m * 1.15, label = label),
            inherit.aes = FALSE, size = 2.7, colour = "grey35", lineheight = 0.95) +
  scale_fill_manual(name = NULL, values = c("Observed" = "#cb181d", "Null" = "#D4CCC2")) +
  scale_y_continuous(limits = c(0, max(nnr_long$dist_m) * 1.34),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "(c) Observation-frame NNR",
    subtitle = "Observed mean 1-NN distance vs 999 draws from the available panoramas",
    x = NULL, y = "Mean 1-NN distance (m)"
  ) +
  base_theme()

fig <- (p_rate | p_dens | p_nnr) +
  plot_annotation(
    title = "The settlement association, with and without self-collected imagery",
    subtitle = sprintf(
      "%s → %s observation locations | %s → %s waste-positive | same settlement polygons on both arms",
      get_row("Observation locations", "GSVI"), get_row("Observation locations", "GSVI + SC"),
      get_row("Waste-positive locations", "GSVI"), get_row("Waste-positive locations", "GSVI + SC")
    ),
    caption = paste0(
      "The NNR null is drawn from the panoramas that were actually available, not from the city polygon, so it asks whether positives cluster relative to where the platform could see.\n",
      "The rate and density outside settlements are unchanged and the NNR barely moves, so the association is not an artefact of Street View's routes.\n",
      "The inside figures rise partly by construction: self-collected imagery was gathered near settlements on purpose."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 14, height = 5.4, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

#!/usr/bin/env Rscript
# Step 5 sensitivity figure — is the settlement association just population density?
#   Settlement_by_density_band.png
#     (a) waste-positive rate inside vs outside a settlement, within density bands
#     (b) the rate ratio between them, with 95% CI
#
# If density explained the settlement association, the two series in (a) would
# coincide and every ratio in (b) would sit on 1.
#
# Input: Signed_distance/pop_adjusted/Nairobi_settlement_by_density_band.csv
#        (4_settlement_by_density_band.py)

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

DATA_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance", "pop_adjusted")
BAND_CSV <- file.path(DATA_DIR, "Nairobi_settlement_by_density_band.csv")
FIG_DIR <- file.path(script_dir, "../../..", "Figure", "5_spatial_pattern",
                     "Signed_distance", "pop_adjusted")

if (!file.exists(BAND_CSV)) {
  stop("Missing ", BAND_CSV,
       " — run 5_spatial_pattern/Signed_distance/pop_adjusted/4_settlement_by_density_band.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

bands <- read.csv(BAND_CSV, stringsAsFactors = FALSE) |>
  arrange(density_low) |>
  mutate(
    band = factor(density_band, levels = density_band),
    # pandas writes booleans as "True"/"False", which read.csv keeps as character
    reportable = as.logical(reportable)
  )

ZONE_COLOURS <- c("Outside settlement" = "#C9A27F", "Inside settlement" = "#5F6F5A")

rates <- bands |>
  select(band, reportable, n_outside, n_inside, rate_outside_pct, rate_inside_pct) |>
  pivot_longer(c(rate_outside_pct, rate_inside_pct), names_to = "zone", values_to = "rate") |>
  mutate(
    zone = factor(if_else(zone == "rate_outside_pct", "Outside settlement", "Inside settlement"),
                  levels = names(ZONE_COLOURS)),
    n = if_else(zone == "Outside settlement", n_outside, n_inside),
    # a band with too few inside-settlement panoramas is dropped from that series only
    rate = if_else(zone == "Inside settlement" & !reportable, NA_real_, rate)
  )

n_total <- sum(bands$n_outside) + sum(bands$n_inside)
n_bands_ok <- sum(bands$reportable)

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.4, colour = CHAPTER_AXIS_COLOUR),
      axis.text.x = element_text(angle = 35, hjust = 1),
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = 9, colour = CHAPTER_AXIS_COLOUR)
    )
}

# --- (a) rates side by side --------------------------------------------------
p_rates <- ggplot(rates, aes(band, rate, fill = zone)) +
  geom_col(position = position_dodge(width = 0.76), width = 0.66,
           colour = "white", linewidth = 0.35, na.rm = TRUE) +
  geom_text(aes(label = sprintf("%.1f", rate)),
            position = position_dodge(width = 0.76), vjust = -0.4,
            size = 2.5, fontface = "bold", colour = CHAPTER_AXIS_COLOUR, na.rm = TRUE) +
  scale_fill_manual(values = ZONE_COLOURS) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.14))) +
  labs(
    title = "(a) Waste-positive rate within population-density bands",
    subtitle = "Comparing like with like: if density explained the settlement association, the bars would match",
    x = "WorldPop density band (people / km²)", y = "Waste-positive panoramas (%)"
  ) +
  base_theme()

# --- (b) rate ratio ----------------------------------------------------------
ratios <- bands |> filter(reportable)

p_ratio <- ggplot(ratios, aes(band, rate_ratio)) +
  geom_hline(yintercept = 1, linetype = "22", colour = "grey55", linewidth = 0.4) +
  geom_linerange(aes(ymin = rate_ratio_ci95_low, ymax = rate_ratio_ci95_high),
                 colour = ZONE_COLOURS[["Inside settlement"]], linewidth = 0.7) +
  geom_point(size = 2.6, colour = ZONE_COLOURS[["Inside settlement"]]) +
  geom_text(aes(label = sprintf("%.1f×", rate_ratio)),
            hjust = -0.35, size = 2.7, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  scale_y_log10(breaks = c(1, 2, 5, 10, 20), labels = function(x) paste0(x, "×"),
                expand = expansion(mult = c(0.06, 0.16))) +
  labs(
    title = "(b) Inside / outside rate ratio",
    subtitle = "Every band is above 1, but the gap narrows as density rises",
    x = "WorldPop density band (people / km²)", y = "Rate ratio (log scale, 95% CI)"
  ) +
  base_theme()

fig <- (p_rates | p_ratio) +
  plot_layout(widths = c(1.35, 1)) +
  plot_annotation(
    title = "Settlement association within population-density bands",
    subtitle = sprintf(
      "Nairobi | %s GSVI panoramas | %d of %d bands have enough inside-settlement panoramas to report",
      comma(n_total), n_bands_ok, nrow(bands)
    ),
    caption = paste0(
      "Non-parametric companion to the nested GAMs: panoramas are grouped into equal-count bands of WorldPop density, ",
      "then compared inside vs outside a mapped urban-poor settlement.\nThe lowest band is omitted from the inside series ",
      "(only 15 panoramas). Ratios narrow from 11.1× to 1.6×, so density carries real weight at the top end, ",
      "but never accounts for the association entirely."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

out <- file.path(FIG_DIR, "Settlement_by_density_band.png")
ggsave(out, fig, width = 12, height = 5.8, dpi = 400, bg = "white")
message("Wrote ", out)
message("Done.")

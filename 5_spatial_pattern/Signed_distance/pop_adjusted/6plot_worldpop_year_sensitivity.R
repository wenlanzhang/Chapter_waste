#!/usr/bin/env Rscript
# WorldPop reference-year sensitivity, from 6_worldpop_year_sensitivity.py.
#   (a) MDP distance curve, manuscript product (unconstrained): 2020 / 2018 / year-matched
#   (b) MDP distance curve, WorldPop R2025A constrained: 2018 / 2022 / year-matched (+ 2020 bridge)
#   (c) settlement edge ÷ 2 km contrast (2 km block bootstrap 95%) and ΔAIC for distance
# Output: Figure/5_spatial_pattern/Signed_distance/pop_adjusted/worldpop_2020/Worldpop_year_sensitivity.png

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

if (!identical(Sys.getlocale("LC_CTYPE"), "en_US.UTF-8")) {
  invisible(suppressWarnings(Sys.setlocale("LC_CTYPE", "en_US.UTF-8")))
}

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
repo_root <- normalizePath(file.path(script_dir, "..", "..", ".."))
source(file.path(repo_root, "R", "pop_adjusted_paths.R"))
WY_DIR <- file.path(POP_DIR, "worldpop_year")

summ_path <- file.path(WY_DIR, "Nairobi_worldpop_year_summary.csv")
curve_path <- file.path(WY_DIR, "Nairobi_worldpop_year_curves.csv")
if (!file.exists(summ_path) || !file.exists(curve_path)) {
  stop("Missing outputs in ", WY_DIR, ". Run 6_worldpop_year_sensitivity.py")
}
summ <- read.csv(summ_path, stringsAsFactors = FALSE)
cur <- read.csv(curve_path, stringsAsFactors = FALSE)

AXIS <- CHAPTER_AXIS_COLOUR
base_theme <- theme_classic(base_size = 10) +
  theme(
    plot.title = element_text(colour = AXIS, face = "bold", size = 10),
    plot.subtitle = element_text(colour = AXIS, size = 8),
    plot.caption = element_text(colour = AXIS, size = 7.5, hjust = 0, lineheight = 1.1),
    axis.title = element_text(colour = AXIS, size = 9),
    axis.text = element_text(colour = AXIS, size = 8),
    axis.line = element_line(colour = AXIS, linewidth = 0.4),
    axis.ticks = element_line(colour = AXIS, linewidth = 0.35),
    legend.text = element_text(colour = AXIS, size = 7.8),
    legend.key.width = unit(16, "pt"),
    plot.margin = margin(6, 10, 6, 6)
  )

order <- summ$label
cols <- setNames(
  c("#1F120C", GSVI_COLOUR, WASTE_COLOUR, "#9C9C9C", CHAPTER_SEQ_MID, SLUM_FILL, "#2E4A2A"),
  summ$label[match(c("A_static_2020", "A_static_2018", "A_matched", "B_bridge_2020",
                     "B_static_2018", "B_static_2022", "B_matched"), summ$spec)]
)
ltys <- setNames(ifelse(grepl("matched", summ$spec), "solid",
                        ifelse(grepl("bridge", summ$spec), "22", "solid")), summ$label)
nlab <- setNames(sprintf("%s (n = %s)", summ$label, comma(summ$n_panoramas)), summ$label)

curve_panel <- function(set_id, title) {
  d <- filter(cur, set == set_id) %>% mutate(label = factor(label, levels = order))
  ggplot(d, aes(signed_distance_m, prob, colour = label, linetype = label)) +
    geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35) +
    geom_line(linewidth = 0.75) +
    scale_colour_manual(values = cols, labels = nlab, name = NULL) +
    scale_linetype_manual(values = ltys, labels = nlab, name = NULL) +
    scale_x_continuous(labels = comma, breaks = seq(0, 5000, 1000)) +
    scale_y_continuous(breaks = seq(0, 0.12, 0.02), labels = percent_format(accuracy = 1),
                       expand = expansion(mult = c(0, 0.04))) +
    coord_cartesian(xlim = c(min(d$signed_distance_m), 5000), ylim = c(0, NA)) +
    labs(title = title, subtitle = "MDP, standardised over population and year",
         x = "Signed distance to settlement (m; negative = inside)",
         y = "Predicted P(waste-positive)") +
    base_theme +
    theme(legend.position = c(0.60, 0.80))
}

p_a <- curve_panel("A", "(a) Manuscript product: WorldPop unconstrained")
p_b <- curve_panel("B", "(b) WorldPop R2025A constrained (2018, 2022)")

sc <- summ %>% mutate(label = factor(label, levels = rev(order)),
                      setlab = ifelse(set == "A", "Unconstrained (manuscript product)",
                                      "Constrained R2025A, common sample"))
p_c <- ggplot(sc, aes(curve_ratio_0m_vs_2000m, label, colour = label)) +
  geom_vline(xintercept = 1, colour = "#BDBDBD", linewidth = 0.3) +
  geom_errorbar(aes(xmin = curve_ratio_lo, xmax = curve_ratio_hi), width = 0.25, linewidth = 0.5,
                orientation = "y") +
  geom_point(size = 1.9) +
  geom_text(aes(x = curve_ratio_hi, label = sprintf("%.2f (%.2f–%.2f)   ΔAIC distance %s",
                                                    curve_ratio_0m_vs_2000m, curve_ratio_lo,
                                                    curve_ratio_hi, comma(round(delta_aic_MP_minus_MDP)))),
            hjust = -0.05, size = 2.5, colour = AXIS) +
  scale_colour_manual(values = cols, guide = "none") +
  scale_x_continuous(limits = c(0, NA), expand = expansion(mult = c(0, 0.75))) +
  labs(title = "(c) Settlement edge ÷ 2 km, by population layer",
       subtitle = "Point estimate and 2 km spatial block bootstrap 95% interval; ΔAIC = MP − MDP",
       x = "Adjusted P(waste) at settlement edge ÷ at 2 km", y = NULL) +
  base_theme

caption <- paste(strwrap(sprintf(paste(
  "Year-matched: 2015–2019 imagery takes the 2018 layer; 2021–2022 imagery takes 2020 (unconstrained, the",
  "latest in that series) or 2022 (constrained). Constrained layers have no value outside built-up areas,",
  "so set (b) uses the panoramas valid in every layer. %d block draws per specification."
), max(summ$n_boot)), 190), collapse = "\n")

fig <- wrap_elements(full = p_a | p_b) / wrap_elements(full = p_c) +
  plot_layout(heights = c(1.15, 0.9)) +
  plot_annotation(caption = caption, theme = base_theme)

out <- file.path(FIG_DIR, "Worldpop_year_sensitivity.png")
if (requireNamespace("ragg", quietly = TRUE)) {
  ggsave(out, fig, width = 11, height = 8, dpi = 300, bg = "white", device = ragg::agg_png)
} else {
  ggsave(out, fig, width = 11, height = 8, dpi = 300, bg = "white")
}
message("Wrote ", out)

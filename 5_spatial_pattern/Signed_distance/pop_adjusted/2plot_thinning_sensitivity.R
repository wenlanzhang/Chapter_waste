#!/usr/bin/env Rscript
# Spatial-thinning sensitivity (R1.5 / R3.1), from 2_thinning_sensitivity.py.
#
# Thinning_sensitivity.png  (supplementary, four panels)
#   (a) pop- and year-standardised MDP distance curve: no thinning vs label-blind
#       thinning at each threshold
#   (b) prevalence, (c) settlement prevalence ratio, (d) McFadden pseudo-R² (MDP)
#       against threshold, label-blind thinning only
# Thinning_sensitivity_main.png  (main text, two panels): the curve and the ratio
#
# Bands and error bars are the 2.5th–97.5th percentiles over 100 random thinning
# draws: variability due to which panoramas are retained, NOT confidence intervals.
#
# Optional: --data-subdir=worldpop_2020 reads pop_adjusted/worldpop_2020/thinning/
# and writes to Figure/.../pop_adjusted/worldpop_2020/ (the manuscript sample).

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

trailing <- commandArgs(trailingOnly = TRUE)
hit <- grep("^--data-subdir=", trailing, value = TRUE)
data_subdir <- if (length(hit)) sub("^--data-subdir=", "", hit[[1]]) else "worldpop_2020"

source(file.path(repo_root, "R", "chapter_paths.R"))
source(file.path(repo_root, "R", "chapter_colours.R"))

POP_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance", "pop_adjusted")
FIG_DIR <- file.path(repo_root, "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted")
if (nzchar(data_subdir)) {
  POP_DIR <- file.path(POP_DIR, data_subdir)
  FIG_DIR <- file.path(FIG_DIR, data_subdir)
}
THIN_DIR <- file.path(POP_DIR, "thinning")
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

summary_path <- file.path(THIN_DIR, "Nairobi_thinning_summary.csv")
curves_path <- file.path(THIN_DIR, "Nairobi_thinning_curves.csv")
if (!file.exists(summary_path) || !file.exists(curves_path)) {
  stop(
    "Missing thinning outputs in ", THIN_DIR, ". Run:\n  python ",
    "5_spatial_pattern/Signed_distance/pop_adjusted/2_thinning_sensitivity.py",
    if (nzchar(data_subdir)) paste0(" --data-subdir ", data_subdir) else ""
  )
}
smry <- read.csv(summary_path, stringsAsFactors = FALSE)
curves <- read.csv(curves_path, stringsAsFactors = FALSE)
n_unthinned <- smry$n_panoramas_median[smry$scheme == "baseline"][1]
n_draws <- max(smry$n_reps)

AXIS <- CHAPTER_AXIS_COLOUR
BLIND <- WASTE_COLOUR
BASE <- "#1F120C"

base_theme <- theme_classic(base_size = 10) +
  theme(
    plot.title = element_text(colour = AXIS, face = "bold", size = 10),
    plot.subtitle = element_text(colour = AXIS, size = 8),
    plot.caption = element_text(colour = AXIS, size = 7.5, hjust = 0, lineheight = 1.1),
    axis.title = element_text(colour = AXIS, size = 9),
    axis.text = element_text(colour = AXIS, size = 8),
    axis.line = element_line(colour = AXIS, linewidth = 0.4),
    axis.ticks = element_line(colour = AXIS, linewidth = 0.35),
    legend.title = element_text(colour = AXIS, size = 8.5),
    legend.text = element_text(colour = AXIS, size = 8),
    legend.key.height = unit(10, "pt"),
    plot.margin = margin(6, 10, 6, 6)
  )

# ---------------------------------------------------------------- curve panel
thresholds <- sort(unique(smry$threshold_m[smry$threshold_m > 0]))
thr_levels <- c("No thinning", paste0(thresholds, " m"))
thr_cols <- c(
  "No thinning" = BASE,
  setNames(
    colorRampPalette(c(CHAPTER_SEQ_MID, SLUM_FILL))(length(thresholds)),
    paste0(thresholds, " m")
  )
)

cv <- curves %>%
  filter(scheme %in% c("baseline", "label_blind")) %>%
  mutate(label = factor(
    ifelse(scheme == "baseline", "No thinning", paste0(threshold_m, " m")),
    levels = thr_levels
  ))

curve_panel <- function(title, legend_pos) {
  ggplot(cv, aes(signed_distance_m, prob_median, colour = label, fill = label)) +
    geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35) +
    geom_ribbon(
      data = filter(cv, scheme == "label_blind"),
      aes(ymin = prob_lo, ymax = prob_hi),
      alpha = 0.10, colour = NA
    ) +
    geom_line(aes(linewidth = label == "No thinning")) +
    scale_linewidth_manual(values = c(`TRUE` = 0.9, `FALSE` = 0.6), guide = "none") +
    scale_colour_manual(values = thr_cols, name = "Label-blind\nthinning distance") +
    scale_fill_manual(values = thr_cols, guide = "none") +
    scale_x_continuous(labels = comma, breaks = seq(0, 5000, 1000)) +
    scale_y_continuous(labels = percent_format(accuracy = 1),
                       expand = expansion(mult = c(0, 0.04))) +
    # the curve is flat beyond ~4 km; zoom without dropping data from the ribbons
    coord_cartesian(xlim = c(min(cv$signed_distance_m), 5000), ylim = c(0, NA)) +
    labs(
      title = title,
      subtitle = "MDP, standardised over population and year; shown to 5 km",
      x = "Signed distance to settlement (m; negative = inside)",
      y = "Predicted P(waste-positive)"
    ) +
    base_theme +
    theme(legend.position = legend_pos)
}

# ---------------------------------------------------------------- metric panels
# Only the label-blind scheme is drawn. The superseded positive-only scheme
# stays in the summary table but is not shown.
scheme_lab <- c(label_blind = "Label-blind thinning of all panoramas")
base_row <- filter(smry, scheme == "baseline")
long <- bind_rows(
  lapply(names(scheme_lab), function(s) {
    bind_rows(mutate(base_row, scheme = s), filter(smry, scheme == s))
  })
) %>%
  mutate(scheme = factor(scheme_lab[scheme], levels = scheme_lab))

# Retained counts per threshold (medians over draws), printed above each point
# so the figure itself shows that positives and negatives are thinned together.
count_lab <- long %>%
  distinct(threshold_m, n_panoramas_median, n_positive_median) %>%
  transmute(
    threshold_m,
    count_label = sprintf("%s\n(%s)", comma(round(n_panoramas_median)),
                          comma(round(n_positive_median)))
  )

metric_panel <- function(col, title, ylab, lab_fun, subtitle = NULL, counts = FALSE) {
  d <- long %>%
    transmute(
      scheme, threshold_m,
      med = .data[[paste0(col, "_median")]],
      lo = .data[[paste0(col, "_lo")]],
      hi = .data[[paste0(col, "_hi")]]
    )
  if (counts) {
    d <- left_join(d, count_lab, by = "threshold_m") %>%
      arrange(threshold_m) %>%
      mutate(
        top = pmax(med, hi, na.rm = TRUE),
        # the unthinned label goes below its point when the line rises from it,
        # so it does not cover the start of the line
        below = threshold_m == 0 & lead(med) > med,
        lab_y = ifelse(below, med, top),
        lab_vjust = ifelse(below, 1.25, -0.2)
      )
  }
  count_layer <- if (counts) {
    # white backing so the unthinned reference line does not strike through a label
    geom_label(aes(y = lab_y, label = count_label, vjust = lab_vjust), size = 2.5,
               lineheight = 0.9, colour = AXIS, fill = "white", linewidth = 0,
               label.padding = unit(1.5, "pt"), show.legend = FALSE)
  }
  ggplot(d, aes(threshold_m, med, colour = scheme, linetype = scheme, shape = scheme)) +
    geom_hline(yintercept = d$med[d$threshold_m == 0][1], colour = "#BDBDBD", linewidth = 0.3) +
    geom_errorbar(aes(ymin = lo, ymax = hi), width = 4, linetype = "solid", linewidth = 0.4) +
    geom_line(linewidth = 0.6) +
    geom_point(size = 1.8, fill = "white") +
    count_layer +
    scale_colour_manual(values = setNames(BLIND, scheme_lab), name = NULL) +
    scale_linetype_manual(values = setNames("solid", scheme_lab), name = NULL) +
    scale_shape_manual(values = setNames(16, scheme_lab), name = NULL) +
    scale_x_continuous(
      breaks = c(0, thresholds), labels = function(x) ifelse(x == 0, "none", x),
      expand = expansion(mult = if (counts) 0.09 else 0.05)
    ) +
    scale_y_continuous(labels = lab_fun,
                       expand = expansion(mult = c(0.05, if (counts) 0.16 else 0.05))) +
    labs(title = title, subtitle = subtitle, x = "Thinning distance (m)", y = ylab) +
    base_theme +
    theme(legend.position = "none")
}

pct_lab <- function(x) paste0(format(x, nsmall = 1), "%")
ratio_lab <- label_number(accuracy = 0.1)

interval_text <- sprintf(
  paste(
    "Thinning is label-blind: it is applied to all panoramas, waste-positive and waste-negative alike.",
    "Numbers at each point: panoramas retained, with the waste-positive among them in brackets (medians over draws).",
    "Shaded bands and error bars: 2.5th–97.5th percentiles over %d random thinning draws per distance.",
    "They show variability due to which panoramas are retained, not statistical confidence intervals.",
    "Thin horizontal line: value in the unthinned sample (%s panoramas)."
  ),
  n_draws, comma(n_unthinned)
)
interval_note <- function(width) paste(strwrap(interval_text, width), collapse = "\n")

save_fig <- function(fig, name, width, height) {
  out <- file.path(FIG_DIR, name)
  if (requireNamespace("ragg", quietly = TRUE)) {
    ggsave(out, fig, width = width, height = height, dpi = 300, bg = "white", device = ragg::agg_png)
  } else {
    ggsave(out, fig, width = width, height = height, dpi = 300, bg = "white")
  }
  message("Wrote ", out)
}

# ---------------------------------------------------------------- supplementary: four panels
p_b <- metric_panel("prevalence_pct", "(b) Prevalence", "Waste-positive panoramas", pct_lab,
                    counts = TRUE)
p_c <- metric_panel("prevalence_ratio", "(c) Settlement prevalence ratio",
                    "Rate inside / rate outside", ratio_lab)
p_d <- metric_panel("pseudo_r2_MDP", "(d) Model fit, MDP", "McFadden pseudo-R²",
                    label_number(accuracy = 0.01),
                    subtitle = "Diagnostic only; n and sample vary")

bottom <- (p_b | p_c | p_d)
supp <- wrap_elements(full = curve_panel("(a) Adjusted signed-distance curve", c(0.85, 0.62))) /
  wrap_elements(full = bottom) +
  plot_layout(heights = c(1, 1.05)) +
  plot_annotation(caption = interval_note(175), theme = base_theme)
save_fig(supp, "Thinning_sensitivity.png", 9, 7.6)

# ---------------------------------------------------------------- main text: curve + ratio
m_a <- curve_panel("(a) Adjusted signed-distance curve", c(0.78, 0.62))
m_b <- metric_panel("prevalence_ratio", "(b) Settlement prevalence ratio",
                    "Rate inside / rate outside", ratio_lab, counts = TRUE)
main <- (m_a | m_b) +
  plot_layout(widths = c(1.7, 1)) +
  plot_annotation(caption = interval_note(195), theme = base_theme)
save_fig(main, "Thinning_sensitivity_main.png", 10, 4.6)

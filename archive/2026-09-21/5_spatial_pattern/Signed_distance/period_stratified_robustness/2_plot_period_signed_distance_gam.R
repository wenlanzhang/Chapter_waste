#!/usr/bin/env Rscript
# Period-stratified signed-distance logistic GAM curves (2015-2019 vs 2021-2022)
# Full-range panel + top-right inset; bootstrap 95% CI bands.

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

source(file.path(script_dir, "../../..", "R", "chapter_paths.R"))
DATA_ROOT <- chapter_data_root
EXTERNAL_DIR <- file.path(
  DATA_ROOT, "5_spatial_pattern", "Signed_distance", "period_stratified_robustness"
)
DATA_DIR <- if (dir.exists(EXTERNAL_DIR) &&
                 file.exists(file.path(EXTERNAL_DIR, "Nairobi_period_signed_distance_gam_curve.csv"))) {
  EXTERNAL_DIR
} else {
  script_dir
}
FIG_DIR <- file.path(
  script_dir, "..", "..", "..", "Figure", "5_spatial_pattern", "Signed_distance",
  "period_stratified_robustness"
)

INSET_XMAX_M <- 1000
AXIS_COLOUR <- "#1F120C"
INSET_EDGE <- "#1F120C"
GSVI_COLOUR <- "#C9A27F"

curve_path <- file.path(DATA_DIR, "Nairobi_period_signed_distance_gam_curve.csv")
summary_path <- file.path(DATA_DIR, "Nairobi_period_signed_distance_gam_summary.csv")
frame_path <- file.path(DATA_DIR, "Nairobi_period_signed_distance_frame.csv")

message("Data dir: ", DATA_DIR)
if (!file.exists(curve_path)) {
  stop(
    "Missing period GAM curve. Run:\n",
    "  python 5_spatial_pattern/Signed_distance/period_stratified_robustness/",
    "1_period_signed_distance_gam.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

curve <- read.csv(curve_path, stringsAsFactors = FALSE)
if (!"period_label" %in% names(curve)) {
  curve$period_label <- curve$period
}

# ASCII hyphens so titles/legend never render as "..."
normalise_period <- function(x) {
  x <- as.character(x)
  x <- iconv(x, from = "", to = "ASCII", sub = "-")
  x <- gsub("-+", "-", x)
  x <- gsub("^2015-2019.*", "2015-2019", x)
  x <- gsub("^2021-2022.*", "2021-2022", x)
  x[grepl("2015", x) & grepl("2019", x)] <- "2015-2019"
  x[grepl("2021", x) & grepl("2022", x)] <- "2021-2022"
  x
}

curve$period_label <- normalise_period(curve$period_label)
curve$period_label <- factor(curve$period_label, levels = c("2015-2019", "2021-2022"))

period_cols <- c(
  "2015-2019" = "#6B4226",
  "2021-2022" = "#C9A27F"
)
period_cols <- period_cols[names(period_cols) %in% levels(droplevels(curve$period_label))]

has_ci <- all(c("prob_ci_low", "prob_ci_high") %in% names(curve)) &&
  any(is.finite(curve$prob_ci_low) & is.finite(curve$prob_ci_high))

subtitle <- "P(waste-positive panorama | signed distance) by capture period"
if (file.exists(summary_path)) {
  sm <- read.csv(summary_path, stringsAsFactors = FALSE)
  if (all(c("period_label", "n_panoids", "n_waste_positive") %in% names(sm))) {
    sm$period_label <- normalise_period(sm$period_label)
    bits <- apply(sm, 1, function(r) {
      sprintf(
        "%s: n=%s (waste+=%s)",
        r[["period_label"]],
        format(as.integer(r[["n_panoids"]]), big.mark = ","),
        format(as.integer(r[["n_waste_positive"]]), big.mark = ",")
      )
    })
    subtitle <- paste(bits, collapse = "  |  ")
  }
}

caption <- if (has_ci) {
  "Shaded bands: bootstrap 95% CI  |  Panorama unit; GSVI only"
} else {
  "Panorama unit; GSVI only"
}

rug_df <- NULL
if (file.exists(frame_path)) {
  frame <- read.csv(frame_path, stringsAsFactors = FALSE)
  if ("signed_distance_m" %in% names(frame)) {
    set.seed(42)
    n_rug <- min(nrow(frame), 5000)
    rug_df <- frame[sample.int(nrow(frame), n_rug), , drop = FALSE]
  }
}

base_theme <- theme_classic(base_size = 12) +
  theme(
    plot.title = element_text(colour = AXIS_COLOUR, face = "bold"),
    plot.subtitle = element_text(colour = AXIS_COLOUR, size = 9),
    plot.caption = element_text(colour = AXIS_COLOUR, size = 8, hjust = 1),
    axis.title = element_text(colour = AXIS_COLOUR),
    axis.title.x = element_text(colour = AXIS_COLOUR),
    axis.title.y = element_text(colour = AXIS_COLOUR),
    axis.text = element_text(colour = AXIS_COLOUR),
    axis.text.x = element_text(colour = AXIS_COLOUR),
    axis.text.y = element_text(colour = AXIS_COLOUR),
    axis.line = element_line(colour = AXIS_COLOUR, linewidth = 0.45),
    axis.ticks = element_line(colour = AXIS_COLOUR, linewidth = 0.4),
    legend.position = c(0.22, 0.82),
    legend.background = element_rect(fill = alpha("white", 0.9), colour = NA),
    legend.text = element_text(colour = AXIS_COLOUR, size = 9),
    plot.margin = margin(t = 8, r = 14, b = 10, l = 8)
  )

main_x_vals <- curve$signed_distance_m
if (!is.null(rug_df)) {
  main_x_vals <- c(main_x_vals, rug_df$signed_distance_m)
}
main_x_lim <- range(main_x_vals, na.rm = TRUE)
main_y_hi <- max(
  curve$prob_waste_positive,
  if (has_ci) curve$prob_ci_high else NA_real_,
  na.rm = TRUE
)
main_y_lim <- c(0, main_y_hi * 1.06)

panel_x_range <- function(lim, mult = 0.02) {
  d <- diff(lim)
  c(lim[1] - mult * d, lim[2] + mult * d)
}
panel_y_range <- function(lim, mult_top = 0.02) {
  d <- diff(lim)
  c(lim[1], lim[2] + mult_top * d)
}

xlim_panel <- panel_x_range(main_x_lim)
ylim_panel <- panel_y_range(main_y_lim)

build_main_plot <- function(highlight_zoom = FALSE, x_min = NA_real_, x_max = NA_real_) {
  g <- ggplot(
    curve,
    aes(
      x = signed_distance_m,
      y = prob_waste_positive,
      colour = period_label,
      fill = period_label
    )
  )
  if (isTRUE(highlight_zoom) && is.finite(x_min) && is.finite(x_max)) {
    g <- g +
      annotate(
        "rect",
        xmin = x_min,
        xmax = x_max,
        ymin = -Inf,
        ymax = Inf,
        fill = alpha(GSVI_COLOUR, 0.12),
        colour = NA
      )
  }
  g <- g +
    geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.4)

  if (has_ci) {
    g <- g +
      geom_ribbon(
        aes(ymin = prob_ci_low, ymax = prob_ci_high),
        alpha = 0.18,
        colour = NA
      )
  }

  g <- g +
    geom_line(linewidth = 1.05) +
    scale_colour_manual(values = period_cols, name = NULL) +
    scale_fill_manual(values = period_cols, name = NULL) +
    scale_x_continuous(limits = xlim_panel, expand = c(0, 0)) +
    scale_y_continuous(
      labels = percent_format(accuracy = 0.1),
      limits = ylim_panel,
      expand = c(0, 0)
    ) +
    labs(
      title = "Period-stratified signed-distance logistic GAM",
      subtitle = subtitle,
      x = "Signed distance to settlement (m)\n(negative = inside, positive = outside)",
      y = "Predicted probability",
      caption = caption
    ) +
    base_theme

  if (!is.null(rug_df)) {
    g <- g +
      geom_rug(
        data = rug_df,
        aes(x = signed_distance_m),
        inherit.aes = FALSE,
        colour = GSVI_COLOUR,
        alpha = 0.12,
        length = unit(0.03, "npc")
      )
  }
  g
}

# --- Full-range figure with near-boundary inset ---
x_min <- min(curve$signed_distance_m, na.rm = TRUE)
curve_zoom <- curve %>%
  filter(signed_distance_m >= x_min, signed_distance_m <= INSET_XMAX_M)

fmt_m <- function(x) format(x, big.mark = ",", scientific = FALSE, trim = TRUE)
x_min_lab <- as.integer(10 * floor(x_min / 10))
inset_title <- sprintf(
  "Near-boundary relationship (%s to %s m)",
  fmt_m(x_min_lab),
  fmt_m(INSET_XMAX_M)
)

y_candidates <- curve_zoom$prob_waste_positive
if (has_ci) {
  y_candidates <- c(y_candidates, curve_zoom$prob_ci_high)
}
y_zoom_max <- max(y_candidates, na.rm = TRUE)
y_pad <- max(y_zoom_max * 0.08, 0.002)

p_inset <- ggplot(
  curve_zoom,
  aes(
    x = signed_distance_m,
    y = prob_waste_positive,
    colour = period_label,
    fill = period_label
  )
) +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35)

if (has_ci) {
  p_inset <- p_inset +
    geom_ribbon(
      aes(ymin = prob_ci_low, ymax = prob_ci_high),
      alpha = 0.18,
      colour = NA
    )
}

p_inset <- p_inset +
  geom_line(linewidth = 0.85) +
  scale_colour_manual(values = period_cols, guide = "none") +
  scale_fill_manual(values = period_cols, guide = "none") +
  scale_x_continuous(
    limits = c(x_min, INSET_XMAX_M),
    breaks = pretty(c(x_min, INSET_XMAX_M), n = 4),
    expand = expansion(mult = c(0.02, 0.02))
  ) +
  scale_y_continuous(
    labels = percent_format(accuracy = 0.1),
    limits = c(0, y_zoom_max + y_pad),
    breaks = pretty(c(0, y_zoom_max), n = 3),
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(title = inset_title, x = NULL, y = NULL) +
  theme_classic(base_size = 8) +
  theme(
    plot.title = element_text(
      colour = AXIS_COLOUR,
      face = "bold",
      size = 8.5,
      hjust = 0.5,
      margin = margin(b = 2, t = 1)
    ),
    axis.title = element_blank(),
    axis.text = element_text(colour = AXIS_COLOUR, size = 7.5),
    axis.line = element_line(colour = AXIS_COLOUR, linewidth = 0.35),
    axis.ticks = element_line(colour = AXIS_COLOUR, linewidth = 0.3),
    panel.background = element_rect(fill = "white", colour = NA),
    plot.background = element_rect(
      fill = alpha("white", 0.96),
      colour = INSET_EDGE,
      linewidth = 0.45
    ),
    plot.margin = margin(4, 6, 4, 4),
    legend.position = "none"
  )

if (!is.null(rug_df)) {
  rug_zoom <- rug_df %>%
    filter(signed_distance_m >= x_min, signed_distance_m <= INSET_XMAX_M)
  if (nrow(rug_zoom) > 0L) {
    p_inset <- p_inset +
      geom_rug(
        data = rug_zoom,
        aes(x = signed_distance_m),
        inherit.aes = FALSE,
        colour = GSVI_COLOUR,
        alpha = 0.18,
        length = unit(0.04, "npc")
      )
  }
}

p_with_inset <- build_main_plot(
  highlight_zoom = TRUE,
  x_min = x_min,
  x_max = INSET_XMAX_M
) +
  inset_element(
    p_inset,
    left = 0.34,
    bottom = 0.26,
    right = 0.985,
    top = 0.985,
    align_to = "panel",
    clip = TRUE
  )

out <- file.path(FIG_DIR, "Period_signed_distance_gam_curve.png")
ggsave(out, p_with_inset, width = 9.2, height = 5.6, dpi = 300)
message("Wrote ", out, " (inset: ", inset_title, ")")

# --- Standalone near-edge figure (same window as inset) ---
p_zoom <- ggplot(
  curve_zoom,
  aes(
    x = signed_distance_m,
    y = prob_waste_positive,
    colour = period_label,
    fill = period_label
  )
) +
  geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.4)

if (has_ci) {
  p_zoom <- p_zoom +
    geom_ribbon(
      aes(ymin = prob_ci_low, ymax = prob_ci_high),
      alpha = 0.18,
      colour = NA
    )
}

p_zoom <- p_zoom +
  geom_line(linewidth = 1.05) +
  scale_colour_manual(values = period_cols, name = NULL) +
  scale_fill_manual(values = period_cols, name = NULL) +
  scale_x_continuous(
    limits = c(x_min, INSET_XMAX_M),
    expand = expansion(mult = c(0.02, 0.02))
  ) +
  scale_y_continuous(
    labels = percent_format(accuracy = 0.1),
    limits = c(0, y_zoom_max + y_pad),
    expand = expansion(mult = c(0, 0.02))
  ) +
  labs(
    title = "Period-stratified signed-distance GAM (near edge to 1 km)",
    subtitle = subtitle,
    x = "Signed distance to settlement (m)\n(negative = inside, positive = outside)",
    y = "Predicted probability",
    caption = caption
  ) +
  base_theme +
  theme(legend.position = c(0.78, 0.82))

if (!is.null(rug_df)) {
  rug_zoom <- rug_df %>%
    filter(signed_distance_m >= x_min, signed_distance_m <= INSET_XMAX_M)
  if (nrow(rug_zoom) > 0L) {
    p_zoom <- p_zoom +
      geom_rug(
        data = rug_zoom,
        aes(x = signed_distance_m),
        inherit.aes = FALSE,
        colour = GSVI_COLOUR,
        alpha = 0.15,
        length = unit(0.03, "npc")
      )
  }
}

out_zoom <- file.path(FIG_DIR, "Period_signed_distance_gam_curve_near_edge.png")
ggsave(out_zoom, p_zoom, width = 8.5, height = 5.4, dpi = 300)
message("Wrote ", out_zoom)

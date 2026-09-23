#!/usr/bin/env Rscript
# Year-adjusted signed-distance logistic GAM predicted probability curve
# Full-range panel + top-right inset; bootstrap 95% CI band.

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

source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
DATA_ROOT <- chapter_data_root
SIG_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "Signed_distance")
LEGACY_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "settlement")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "Signed_distance")

INSET_XMAX_M <- 1000

WASTE_COLOUR <- "#6B4226"
GSVI_COLOUR <- "#C9A27F"
AXIS_COLOUR <- "#1F120C"
INSET_EDGE <- "#1F120C"

resolve_input <- function(filename) {
  candidates <- c(
    file.path(SIG_DIR, filename),
    file.path(script_dir, filename),
    file.path(LEGACY_DIR, filename)
  )
  for (p in candidates) {
    if (file.exists(p)) {
      if (!identical(p, candidates[[1]])) {
        message("Using path: ", p)
      }
      return(p)
    }
  }
  candidates[[1]]
}

curve_path <- resolve_input("Nairobi_signed_distance_gam_curve.csv")
summary_path <- resolve_input("Nairobi_signed_distance_gam_summary.csv")
frame_path <- resolve_input("Nairobi_signed_distance_gam_frame.csv")

if (!file.exists(curve_path)) {
  stop(
    "Missing GAM curve. Run:\n",
    "  python 5_spatial_pattern/Signed_distance/1_signed_distance_gam.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

curve <- read.csv(curve_path, stringsAsFactors = FALSE)
summary <- if (file.exists(summary_path)) read.csv(summary_path, stringsAsFactors = FALSE) else NULL
frame <- if (file.exists(frame_path)) read.csv(frame_path, stringsAsFactors = FALSE) else NULL

pred_type <- if ("prediction_type" %in% names(curve)) {
  as.character(curve$prediction_type[1])
} else {
  "fixed_year"
}

if (identical(pred_type, "year_standardised")) {
  # Keep figure text short; put technical detail in the thesis caption.
  subtitle <- "Year-standardised marginal predictions; model adjusted for panorama capture year"
} else {
  year_fixed <- if ("year_fe_fixed" %in% names(curve) && !is.na(curve$year_fe_fixed[1])) {
    as.character(curve$year_fe_fixed[1])
  } else {
    "modal year"
  }
  subtitle <- sprintf(
    "Predictions at year = %s; model adjusted for panorama capture year",
    year_fixed
  )
}
caption <- "Shaded bands = bootstrap 95% CI; rug = observed panorama distribution"

has_ci <- all(c("prob_ci_low", "prob_ci_high") %in% names(curve)) &&
  any(is.finite(curve$prob_ci_low) & is.finite(curve$prob_ci_high))
if (!has_ci) {
  message("Note: curve CSV has no CI columns; re-run 1_signed_distance_gam.py")
}

# Rug of observed signed distances (sample if huge)
rug_df <- NULL
if (!is.null(frame) && "signed_distance_m" %in% names(frame)) {
  set.seed(42)
  n_rug <- min(nrow(frame), 5000)
  rug_df <- frame[sample.int(nrow(frame), n_rug), , drop = FALSE]
}

base_theme <- theme_classic(base_size = 12) +
  theme(
    plot.title = element_text(colour = AXIS_COLOUR, face = "bold"),
    plot.subtitle = element_text(colour = AXIS_COLOUR, size = 9.5),
    plot.caption = element_text(colour = AXIS_COLOUR, size = 8, hjust = 0),
    axis.title = element_text(colour = AXIS_COLOUR),
    axis.title.x = element_text(colour = AXIS_COLOUR),
    axis.title.y = element_text(colour = AXIS_COLOUR),
    axis.text = element_text(colour = AXIS_COLOUR),
    axis.text.x = element_text(colour = AXIS_COLOUR),
    axis.text.y = element_text(colour = AXIS_COLOUR),
    axis.line = element_line(colour = AXIS_COLOUR, linewidth = 0.45),
    axis.ticks = element_line(colour = AXIS_COLOUR, linewidth = 0.4),
    # Extra right/bottom margin so subtitle and caption do not clip at canvas edge
    plot.margin = margin(t = 8, r = 14, b = 10, l = 8)
  )

# Panel axis limits (slight expand so curve is not flush to edges)
main_x_vals <- curve$signed_distance_m
if (!is.null(frame) && "signed_distance_m" %in% names(frame)) {
  main_x_vals <- c(main_x_vals, frame$signed_distance_m)
}
main_x_lim <- range(main_x_vals, na.rm = TRUE)
main_y_hi <- max(
  curve$prob_waste_positive,
  if (has_ci) curve$prob_ci_high else NA_real_,
  na.rm = TRUE
)
main_y_lim <- c(0, main_y_hi * 1.06)
X_EXPAND <- 0.02
Y_EXPAND_TOP <- 0.02

panel_x_range <- function(lim, mult = X_EXPAND) {
  d <- diff(lim)
  c(lim[1] - mult * d, lim[2] + mult * d)
}
panel_y_range <- function(lim, mult_bottom = 0, mult_top = Y_EXPAND_TOP) {
  d <- diff(lim)
  c(lim[1] - mult_bottom * d, lim[2] + mult_top * d)
}

xlim_panel <- panel_x_range(main_x_lim)
ylim_panel <- panel_y_range(main_y_lim)

build_main_plot <- function(
    highlight_zoom = FALSE,
    x_min = NA_real_,
    x_max = NA_real_
) {
  g <- ggplot(curve, aes(x = signed_distance_m, y = prob_waste_positive))
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
        fill = alpha(WASTE_COLOUR, 0.22),
        colour = NA
      )
  }

  g <- g +
    geom_line(colour = WASTE_COLOUR, linewidth = 1.0) +
    scale_x_continuous(
      limits = xlim_panel,
      expand = c(0, 0)
    ) +
    scale_y_continuous(
      labels = percent_format(accuracy = 0.1),
      limits = ylim_panel,
      expand = c(0, 0)
    ) +
    labs(
      title = "Signed-distance logistic GAM (panorama unit)",
      subtitle = subtitle,
      caption = caption,
      x = "Signed distance to settlement (m)\n(negative = inside, positive = outside)",
      y = "Predicted probability"
    ) +
    base_theme

  if (!is.null(rug_df)) {
    g <- g +
      geom_rug(
        data = rug_df,
        aes(x = signed_distance_m),
        inherit.aes = FALSE,
        colour = GSVI_COLOUR,
        alpha = 0.15,
        length = unit(0.03, "npc")
      )
  }
  g
}

p <- build_main_plot()
out <- file.path(FIG_DIR, "Signed_distance_gam_curve.png")
ggsave(out, p, width = 9.2, height = 5.6, dpi = 300)
message("Wrote ", out)

# --- Top-right inset: min signed distance → 1 km ---
x_min <- min(curve$signed_distance_m, na.rm = TRUE)
curve_zoom <- curve %>%
  filter(signed_distance_m >= x_min, signed_distance_m <= INSET_XMAX_M)

if (nrow(curve_zoom) < 2L) {
  warning("Too few points in inset range; skipping inset figure.")
} else {
  y_candidates <- c(curve_zoom$prob_waste_positive)
  if (has_ci) {
    y_candidates <- c(y_candidates, curve_zoom$prob_ci_high)
  }
  y_zoom_max <- max(y_candidates, na.rm = TRUE)
  y_pad <- max(y_zoom_max * 0.08, 0.002)

  rug_zoom <- NULL
  if (!is.null(rug_df)) {
    rug_zoom <- rug_df %>%
      filter(signed_distance_m >= x_min, signed_distance_m <= INSET_XMAX_M)
  }

  p_inset <- ggplot(curve_zoom, aes(x = signed_distance_m, y = prob_waste_positive)) +
    geom_vline(xintercept = 0, colour = "#8C7355", linetype = "dashed", linewidth = 0.35)

  if (has_ci) {
    p_inset <- p_inset +
      geom_ribbon(
        aes(ymin = prob_ci_low, ymax = prob_ci_high),
        fill = alpha(WASTE_COLOUR, 0.22),
        colour = NA
      )
  }

  # Readable inset range label (en dash); matches plotted zoom window
  # Round display bounds to tens for a clean title (limits stay exact).
  fmt_m <- function(x) format(x, big.mark = ",", scientific = FALSE, trim = TRUE)
  x_min_lab <- as.integer(10 * floor(x_min / 10))
  inset_title <- sprintf(
    "Near-boundary relationship (%s to %s m)",
    fmt_m(x_min_lab),
    fmt_m(INSET_XMAX_M)
  )

  p_inset <- p_inset +
    geom_line(colour = WASTE_COLOUR, linewidth = 0.85) +
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
    labs(
      title = inset_title,
      x = NULL,
      y = NULL
    ) +
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
      plot.margin = margin(4, 6, 4, 4)
    )

  if (!is.null(rug_zoom) && nrow(rug_zoom) > 0L) {
    p_inset <- p_inset +
      geom_rug(
        data = rug_zoom,
        aes(x = signed_distance_m),
        inherit.aes = FALSE,
        colour = GSVI_COLOUR,
        alpha = 0.2,
        length = unit(0.04, "npc")
      )
  }

  # Larger inset (left + down); soft band marks the zoom window (no 引线)
  inset_npc <- list(left = 0.34, bottom = 0.26, right = 0.985, top = 0.985)

  p_with_inset <- build_main_plot(
    highlight_zoom = TRUE,
    x_min = x_min,
    x_max = INSET_XMAX_M
  ) +
    inset_element(
      p_inset,
      left = inset_npc$left,
      bottom = inset_npc$bottom,
      right = inset_npc$right,
      top = inset_npc$top,
      align_to = "panel",
      clip = TRUE
    )

  out_inset <- file.path(FIG_DIR, "Signed_distance_gam_curve_inset.png")
  ggsave(out_inset, p_with_inset, width = 9.2, height = 5.6, dpi = 300)
  message("Wrote ", out_inset, " (inset: ", inset_title, ")")
}

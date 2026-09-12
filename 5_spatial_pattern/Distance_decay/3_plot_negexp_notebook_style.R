#!/usr/bin/env Rscript
# Notebook-style NegExp figures at panorama level
# Mirrors del/SVI_distance_use.ipynb Chunks 1–2 (NegExp_Images_vs_AllPoints + NegExp_derivative)

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(grid)
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
DECAY_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "Distance_decay")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "Distance_decay")

cdf_path <- file.path(DECAY_DIR, "Nairobi_distance_decay_cdf.csv")
if (!file.exists(cdf_path)) {
  stop(
    "Missing ", cdf_path, "\n",
    "Run: python 5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

WASTE_COLOUR <- "#7b5032"
SVI_COLOUR <- "#e4c8b0"

# Full grid like notebook buffer_distances = np.arange(0, 3000, 10)
cdf <- read.csv(cdf_path)

emp <- bind_rows(
  cdf |> transmute(
    distance_m,
    proportion = emp_waste_positive,
    series = "Waste-positive panoids"
  ),
  cdf |> transmute(
    distance_m,
    proportion = emp_all_gsvi,
    series = "SVI panoids"
  )
)

neg_exp <- function(x, a, b) a * (1 - exp(-b * x))
neg_exp_deriv <- function(x, a, b) a * b * exp(-b * x)

fit_one <- function(df) {
  fit <- nls(
    proportion ~ a * (1 - exp(-b * distance_m)),
    data = df,
    start = list(a = 1, b = 0.001),
    control = nls.control(maxiter = 500, warnOnly = TRUE)
  )
  sm <- summary(fit)
  coefs <- coef(fit)
  a <- unname(coefs[["a"]])
  b <- unname(coefs[["b"]])
  p_b <- sm$coefficients["b", "Pr(>|t|)"]
  pred <- as.numeric(predict(fit))
  ss_res <- sum((df$proportion - pred)^2)
  ss_tot <- sum((df$proportion - mean(df$proportion))^2)
  r2 <- 1 - ss_res / ss_tot
  x_half <- log(2) / b
  list(
    a = a, b = b, r2 = r2, p_b = p_b,
    x_half = x_half,
    y_half = neg_exp(x_half, a, b),
    peak_slope = neg_exp_deriv(0, a, b),
    y_at_half_deriv = neg_exp_deriv(x_half, a, b)
  )
}

fits <- emp |>
  group_by(series) |>
  group_modify(~ {
    f <- fit_one(.x)
    tibble(
      a = f$a, b = f$b, r2 = f$r2, p_b = f$p_b,
      x_half = f$x_half, y_half = f$y_half,
      peak_slope = f$peak_slope, y_at_half_deriv = f$y_at_half_deriv
    )
  }) |>
  ungroup()

message("Fitted NegExp (panorama-level):")
print(fits)

x_fit <- seq(0, 2000, length.out = 300)
fit_curves <- fits |>
  rowwise() |>
  reframe(
    series,
    distance_m = x_fit,
    proportion = neg_exp(x_fit, a, b),
    deriv = neg_exp_deriv(x_fit, a, b)
  )

# Observed points on plot range (notebook scatters all fit x; we keep 0–2000)
emp_plot <- emp |> filter(distance_m <= 2000)

theme_notebook <- function(base_size = 14) {
  theme_classic(base_size = base_size, base_family = "sans") +
    theme(
      plot.background = element_rect(fill = "white", colour = NA),
      panel.background = element_rect(fill = "white", colour = NA),
      plot.title = element_text(
        face = "bold", hjust = 0.5, size = base_size + 4,
        lineheight = 1.05, margin = margin(b = 10)
      ),
      axis.title = element_text(size = base_size),
      axis.text = element_text(size = base_size - 2, colour = "black"),
      legend.title = element_text(size = base_size - 1, face = "bold"),
      legend.text = element_text(size = base_size - 2),
      legend.background = element_rect(fill = alpha("white", 0.92), colour = "grey70"),
      legend.key = element_rect(fill = "white", colour = NA),
      plot.margin = margin(10, 12, 8, 10)
    )
}

# ---- Build combined legend aesthetics for cumulative plot ----
# Four legend keys: Observed / Fit × two series
obs_waste <- emp_plot |> filter(series == "Waste-positive panoids")
obs_svi <- emp_plot |> filter(series == "SVI panoids")
fit_waste <- fit_curves |> filter(series == "Waste-positive panoids")
fit_svi <- fit_curves |> filter(series == "SVI panoids")

ann_cum <- fits |>
  mutate(
    label = sprintf("%s\nR\u00b2 = %.3f\na = %.3f", series, r2, a),
    x_lab = ifelse(
      series == "Waste-positive panoids",
      pmin(x_half + 40, 700),
      pmin(x_half + 40, 1550)
    ),
    y_lab = ifelse(
      series == "Waste-positive panoids",
      pmax(y_half - 0.12, 0.18),
      pmin(y_half + 0.18, 0.92)
    )
  )

p_cum <- ggplot() +
  geom_point(
    data = obs_svi,
    aes(x = distance_m, y = proportion),
    colour = SVI_COLOUR, shape = 1, size = 1.8, alpha = 0.65
  ) +
  geom_point(
    data = obs_waste,
    aes(x = distance_m, y = proportion),
    colour = WASTE_COLOUR, shape = 16, size = 1.7, alpha = 0.65
  ) +
  geom_line(
    data = fit_svi,
    aes(x = distance_m, y = proportion),
    colour = SVI_COLOUR, linewidth = 1.05
  ) +
  geom_line(
    data = fit_waste,
    aes(x = distance_m, y = proportion),
    colour = WASTE_COLOUR, linewidth = 1.05
  ) +
  geom_vline(
    data = fits,
    aes(xintercept = x_half, colour = series),
    linetype = "dashed", linewidth = 0.55, alpha = 0.55, show.legend = FALSE
  ) +
  geom_point(
    data = fits,
    aes(x = x_half, y = y_half, fill = series),
    shape = 21, size = 3.4, colour = "black", stroke = 0.7, show.legend = FALSE
  ) +
  geom_text(
    data = ann_cum,
    aes(x = x_lab, y = y_lab, label = label, colour = series),
    hjust = 0, vjust = 1, size = 4.3, lineheight = 0.95, show.legend = FALSE
  ) +
  # Invisible layers only for a clean 4-key legend
  geom_point(
    data = tibble(
      distance_m = -100,
      proportion = -1,
      key = factor(
        c(
          "Observed (SVI panoids)",
          "Neg. Exp. Fit (SVI panoids)",
          "Observed (waste-positive)",
          "Neg. Exp. Fit (waste-positive)"
        ),
        levels = c(
          "Observed (SVI panoids)",
          "Neg. Exp. Fit (SVI panoids)",
          "Observed (waste-positive)",
          "Neg. Exp. Fit (waste-positive)"
        )
      )
    ),
    aes(x = distance_m, y = proportion, colour = key, shape = key),
    size = 2.5
  ) +
  scale_colour_manual(
    name = "SVI panoids vs waste-positive",
    values = c(
      "Observed (SVI panoids)" = SVI_COLOUR,
      "Neg. Exp. Fit (SVI panoids)" = SVI_COLOUR,
      "Observed (waste-positive)" = WASTE_COLOUR,
      "Neg. Exp. Fit (waste-positive)" = WASTE_COLOUR,
      "Waste-positive panoids" = WASTE_COLOUR,
      "SVI panoids" = SVI_COLOUR
    ),
    breaks = c(
      "Observed (SVI panoids)",
      "Neg. Exp. Fit (SVI panoids)",
      "Observed (waste-positive)",
      "Neg. Exp. Fit (waste-positive)"
    )
  ) +
  scale_shape_manual(
    name = "SVI panoids vs waste-positive",
    values = c(
      "Observed (SVI panoids)" = 1,
      "Neg. Exp. Fit (SVI panoids)" = 95,
      "Observed (waste-positive)" = 16,
      "Neg. Exp. Fit (waste-positive)" = 95
    ),
    breaks = c(
      "Observed (SVI panoids)",
      "Neg. Exp. Fit (SVI panoids)",
      "Observed (waste-positive)",
      "Neg. Exp. Fit (waste-positive)"
    )
  ) +
  scale_fill_manual(
    values = c(
      "Waste-positive panoids" = WASTE_COLOUR,
      "SVI panoids" = SVI_COLOUR
    ),
    guide = "none"
  ) +
  coord_cartesian(xlim = c(0, 2000), ylim = c(0, 1.05), clip = "on") +
  labs(
    title = "Negative Exponential Fit\nWaste Proximity to Urban Poor",
    x = "Distance to urban poor boundary (m)",
    y = "Proportion within distance"
  ) +
  theme_notebook(14) +
  theme(legend.position = c(0.72, 0.22)) +
  guides(
    colour = guide_legend(
      override.aes = list(
        shape = c(1, 95, 16, 95),
        size = c(3, 4, 3, 4),
        linetype = c(0, 1, 0, 1),
        alpha = 1
      )
    ),
    shape = "none"
  )

ggsave(
  file.path(FIG_DIR, "NegExp_Panoids_vs_WastePositive.png"),
  p_cum,
  width = 8,
  height = 8,
  dpi = 600,
  bg = "white"
)

# ---------------------------------------------------------------------------
# Derivative figure
# ---------------------------------------------------------------------------
ann_der <- fits |>
  mutate(
    p_str = ifelse(p_b < 0.001, "< 0.001", sprintf("= %.3f", p_b)),
    label = sprintf(
      "%s\nx\u00bd = %.0f m\nSlope = %.2f \u00d710\u207b\u00b2\np %s",
      series, x_half, peak_slope * 100, p_str
    ),
    x_lab = pmin(x_half + 30, 1500),
    y_lab = y_at_half_deriv
  )

legend_labels <- setNames(
  sprintf("%s (x\u00bd \u2248 %.0f m)", fits$series, fits$x_half),
  fits$series
)

p_der <- ggplot() +
  geom_line(
    data = fit_curves,
    aes(x = distance_m, y = deriv, colour = series),
    linewidth = 1.15
  ) +
  geom_vline(
    data = fits,
    aes(xintercept = x_half, colour = series),
    linetype = "dashed", linewidth = 0.55, alpha = 0.65, show.legend = FALSE
  ) +
  geom_text(
    data = ann_der,
    aes(x = x_lab, y = y_lab, label = label, colour = series),
    hjust = 0, vjust = 0, size = 4.1, lineheight = 0.95, show.legend = FALSE
  ) +
  scale_colour_manual(
    name = "SVI panoids vs waste-positive",
    values = c(
      "Waste-positive panoids" = WASTE_COLOUR,
      "SVI panoids" = SVI_COLOUR
    ),
    labels = legend_labels
  ) +
  coord_cartesian(xlim = c(0, 2000), clip = "on") +
  labs(
    title = "Neg. Exponential Derivative:\nRate of Change vs. Distance to Urban Poor",
    x = "Distance to urban poor boundary (m)",
    y = "Change in proportion per metre"
  ) +
  theme_notebook(14) +
  theme(legend.position = c(0.72, 0.82))

ggsave(
  file.path(FIG_DIR, "NegExp_derivative.png"),
  p_der,
  width = 10,
  height = 5.2,
  dpi = 600,
  bg = "white"
)

params_out <- fits |>
  transmute(
    series,
    a = round(a, 6),
    b = round(b, 8),
    r2 = round(r2, 4),
    half_distance_m = round(x_half, 2),
    peak_slope = round(peak_slope, 8),
    p_value_b = p_b
  )
write.csv(
  params_out,
  file.path(DECAY_DIR, "Nairobi_negexp_notebook_style.csv"),
  row.names = FALSE
)

message("Wrote ", file.path(FIG_DIR, "NegExp_Panoids_vs_WastePositive.png"))
message("Wrote ", file.path(FIG_DIR, "NegExp_derivative.png"))
message("Wrote ", file.path(DECAY_DIR, "Nairobi_negexp_notebook_style.csv"))
message("Done.")

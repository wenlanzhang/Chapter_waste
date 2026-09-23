#!/usr/bin/env Rscript
# Settlement association figures: density / rates / NNR (urban-poor boundary)
# Distance-decay / NegExp figures: see Distance_decay/

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
SETTLE_DIR <- file.path(DATA_ROOT, "5_spatial_pattern", "settlement")
FIG_DIR <- file.path(script_dir, "..", "..", "Figure", "5_spatial_pattern", "settlement")

WASTE_COLOUR <- "#6B4226"
GSVI_COLOUR <- "#C9A27F"
INSIDE_COLOUR <- "#496142"
OUTSIDE_COLOUR <- "#A67B5B"

density_path <- file.path(SETTLE_DIR, "Nairobi_settlement_density.csv")
contingency_path <- file.path(SETTLE_DIR, "Nairobi_settlement_contingency.csv")
nnr_path <- file.path(SETTLE_DIR, "Nairobi_nnr_observation_frame_summary.csv")
nnr_null_path <- file.path(SETTLE_DIR, "Nairobi_nnr_null_mean_nn_distances.csv")

required <- c(density_path, contingency_path)
missing <- required[!file.exists(required)]
if (length(missing)) {
  stop(
    "Missing settlement outputs. Run:\n",
    "  python 5_spatial_pattern/settlement/2_settlement_association.py\n",
    paste(missing, collapse = "\n")
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

density <- read.csv(density_path)
contingency <- read.csv(contingency_path)

theme_chapter <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "sans") +
    theme(
      plot.title = element_text(face = "bold", hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(hjust = 0.5, colour = "#5C6B7A"),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      legend.title = element_blank()
    )
}

# --- Density bars ---
dens_df <- tibble(
  zone = c("Inside settlements", "Outside settlements"),
  density = c(density$density_inside_per_km2[1], density$density_outside_per_km2[1])
)

p_dens <- ggplot(dens_df, aes(x = zone, y = density, fill = zone)) +
  geom_col(width = 0.65, colour = NA) +
  scale_fill_manual(values = c(
    "Inside settlements" = INSIDE_COLOUR,
    "Outside settlements" = OUTSIDE_COLOUR
  )) +
  labs(
    title = "Area-Normalised Waste-Positive Panorama Density",
    subtitle = sprintf(
      "PCR = %.2f | density ratio (in/out) = %.2f",
      density$pcr[1],
      density$density_ratio[1]
    ),
    x = NULL,
    y = "Waste-positive panoids per km²"
  ) +
  theme_chapter() +
  theme(legend.position = "none")

ggsave(
  file.path(FIG_DIR, "Settlement_area_normalised_density.png"),
  p_dens,
  width = 7,
  height = 5,
  dpi = 600,
  bg = "white"
)

# --- Contingency shares among waste-positive (composition) ---
waste_row <- contingency |> filter(waste_status == "waste_positive")
cont_df <- tibble(
  zone = c("Inside mapped settlements", "Outside mapped settlements"),
  n = c(waste_row$inside_settlement[1], waste_row$outside_settlement[1])
) |>
  mutate(share = n / sum(n))

p_cont <- ggplot(cont_df, aes(x = zone, y = share, fill = zone)) +
  geom_col(width = 0.65, colour = NA) +
  geom_text(aes(label = sprintf("%s\n(%.1f%%)", comma(n), 100 * share)),
            vjust = -0.2, size = 3.3, colour = "#2f2f2f") +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, 1.05)) +
  scale_fill_manual(values = c(
    "Inside mapped settlements" = INSIDE_COLOUR,
    "Outside mapped settlements" = OUTSIDE_COLOUR
  )) +
  labs(
    title = "Where Waste-Positive Panoramas Are Located",
    subtitle = "Composition of the 2,696 positives (not a location-specific risk)",
    x = NULL,
    y = "Share of waste-positive panoramas"
  ) +
  theme_chapter() +
  theme(legend.position = "none")

ggsave(
  file.path(FIG_DIR, "Settlement_waste_positive_share.png"),
  p_cont,
  width = 7,
  height = 5,
  dpi = 600,
  bg = "white"
)

# --- Positive rates by location ---
chi2_path <- file.path(SETTLE_DIR, "Nairobi_settlement_chisquare.csv")
if (file.exists(chi2_path)) {
  assoc <- read.csv(chi2_path)
  rate_df <- tibble(
    zone = factor(
      c("Inside mapped settlements", "Outside mapped settlements"),
      levels = c("Inside mapped settlements", "Outside mapped settlements")
    ),
    n_positive = c(assoc$waste_inside_a[1], assoc$waste_outside_c[1]),
    n_all = c(
      assoc$waste_inside_a[1] + assoc$nonwaste_inside_b[1],
      assoc$waste_outside_c[1] + assoc$nonwaste_outside_d[1]
    ),
    rate = c(assoc$positive_rate_inside[1], assoc$positive_rate_outside[1])
  )

  pr <- assoc$prevalence_ratio[1]
  p_rate <- ggplot(rate_df, aes(x = zone, y = rate, fill = zone)) +
    geom_col(width = 0.62, colour = NA) +
    geom_text(
      aes(
        label = sprintf(
          "%s / %s\n(%.2f%%)",
          comma(n_positive),
          comma(n_all),
          100 * rate
        )
      ),
      vjust = -0.15,
      size = 3.4,
      colour = "#2f2f2f",
      lineheight = 0.95
    ) +
    scale_y_continuous(
      labels = percent_format(accuracy = 1),
      limits = c(0, max(rate_df$rate) * 1.28),
      expand = c(0, 0)
    ) +
    scale_fill_manual(values = c(
      "Inside mapped settlements" = INSIDE_COLOUR,
      "Outside mapped settlements" = OUTSIDE_COLOUR
    )) +
    labs(
      title = "Waste-Positive Rate by Settlement Location",
      subtitle = sprintf(
        "Prevalence ratio = %.2f  |  a panorama inside was %.2f times as likely to be waste-positive",
        pr,
        pr
      ),
      x = NULL,
      y = "Waste-positive panoramas / all GSVI panoramas in zone"
    ) +
    theme_chapter() +
    theme(legend.position = "none")

  ggsave(
    file.path(FIG_DIR, "Settlement_waste_positive_rate.png"),
    p_rate,
    width = 7.5,
    height = 5.2,
    dpi = 600,
    bg = "white"
  )
  message("Wrote ", file.path(FIG_DIR, "Settlement_waste_positive_rate.png"))

  p_rate_panel <- p_rate +
    labs(
      title = "A. Location-specific positive rate",
      subtitle = sprintf("Denominators = panoramas in each zone  |  PR = %.2f", pr),
      y = "Positive rate"
    ) +
    theme(plot.title = element_text(size = 11), plot.subtitle = element_text(size = 9))

  p_comp_panel <- p_cont +
    labs(
      title = "B. Composition of all positives",
      subtitle = "Denominators = all waste-positive panoramas",
      y = "Share of positives"
    ) +
    theme(plot.title = element_text(size = 11), plot.subtitle = element_text(size = 9))

  p_compare <- (p_rate_panel + p_comp_panel) +
    plot_annotation(
      title = "Settlement association: rates versus composition",
      subtitle = "For inequality between locations, use A (13.34% vs 3.01%), not B (18.6% vs 81.4%)"
    ) &
    theme(
      plot.title = element_text(face = "bold", hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(hjust = 0.5, colour = "#5C6B7A")
    )

  ggsave(
    file.path(FIG_DIR, "Settlement_rate_vs_composition.png"),
    p_compare,
    width = 11.5,
    height = 5.4,
    dpi = 600,
    bg = "white"
  )
  message("Wrote ", file.path(FIG_DIR, "Settlement_rate_vs_composition.png"))
}

# --- Optional NNR null histogram ---
if (file.exists(nnr_path) && file.exists(nnr_null_path)) {
  nnr <- read.csv(nnr_path)
  null_df <- read.csv(nnr_null_path)
  p_nnr <- ggplot(null_df, aes(x = d_null_m)) +
    geom_histogram(bins = 40, fill = GSVI_COLOUR, colour = "white", linewidth = 0.2) +
    geom_vline(xintercept = nnr$d_obs_m[1], colour = WASTE_COLOUR, linewidth = 1) +
    labs(
      title = "Observation-Frame Nearest-Neighbour Null",
      subtitle = sprintf(
        "Observed mean NN = %.1f m | null mean = %.1f m (SD %.1f) | NNR = %.3f | p = %.4f",
        nnr$d_obs_m[1],
        nnr$null_mean_m[1],
        if ("null_std_m" %in% names(nnr)) nnr$null_std_m[1] else NA_real_,
        nnr$nnr_observation_frame[1],
        nnr$p_value_one_sided[1]
      ),
      x = "Mean nearest-neighbour distance under random draws (m)",
      y = "Count of permutations"
    ) +
    theme_chapter()

  ggsave(
    file.path(FIG_DIR, "NNR_observation_frame_null.png"),
    p_nnr,
    width = 8,
    height = 5,
    dpi = 600,
    bg = "white"
  )
  message("Wrote ", file.path(FIG_DIR, "NNR_observation_frame_null.png"))
}

message("Wrote ", file.path(FIG_DIR, "Settlement_area_normalised_density.png"))
message("Wrote ", file.path(FIG_DIR, "Settlement_waste_positive_share.png"))
message("Done.")

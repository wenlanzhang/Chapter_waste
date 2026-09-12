#!/usr/bin/env Rscript
# Optional SE analysis — correlation bar + scatter panels

# suppressWarnings: packages may be built under a newer R than this session
suppressWarnings(suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(readr)
  library(scales)
  library(patchwork)
}))

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
repo_root <- normalizePath(file.path(script_dir, ".."))
source(file.path(repo_root, "R", "chapter_paths.R"))
source(file.path(repo_root, "R", "chapter_colours.R"))

year <- 2019
args <- commandArgs(trailingOnly = TRUE)
if (length(args) >= 1) {
  year <- as.integer(args[[1]])
}

DATA_DIR <- file.path(chapter_data_root, "99_optional_SE_analysis")
TABLE_DIR <- file.path(DATA_DIR, "thesis_table")
FIG_DIR <- file.path(repo_root, "Figure", "99_optional_SE_analysis")
CORR_CSV <- file.path(TABLE_DIR, sprintf("se_waste_correlations_%d.csv", year))
ADMIN_CSV <- file.path(DATA_DIR, sprintf("Nairobi_admin_se_waste_%d.csv", year))

if (!file.exists(CORR_CSV) || !file.exists(ADMIN_CSV)) {
  stop(
    "Missing correlation/admin tables.\n",
    "Run: python 99_optional_SE_analysis/1_admin_se_waste_join.py"
  )
}

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

corr <- read_csv(CORR_CSV, show_col_types = FALSE) %>%
  arrange(desc(abs(pearson_r))) %>%
  mutate(
    covariate = factor(covariate, levels = rev(covariate)),
    sig = ifelse(p_value < 0.05, "p < 0.05", "n.s.")
  )

admin <- read_csv(ADMIN_CSV, show_col_types = FALSE) %>%
  filter(has_svi)

theme_se <- theme_minimal(base_size = 12) +
  theme(
    plot.title = element_text(face = "bold", colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(colour = CHAPTER_TITLE_COLOUR),
    axis.title = element_text(colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(colour = CHAPTER_AXIS_COLOUR),
    panel.grid.minor = element_blank()
  )

message("Plotting correlation bars...")
p_bar <- ggplot(corr, aes(x = pearson_r, y = covariate, fill = sig)) +
  geom_col(width = 0.7) +
  geom_vline(xintercept = 0, colour = "grey40", linewidth = 0.4) +
  scale_fill_manual(
    values = c("p < 0.05" = CHAPTER_SEQ_HIGH, "n.s." = "grey70"),
    name = NULL
  ) +
  scale_x_continuous(limits = c(-1, 1), breaks = seq(-1, 1, 0.25)) +
  labs(
    title = "Pearson correlation with waste-positive rate",
    subtitle = sprintf("Admin units with ≥1 GSVI panoid · SE year %d", year),
    x = "Pearson r",
    y = NULL
  ) +
  theme_se

out_bar <- file.path(FIG_DIR, sprintf("SE_correlation_bars_%d.png", year))
ggsave(out_bar, p_bar, width = 7.5, height = 6.5, dpi = 300, bg = "white")
message("Wrote ", out_bar)

scatter_vars <- intersect(c("density_pop", "grdi", "nr_buildings", "rwi_weight"), names(admin))
if (length(scatter_vars) == 0) {
  stop("No scatter covariates found in admin CSV")
}

make_scatter <- function(var) {
  sub <- admin %>%
    transmute(
      x = .data[[var]],
      y = waste_positive_rate
    ) %>%
    filter(is.finite(x), is.finite(y))
  r <- cor(sub$x, sub$y, use = "complete.obs")
  ggplot(sub, aes(x = x, y = y)) +
    geom_point(alpha = 0.55, colour = CHAPTER_SEQ_HIGH, size = 1.8) +
    geom_smooth(
      method = "lm",
      formula = y ~ x,
      se = TRUE,
      colour = "grey20",
      linewidth = 0.6
    ) +
    labs(
      title = var,
      subtitle = sprintf("r = %.3f · n = %d", r, nrow(sub)),
      x = var,
      y = "Waste-positive rate"
    ) +
    theme_se +
    theme(plot.title = element_text(size = 11), plot.subtitle = element_text(size = 9))
}

message("Plotting scatter panel...")
plots <- lapply(scatter_vars, make_scatter)
p_scatter <- wrap_plots(plots, ncol = 2) +
  plot_annotation(
    title = "Waste-positive rate vs selected socio-economic covariates",
    subtitle = sprintf("Admin units with SVI coverage · SE year %d", year)
  )
out_scatter <- file.path(FIG_DIR, sprintf("SE_scatter_panel_%d.png", year))
ggsave(out_scatter, p_scatter, width = 9.5, height = 8, dpi = 300, bg = "white")
message("Wrote ", out_scatter)
message("Done.")

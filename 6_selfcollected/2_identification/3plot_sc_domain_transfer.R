#!/usr/bin/env Rscript
# Step 6.2b — does the detector transfer to locally collected imagery?
#   3_SC_domain_transfer.png
#     (a) recall on each held-out set against the SC share of the training mix
#     (b) mAP@0.50 on each set — where the domain gap actually is
#     (c) the gap itself (GSVI − SC), for both metrics
#
# The expected story was a recall gap that SC training closes. Panel (a) shows
# there is no recall gap to close. Panels (b) and (c) show where the gap really
# sits and how much of it local training data recovers.
#
# Inputs (6_selfcollected/2_identification/, from 3_sc_domain_transfer.py):
#   3_sc_domain_transfer.csv

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
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "2_identification")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "2_identification")

LONG_CSV <- file.path(DATA_DIR, "3_sc_domain_transfer.csv")
OUT_PATH <- file.path(FIG_DIR, "3_SC_domain_transfer.png")

GSVI_COL <- "#BDB3A8"
SC_COL <- "#6B4226"
GAP_COL <- "#496142"

if (!file.exists(LONG_CSV)) {
  stop("Missing ", LONG_CSV,
       " — run 6_selfcollected/2_identification/3_sc_domain_transfer.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

long <- read.csv(LONG_CSV, stringsAsFactors = FALSE)
n_gsvi <- long$n_images[long$domain == "gsvi"][1]
n_sc <- long$n_images[long$domain == "sc"][1]

DOMAIN_LABELS <- c(
  gsvi = sprintf("GSVI held-out (n = %s)", comma(n_gsvi)),
  sc = sprintf("Self-collected held-out (n = %s)", comma(n_sc))
)
DOMAIN_COLOURS <- setNames(c(GSVI_COL, SC_COL), DOMAIN_LABELS)

long <- long |> mutate(Domain = factor(DOMAIN_LABELS[domain], levels = DOMAIN_LABELS))
shares <- sort(unique(long$sc_share))

base_theme <- function() {
  theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      legend.text = element_text(size = 8.4)
    )
}

line_panel <- function(metric, title, subtitle, ylab, pct) {
  d <- long |> mutate(value = .data[[metric]], shown = if (pct) 100 * value else value)
  ggplot(d, aes(sc_share, shown, colour = Domain, group = Domain)) +
    geom_line(linewidth = 0.9) +
    geom_point(size = 2.2) +
    scale_colour_manual(name = NULL, values = DOMAIN_COLOURS) +
    scale_x_continuous(breaks = shares, labels = paste0(shares, "%")) +
    scale_y_continuous(
      limits = c(if (pct) 0 else 0, if (pct) 108 else max(d$shown) * 1.15),
      labels = if (pct) label_percent(scale = 1) else label_number(accuracy = 0.1)
    ) +
    labs(title = title, subtitle = subtitle,
         x = "Self-collected share of the YOLO training set", y = ylab) +
    base_theme()
}

p_recall <- line_panel(
  "recall", "(a) Recall — no domain gap to close",
  "Recall on self-collected imagery is at or above GSVI at every training mix",
  "Recall (%)", TRUE
)

p_map <- line_panel(
  "mAP50", "(b) mAP@0.50 — where the gap actually is",
  "Localisation quality is far lower on self-collected imagery, and rises as SC enters training",
  "mAP@0.50", FALSE
)

# --- (c) the gap itself -------------------------------------------------------
gap <- long |>
  select(sc_share, domain, recall, mAP50) |>
  pivot_longer(c(recall, mAP50), names_to = "metric", values_to = "value") |>
  pivot_wider(names_from = domain, values_from = value) |>
  mutate(
    gap = gsvi - sc,
    metric = factor(
      if_else(metric == "recall", "Recall gap (pp)", "mAP@0.50 gap"),
      levels = c("Recall gap (pp)", "mAP@0.50 gap")
    ),
    shown = if_else(metric == "Recall gap (pp)", 100 * gap, gap)
  )

p_gap <- ggplot(gap, aes(sc_share, shown)) +
  geom_hline(yintercept = 0, colour = "grey45", linewidth = 0.4) +
  geom_col(fill = GAP_COL, width = 14) +
  geom_text(aes(label = sprintf("%+.2f", shown),
                vjust = if_else(shown >= 0, -0.4, 1.3)),
            size = 2.5, fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  facet_wrap(~metric, nrow = 1, scales = "free_y") +
  scale_x_continuous(breaks = shares, labels = paste0(shares, "%")) +
  labs(
    title = "(c) The domain gap, GSVI minus self-collected",
    subtitle = "Above zero = the detector does better on GSVI. Recall sits below zero throughout.",
    x = "Self-collected share of the YOLO training set", y = NULL
  ) +
  base_theme() +
  theme(strip.text = element_text(face = "bold", size = 9, colour = CHAPTER_AXIS_COLOUR),
        panel.grid.major.x = element_blank())

fig <- ((p_recall | p_map) / p_gap) +
  plot_layout(heights = c(1.15, 1), guides = "collect") +
  plot_annotation(
    title = "Does the detector transfer to locally collected imagery?",
    subtitle = sprintf(
      "Two independent held-out sets scored with the same five detectors | GSVI %s images, self-collected %s images",
      comma(n_gsvi), comma(n_sc)
    ),
    caption = paste0(
      "The mitigation claim this supports is not \"recall increased\" — recall on self-collected imagery is already at or above GSVI without any SC training data.\n",
      "It is that supplementary local training data reduced source-specific localisation loss: mAP@0.50 on self-collected imagery rises 0.160 → 0.313 (+96%), closing 40% of the domain gap, while GSVI performance is unharmed.\n",
      "The two sets differ in size and composition (180 images, 90/90 vs 107 images, 55/52), so the levels are not directly comparable; the trends across training mixes are."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8)),
      legend.position = "bottom"
    )
  ) & theme(legend.position = "bottom")

ggsave(OUT_PATH, fig, width = 12.5, height = 7.4, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

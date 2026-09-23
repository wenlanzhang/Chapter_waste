#!/usr/bin/env Rscript
# Step 4 figure 2 — independent local validation of the 100 m indicator.
#   2_Nairobi_indicator_validation_grid100m_gsvi.png
#     A. Binary agreement with the crowd judgement, split by indicator provenance
#     B. 3-class crowd x indicator confusion matrix over all validated cells
#
# Input: 4_100m/4_validation_detail.csv + 5_validation_confusion.csv (2_validation.py)

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
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "4_100m")
DETAIL_CSV <- file.path(DATA_DIR, "4_validation_detail.csv")
CONF_CSV <- file.path(DATA_DIR, "5_validation_confusion.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "4_100m")

for (f in c(DETAIL_CSV, CONF_CSV)) {
  if (!file.exists(f)) stop("Missing ", f, " — run 4_100m/2_validation.py first")
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

detail <- read.csv(DETAIL_CSV, stringsAsFactors = FALSE)

# Only the three headline subsets go in the figure; the distance bands stay in
# the table, where their small counts can be read alongside n.
SUBSETS <- c("All validated cells", "Direct observation", "Interpolated support")
SUBSET_LABELS <- c(
  "All validated cells" = "All\nvalidated",
  "Direct observation" = "Direct\nobservation",
  "Interpolated support" = "Interpolated\nsupport"
)
SUBSET_COLOURS <- c(
  "All validated cells" = "#C9A27F",
  "Direct observation" = "#5F6F5A",
  "Interpolated support" = "#8B5A3C"
)

METRIC_KEYS <- c("accuracy", "precision", "recall")
METRIC_LABELS <- c(accuracy = "Agreement", precision = "Precision", recall = "Recall")

bars <- detail |>
  filter(subset %in% SUBSETS) |>
  mutate(subset = factor(subset, levels = SUBSETS)) |>
  select(subset, n, all_of(METRIC_KEYS)) |>
  pivot_longer(all_of(METRIC_KEYS), names_to = "metric_key", values_to = "value") |>
  mutate(
    metric = factor(METRIC_LABELS[metric_key], levels = unname(METRIC_LABELS)),
    pct = 100 * value
  )

n_by_subset <- detail |> filter(subset %in% SUBSETS) |> select(subset, n)
subset_caption <- paste(
  sprintf("%s n = %s", SUBSETS, comma(n_by_subset$n[match(SUBSETS, n_by_subset$subset)])),
  collapse = " | "
)

p_bars <- ggplot(bars, aes(x = metric, y = pct, fill = subset)) +
  geom_col(position = position_dodge(width = 0.78), width = 0.68, colour = "white", linewidth = 0.4) +
  geom_text(
    aes(label = sprintf("%.0f", pct)),
    position = position_dodge(width = 0.78),
    vjust = -0.45, size = 3.0, fontface = "bold", colour = CHAPTER_AXIS_COLOUR
  ) +
  scale_fill_manual(values = SUBSET_COLOURS, labels = SUBSET_LABELS[SUBSETS], name = NULL) +
  scale_y_continuous(limits = c(0, 100), breaks = seq(0, 100, 25), expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "A. Agreement by indicator provenance",
    subtitle = "Crowd judgement (waste present vs not) as reference",
    x = NULL, y = "Per cent"
  ) +
  map_theme() +
  theme(
    panel.grid.major.x = element_blank(),
    plot.title = element_text(face = "bold", size = 11.5, hjust = 0, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, hjust = 0, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.text.x = element_text(size = 9.5, face = "bold", colour = CHAPTER_AXIS_COLOUR),
    axis.title.y = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    legend.position = "bottom",
    legend.justification = "center",
    legend.background = element_blank(),
    legend.box.background = element_blank(),
    legend.text = element_text(size = 8.4, colour = CHAPTER_AXIS_COLOUR)
  )

# --- B. 3-class confusion ----------------------------------------------------
CLASS_LEVELS <- c("Low", "Medium", "High")
conf <- read.csv(CONF_CSV, stringsAsFactors = FALSE, check.names = FALSE)
names(conf)[1] <- "crowd"
conf_long <- conf |>
  pivot_longer(-crowd, names_to = "indicator", values_to = "n") |>
  mutate(
    crowd = factor(crowd, levels = CLASS_LEVELS),
    indicator = factor(indicator, levels = CLASS_LEVELS),
    text_colour = chocolate_label_colour(n, limits = c(0, max(n)), trans = "sqrt")
  )
total <- sum(conf_long$n)
exact <- sum(conf_long$n[conf_long$crowd == conf_long$indicator])

p_conf <- ggplot(conf_long, aes(x = indicator, y = crowd, fill = n)) +
  geom_tile(colour = "white", linewidth = 1.1) +
  geom_text(aes(label = comma(n), colour = text_colour), size = 4.2, fontface = "bold") +
  scale_colour_identity() +
  scale_fill_gradientn(colours = CHOCOLATE_PALETTE, limits = c(0, max(conf_long$n)),
                       trans = "sqrt", guide = "none") +
  scale_y_discrete(limits = rev(CLASS_LEVELS)) +
  labs(
    title = "B. Validation result vs predicted class",
    subtitle = sprintf("%s validated cells | %.1f%% exact agreement", comma(total), 100 * exact / total),
    x = "Predicted waste indicator class", y = "IDEAMaps crowd validation result"
  ) +
  map_theme() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 11.5, hjust = 0, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, hjust = 0, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.text = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.title = element_text(size = 9.5, face = "bold", colour = CHAPTER_AXIS_COLOUR),
    legend.position = "none"
  )

fig <- (p_bars | p_conf) +
  plot_layout(widths = c(1.15, 1)) +
  plot_annotation(
    title = "Independent local validation of the 100 m visible-waste indicator",
    subtitle = sprintf(
      "IDEAMaps crowd validation, Nairobi | one row per 100 m cell, maximum severity across validators | %s",
      subset_caption
    ),
    caption = paste0(
      "Precision is the share of cells the indicator calls waste that the crowd also calls waste. ",
      "It is the metric that separates the two provenance classes most sharply,\nbecause an interpolated cell can be assigned waste ",
      "with no imagery of its own to support the claim."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

out <- file.path(FIG_DIR, "2_Nairobi_indicator_validation_grid100m_gsvi.png")
ggsave(out, fig, width = 11, height = 5.6, dpi = 400, bg = "white")
message("Wrote ", out)
message("Done.")

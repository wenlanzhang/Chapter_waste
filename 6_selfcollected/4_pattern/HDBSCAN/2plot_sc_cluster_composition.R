#!/usr/bin/env Rscript
# Step 6.4a — are the hotspots still settlement hotspots?
#   2_SC_cluster_composition.png
#     one stacked bar per cluster, split by proximity to a mapped settlement,
#     one panel per arm, clusters ordered by their inside-settlement share
#
# Step 5a's claim is that the hotspots sit on settlements. If self-collected
# imagery were finding waste somewhere else, the bars in the right-hand panel
# would be visibly paler than the left.
#
# Inputs (6_selfcollected/4_pattern/HDBSCAN/, from 2_sc_cluster_settlement_context.py):
#   2_Nairobi_sc_cluster_composition_{gsvi,gsvi_selfcollected}.csv
#   thesis_table/table_6_4_cluster_context.csv

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

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "4_pattern", "HDBSCAN")
FIG_DIR <- file.path(script_dir, "../../..", "Figure", "6_selfcollected", "4_pattern", "HDBSCAN")
OUT_PATH <- file.path(FIG_DIR, "2_SC_cluster_composition.png")
TABLE_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_cluster_context.csv")

CATEGORIES <- c("Within Urban Poor", "0-250m buffer", "250-500m buffer", ">500m outside")
CAT_COLOURS <- c(
  "Within Urban Poor" = "#4D2D18",
  "0-250m buffer" = "#8B5A3C",
  "250-500m buffer" = "#C9A27F",
  ">500m outside" = "#E8DFD5"
)
ARMS <- c(gsvi = "GSVI", gsvi_selfcollected = "GSVI + SC")

comp_csv <- function(key) file.path(DATA_DIR, sprintf("2_Nairobi_sc_cluster_composition_%s.csv", key))
for (f in c(unname(sapply(names(ARMS), comp_csv)), TABLE_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f,
         " — run 6_selfcollected/4_pattern/HDBSCAN/2_sc_cluster_settlement_context.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

tbl <- read.csv(TABLE_CSV, stringsAsFactors = FALSE, check.names = FALSE)
get_row <- function(measure, col) tbl[[col]][tbl$Measure == measure]

read_arm <- function(key) {
  read.csv(comp_csv(key), stringsAsFactors = FALSE, check.names = FALSE) |>
    mutate(arm = ARMS[[key]])
}

comp <- bind_rows(lapply(names(ARMS), read_arm)) |>
  mutate(arm = factor(arm, levels = unname(ARMS)))

long <- comp |>
  pivot_longer(all_of(CATEGORIES), names_to = "category", values_to = "share") |>
  mutate(category = factor(category, levels = rev(CATEGORIES)))

build_panel <- function(arm_label) {
  d <- long |> filter(arm == arm_label)
  order_df <- comp |>
    filter(arm == arm_label) |>
    arrange(desc(`Within Urban Poor`), desc(`0-250m buffer`))
  d <- d |> mutate(cluster = factor(HDB_cluster, levels = rev(order_df$HDB_cluster)))

  n_clusters <- nrow(order_df)
  col <- if (arm_label == "GSVI") "GSVI" else "GSVI + SC"

  ggplot(d, aes(share, cluster, fill = category)) +
    geom_col(width = 0.78) +
    scale_fill_manual(name = NULL, values = CAT_COLOURS,
                      breaks = CATEGORIES, drop = FALSE) +
    scale_x_continuous(labels = percent_format(accuracy = 1),
                       expand = expansion(mult = c(0, 0))) +
    labs(
      title = sprintf("(%s) %s", if (arm_label == "GSVI") "a" else "b", arm_label),
      subtitle = sprintf(
        "%s clusters | %s contain a location inside a settlement | %s have a majority within 250 m",
        n_clusters,
        get_row("Clusters containing a location inside a settlement", col),
        get_row("Clusters with a majority within 250 m", col)
      ),
      x = "Share of clustered locations", y = "HDBSCAN cluster"
    ) +
    theme_minimal(base_size = 11) +
    theme(
      plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
      axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
      axis.text = element_text(size = 8, colour = CHAPTER_AXIS_COLOUR),
      panel.grid.major.y = element_blank(),
      panel.grid.minor = element_blank(),
      legend.position = "bottom"
    )
}

fig <- (build_panel("GSVI") | build_panel("GSVI + SC")) +
  plot_layout(guides = "collect") +
  plot_annotation(
    title = "Hotspot composition by proximity to urban-poor settlements",
    subtitle = sprintf(
      "Clustered locations inside a settlement: %s → %s | median distance %s → %s",
      get_row("Clustered locations inside a settlement", "GSVI"),
      get_row("Clustered locations inside a settlement", "GSVI + SC"),
      get_row("Median distance to a settlement", "GSVI"),
      get_row("Median distance to a settlement", "GSVI + SC")
    ),
    caption = paste0(
      "One bar per HDBSCAN cluster, ordered by inside-settlement share; noise points are excluded. Categories are mutually exclusive.\n",
      "The combined arm has fewer bars because neighbouring clusters merge, not because clusters were lost — 23 of the 24 GSVI hotspots are retained."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8)),
      legend.position = "bottom"
    )
  ) &
  theme(legend.position = "bottom")

ggsave(OUT_PATH, fig, width = 12, height = 6.4, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

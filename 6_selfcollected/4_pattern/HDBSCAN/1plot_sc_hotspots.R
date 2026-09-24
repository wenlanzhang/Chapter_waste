#!/usr/bin/env Rscript
# Step 6.4a — do the hotspots change when self-collected imagery is added?
#   1_SC_hotspot_comparison.png
#     (a) the two sets of convex-hull footprints, overlaid (scale only)
#     (b) GSVI cluster x combined cluster, for the 2,696 locations both runs
#         share — which hotspot each location's label moved to
#     (c) what the 149 added locations join
#
# Panel (b) is the argument, and it rests on cluster labels rather than on
# footprint geometry: every shared location carries a label from each run, so the
# agreement between the two labellings is measurable without choosing an overlap
# threshold or trusting the convex hull. A clean block-diagonal means the
# partition was preserved; rows collapsing onto one column are a merge.
#
# Inputs (6_selfcollected/4_pattern/HDBSCAN/, from 1_sc_hdbscan.py):
#   1_Nairobi_sc_hotspots_{gsvi,gsvi_selfcollected}_32737.gpkg
#   1_Nairobi_sc_hdbscan_gsvi_selfcollected_32737.gpkg
#   1_sc_hdbscan_label_transitions.csv
#   1_sc_hdbscan_new_locations.csv
#   thesis_table/table_6_4_hdbscan_{comparison,stability}.csv

suppressPackageStartupMessages({
  library(sf)
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
PREP_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "../../..", "Figure", "6_selfcollected", "4_pattern", "HDBSCAN")

HULLS_GSVI <- file.path(DATA_DIR, "1_Nairobi_sc_hotspots_gsvi_32737.gpkg")
HULLS_GSC <- file.path(DATA_DIR, "1_Nairobi_sc_hotspots_gsvi_selfcollected_32737.gpkg")
PTS_GSC <- file.path(DATA_DIR, "1_Nairobi_sc_hdbscan_gsvi_selfcollected_32737.gpkg")
TRANSITIONS_CSV <- file.path(DATA_DIR, "1_sc_hdbscan_label_transitions.csv")
NEW_OBS_CSV <- file.path(DATA_DIR, "1_sc_hdbscan_new_locations.csv")
COMPARISON_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_hdbscan_comparison.csv")
STABILITY_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_hdbscan_stability.csv")
OUT_PATH <- file.path(FIG_DIR, "1_SC_hotspot_comparison.png")

GSVI_HULL <- "#C9A27F"
GSC_HULL <- "#6B4226"

for (f in c(HULLS_GSVI, HULLS_GSC, PTS_GSC, TRANSITIONS_CSV, NEW_OBS_CSV,
            COMPARISON_CSV, STABILITY_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 6_selfcollected/4_pattern/HDBSCAN/1_sc_hdbscan.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

hulls_gsvi <- st_read(HULLS_GSVI, quiet = TRUE)
hulls_gsc <- st_read(HULLS_GSC, quiet = TRUE)
pts_gsc <- st_read(PTS_GSC, quiet = TRUE)
new_obs <- read.csv(NEW_OBS_CSV, stringsAsFactors = FALSE)
comparison <- read.csv(COMPARISON_CSV, stringsAsFactors = FALSE, check.names = FALSE)
stability <- read.csv(STABILITY_CSV, stringsAsFactors = FALSE, check.names = FALSE)
boundary <- st_read(file.path(PREP_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE)
slums <- st_read(file.path(PREP_DIR, "Nairobi_slum_polygon_32737.gpkg"), quiet = TRUE) |> st_union()

get_metric <- function(metric, col) comparison[[col]][comparison$Metric == metric]
get_stat <- function(measure) stability$Value[stability$Measure == measure]
parse_count <- function(x) as.integer(gsub(",", "", sub("^([0-9,]+).*", "\\1", x)))

# --- (a) the two hotspot footprints ------------------------------------------
sc_pts <- pts_gsc |> filter(location_kind == "self_collected")

p_map <- ggplot() +
  geom_sf(data = boundary, fill = "white", colour = "grey55", linewidth = 0.4) +
  geom_sf(data = slums, fill = SLUM_FILL, colour = NA, alpha = 0.30) +
  geom_sf(data = hulls_gsvi, aes(fill = "GSVI hotspots", colour = "GSVI hotspots"),
          alpha = 0.40, linewidth = 0.3) +
  geom_sf(data = hulls_gsc, aes(colour = "GSVI + SC hotspots"), fill = NA, linewidth = 0.55) +
  geom_sf(data = sc_pts, aes(colour = "Self-collected waste location"), size = 0.6, alpha = 0.85) +
  scale_fill_manual(name = NULL, values = c("GSVI hotspots" = GSVI_HULL), guide = "none") +
  scale_colour_manual(name = NULL, values = c(
    "GSVI hotspots" = GSVI_HULL,
    "GSVI + SC hotspots" = GSC_HULL,
    "Self-collected waste location" = "#cb181d"
  ), breaks = c("GSVI hotspots", "GSVI + SC hotspots", "Self-collected waste location")) +
  guides(colour = guide_legend(override.aes = list(
    linetype = c("solid", "solid", "blank"),
    shape = c(NA, NA, 16), size = c(0.6, 0.9, 2.2), fill = NA
  ))) +
  coord_sf(datum = NA, expand = FALSE) +
  labs(
    title = "(a) Hotspot footprints, both arms",
    subtitle = sprintf(
      "%s → %s clusters | area %s → %s km² (shown for scale; no result depends on the hull)",
      get_metric("Number of hotspots", "GSVI"), get_metric("Number of hotspots", "GSVI + SC"),
      get_metric("Total hotspot area (km²)", "GSVI"),
      get_metric("Total hotspot area (km²)", "GSVI + SC")
    )
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    legend.position = "bottom",
    legend.text = element_text(size = 8.4, colour = CHAPTER_AXIS_COLOUR),
    legend.key = element_blank()
  )

# --- (b) cluster label transitions -------------------------------------------
trans_raw <- read.csv(TRANSITIONS_CSV, stringsAsFactors = FALSE, check.names = FALSE)
names(trans_raw)[1] <- "from"

lvl <- function(v) {
  nums <- suppressWarnings(as.integer(v))
  c(v[!is.na(nums)][order(nums[!is.na(nums)])], v[v == "Noise"])
}

trans <- trans_raw |>
  filter(from != "Total") |>
  pivot_longer(-from, names_to = "to", values_to = "n") |>
  filter(to != "Total") |>
  mutate(
    from = factor(from, levels = rev(lvl(unique(from)))),
    to = factor(to, levels = lvl(unique(to)))
  )

p_trans <- ggplot(trans, aes(to, from)) +
  geom_tile(aes(fill = ifelse(n == 0, NA_real_, n)), colour = "white", linewidth = 0.4) +
  geom_text(data = filter(trans, n > 0), aes(label = n, colour = n > 120),
            size = 2.3, fontface = "bold", show.legend = FALSE) +
  scale_fill_gradient(name = "Locations", low = "#EFE6DC", high = "#4D2D18",
                      na.value = "#FBF9F7", labels = comma) +
  scale_colour_manual(values = c("FALSE" = "#4D2D18", "TRUE" = "white")) +
  scale_x_discrete(position = "top", expand = expansion(0)) +
  scale_y_discrete(expand = expansion(0)) +
  labs(
    title = "(b) Where each shared location's cluster label went",
    subtitle = sprintf(
      "All %s locations both runs share | ARI %s, NMI %s | median destination purity %s",
      get_stat("Locations present in both runs"),
      get_stat("Adjusted Rand Index"), get_stat("Normalised mutual information"),
      get_stat("Median destination purity")
    ),
    x = "Cluster with GSVI + SC", y = "Cluster with GSVI"
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text = element_text(size = 7, colour = CHAPTER_AXIS_COLOUR),
    panel.grid = element_blank(),
    legend.position = "right",
    legend.key.width = unit(0.32, "cm"),
    legend.key.height = unit(0.9, "cm"),
    legend.title = element_text(size = 8.4, colour = CHAPTER_AXIS_COLOUR),
    legend.text = element_text(size = 7.6)
  )

# --- (c) what the added locations join ---------------------------------------
n_new <- parse_count(new_obs$Value[new_obs$Metric == "New locations added"])
split_df <- new_obs |>
  filter(Metric %in% c("Joined a cluster that already held GSVI locations",
                       "Formed a cluster with no GSVI locations in it",
                       "Did not cluster (noise)")) |>
  mutate(
    segment = recode(Metric,
      "Joined a cluster that already held GSVI locations" = "Joined an existing hotspot",
      "Formed a cluster with no GSVI locations in it" = "Formed a new hotspot",
      "Did not cluster (noise)" = "Did not cluster"
    ),
    n = parse_count(Value)
  ) |>
  filter(n > 0) |>
  mutate(
    segment = factor(segment, levels = c("Did not cluster", "Formed a new hotspot",
                                         "Joined an existing hotspot")),
    label = sprintf("%s (%.1f%%)", comma(n), 100 * n / n_new)
  )

p_bar <- ggplot(split_df, aes(x = n, y = "added", fill = segment)) +
  geom_col(width = 0.4, colour = "white", linewidth = 0.35) +
  geom_text(aes(label = label), position = position_stack(vjust = 0.5),
            size = 3.1, fontface = "bold", colour = "white") +
  scale_fill_manual(name = NULL, values = c(
    "Joined an existing hotspot" = "#C9A27F",
    "Formed a new hotspot" = "#cb181d",
    "Did not cluster" = "#8C8078"
  ), breaks = c("Joined an existing hotspot", "Formed a new hotspot", "Did not cluster")) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02)), breaks = pretty_breaks(n = 4)) +
  labs(
    title = sprintf("(c) What the %s added locations join", comma(n_new)),
    subtitle = "By the cluster label they receive, not by which hull they fall in",
    x = "Number of locations", y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.2, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title.x = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text.x = element_text(size = 8.6, colour = CHAPTER_AXIS_COLOUR),
    axis.text.y = element_blank(),
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    legend.text = element_text(size = 8.2)
  )

fig <- (p_map | (p_trans / p_bar + plot_layout(heights = c(2.4, 1)))) +
  plot_layout(widths = c(1, 1.15)) +
  plot_annotation(
    title = "Waste hotspots with and without self-collected imagery",
    subtitle = sprintf(
      "Same HDBSCAN parameters on both arms (min_cluster_size 25, min_samples 6) | %s → %s waste locations",
      get_metric("Waste locations", "GSVI"), get_metric("Waste locations", "GSVI + SC")
    ),
    caption = paste0(
      "Stability is measured on cluster labels, so nothing depends on an overlap threshold or on the convex hull. Noise is kept as its own label in (b).\n",
      "Each GSVI cluster's locations move to a single combined cluster (median purity 100%), and ", get_stat("GSVI clusters involved in a merge"),
      " of them collapse into one — that merge is the whole of the 24 → 18 drop, and the reason ARI is lower than NMI.\n",
      "No added location forms a hotspot of its own: self-collection reinforces the GSVI hotspot map rather than redrawing it."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 14, height = 7.2, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

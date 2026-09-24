#!/usr/bin/env Rscript
# Step 6.4a — do the hotspots change when self-collected imagery is added?
#   1_SC_hotspot_comparison.png
#     (a) the two sets of convex-hull footprints, overlaid
#     (b) where the added locations fall: inside an existing GSVI hotspot, or not
#
# Panel (b) is the argument. If the added locations mostly land inside hulls the
# platform already drew, self-collection confirms the GSVI picture rather than
# correcting it.
#
# Inputs (6_selfcollected/4_pattern/, from 1_sc_hdbscan.py):
#   1_Nairobi_sc_hotspots_{gsvi,gsvi_selfcollected}_32737.gpkg
#   1_Nairobi_sc_hdbscan_{gsvi,gsvi_selfcollected}_32737.gpkg
#   1_sc_hdbscan_new_locations.csv
#   thesis_table/table_6_4_hdbscan_comparison.csv

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(dplyr)
  library(scales)
  library(patchwork)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "../..", "R", "chapter_paths.R"))
source(file.path(script_dir, "../..", "R", "chapter_colours.R"))

DATA_DIR <- file.path(chapter_data_root, "6_selfcollected", "4_pattern")
PREP_DIR <- file.path(chapter_data_root, "1prepare_chapter_data")
FIG_DIR <- file.path(script_dir, "../..", "Figure", "6_selfcollected", "4_pattern")

HULLS_GSVI <- file.path(DATA_DIR, "1_Nairobi_sc_hotspots_gsvi_32737.gpkg")
HULLS_GSC <- file.path(DATA_DIR, "1_Nairobi_sc_hotspots_gsvi_selfcollected_32737.gpkg")
PTS_GSC <- file.path(DATA_DIR, "1_Nairobi_sc_hdbscan_gsvi_selfcollected_32737.gpkg")
NEW_OBS_CSV <- file.path(DATA_DIR, "1_sc_hdbscan_new_locations.csv")
COMPARISON_CSV <- file.path(DATA_DIR, "thesis_table", "table_6_4_hdbscan_comparison.csv")
OUT_PATH <- file.path(FIG_DIR, "1_SC_hotspot_comparison.png")

GSVI_HULL <- "#C9A27F"
GSC_HULL <- "#6B4226"
INSIDE_COLOUR <- "#C9A27F"
OUTSIDE_COLOUR <- "#6B4226"

for (f in c(HULLS_GSVI, HULLS_GSC, PTS_GSC, NEW_OBS_CSV, COMPARISON_CSV)) {
  if (!file.exists(f)) {
    stop("Missing ", f, " — run 6_selfcollected/4_pattern/1_sc_hdbscan.py first")
  }
}
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

hulls_gsvi <- st_read(HULLS_GSVI, quiet = TRUE)
hulls_gsc <- st_read(HULLS_GSC, quiet = TRUE)
pts_gsc <- st_read(PTS_GSC, quiet = TRUE)
new_obs <- read.csv(NEW_OBS_CSV, stringsAsFactors = FALSE)
comparison <- read.csv(COMPARISON_CSV, stringsAsFactors = FALSE, check.names = FALSE)
boundary <- st_read(file.path(PREP_DIR, "Nairobi_boundary_polygon_32737.gpkg"), quiet = TRUE)
slums <- st_read(file.path(PREP_DIR, "Nairobi_slum_polygon_32737.gpkg"), quiet = TRUE) |> st_union()

parse_count <- function(x) as.integer(gsub(",", "", sub("^([0-9,]+).*", "\\1", x)))
parse_pct <- function(x) as.numeric(sub(".*\\(([0-9.]+)%\\).*", "\\1", x))

n_new <- parse_count(new_obs$Value[new_obs$Metric == "New locations added"])
inside_v <- new_obs$Value[new_obs$Metric == "New locations inside existing hotspots"]
outside_v <- new_obs$Value[new_obs$Metric == "New locations forming new hotspots"]
retained_v <- new_obs$Value[new_obs$Metric == "Existing hotspots retained"]
n_created <- parse_count(new_obs$Value[new_obs$Metric == "Newly created hotspots"])

get_metric <- function(metric, col) comparison[[col]][comparison$Metric == metric]

# --- (a) the two hotspot footprints ------------------------------------------
sc_pts <- pts_gsc |> filter(location_kind == "self_collected")

p_map <- ggplot() +
  geom_sf(data = boundary, fill = "white", colour = "grey55", linewidth = 0.4) +
  geom_sf(data = slums, fill = SLUM_FILL, colour = NA, alpha = 0.30) +
  geom_sf(data = hulls_gsvi, aes(fill = "GSVI hotspots", colour = "GSVI hotspots"),
          alpha = 0.40, linewidth = 0.3) +
  geom_sf(data = hulls_gsc, aes(colour = "GSVI + SC hotspots"),
          fill = NA, linewidth = 0.55) +
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
      "%s → %s clusters | area %s → %s km² | green = mapped settlements",
      get_metric("Number of hotspots", "GSVI"), get_metric("Number of hotspots", "GSVI + SC"),
      get_metric("Total hotspot area (km²)", "GSVI"),
      get_metric("Total hotspot area (km²)", "GSVI + SC")
    )
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    legend.position = "bottom",
    legend.text = element_text(size = 8.4, colour = CHAPTER_AXIS_COLOUR),
    legend.key = element_blank()
  )

# --- (b) where the added locations fall ---------------------------------------
split_df <- tibble(
  segment = c("Inside existing GSVI hotspots", "Outside any existing hotspot"),
  n = c(parse_count(inside_v), parse_count(outside_v)),
  pct = c(parse_pct(inside_v), parse_pct(outside_v))
) |>
  mutate(
    segment = factor(segment, levels = c("Outside any existing hotspot", "Inside existing GSVI hotspots")),
    label = sprintf("%s\n(%.1f%%)", comma(n), pct)
  )

p_bar <- ggplot(split_df, aes(x = n, y = "Self-collected waste locations", fill = segment)) +
  geom_col(width = 0.5, colour = "white", linewidth = 0.35) +
  geom_text(aes(label = label), position = position_stack(vjust = 0.5),
            size = 3.6, fontface = "bold", colour = "white", lineheight = 0.92) +
  scale_fill_manual(name = NULL, values = c(
    "Inside existing GSVI hotspots" = INSIDE_COLOUR,
    "Outside any existing hotspot" = OUTSIDE_COLOUR
  ), breaks = c("Inside existing GSVI hotspots", "Outside any existing hotspot")) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02)), breaks = pretty_breaks(n = 4)) +
  labs(
    title = "(b) Where the added locations fall",
    subtitle = sprintf(
      "%s new waste locations, split by overlap with the GSVI hotspot hulls",
      comma(n_new)
    ),
    x = "Number of locations", y = NULL
  ) +
  theme_minimal(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 11.5, colour = CHAPTER_TITLE_COLOUR),
    plot.subtitle = element_text(size = 8.4, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 6)),
    axis.title.x = element_text(size = 9.5, colour = CHAPTER_AXIS_COLOUR),
    axis.text.x = element_text(size = 8.8, colour = CHAPTER_AXIS_COLOUR),
    axis.text.y = element_blank(),
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    legend.text = element_text(size = 8.6)
  )

# --- (c) what happened to the 24 GSVI hotspots --------------------------------
note <- sprintf(
  "Existing hotspots retained: %s   |   Newly created hotspots: %s",
  retained_v, comma(n_created)
)

p_note <- ggplot() +
  annotate("text", x = 0, y = 0, label = note, hjust = 0.5, size = 3.5,
           fontface = "bold", colour = CHAPTER_AXIS_COLOUR) +
  theme_void()

fig <- (p_map | (p_bar / p_note + plot_layout(heights = c(4, 1)))) +
  plot_layout(widths = c(1.15, 1)) +
  plot_annotation(
    title = "Waste hotspots with and without self-collected imagery",
    subtitle = sprintf(
      "Same HDBSCAN parameters on both arms (min_cluster_size 25, min_samples 6) | %s → %s waste locations",
      get_metric("Waste locations", "GSVI"), get_metric("Waste locations", "GSVI + SC")
    ),
    caption = paste0(
      "A hotspot counts as retained when at least 30% of its GSVI hull area is re-covered by a hotspot of the combined arm.\n",
      "The cluster count falls because neighbouring hotspots merge into larger ones, not because hotspots disappear — total footprint area rises."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = CHAPTER_TITLE_COLOUR),
      plot.subtitle = element_text(size = 9, hjust = 0.5, colour = CHAPTER_SUBTITLE_COLOUR, margin = margin(b = 8)),
      plot.caption = element_text(size = 8.2, hjust = 0, colour = CHAPTER_CAPTION_COLOUR,
                                  lineheight = 1.3, margin = margin(t = 8))
    )
  )

ggsave(OUT_PATH, fig, width = 13, height = 6.6, dpi = 400, bg = "white")
message("Wrote ", OUT_PATH)
message("Done.")

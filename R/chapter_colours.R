# Shared brown-ish chapter palette (aligned with 4_compare / 5_spatial_pattern figures)

CHAPTER_AXIS_COLOUR <- "#4D2D18"

ALL_SVI_COLOUR <- "#D4CCC2"
GSVI_COLOUR <- "#C9A27F"
SELF_COLLECTED_COLOUR <- "#6B4226"

WASTE_COLOUR <- "#6B4226"
WASTE_DARK_COLOUR <- "#4D2D18"
SVI_COLOUR <- "#C9A27F"
SVI_LIGHT_COLOUR <- "#D4CCC2"

SLUM_FILL <- "#496142"
SLUM_EDGE <- "#112721"
SLUM_ALPHA <- 0.22

ROAD_COLOUR <- "#6B5D52"
ROAD_LIGHT_COLOUR <- "#D4CCC2"
ROAD_COVERED_COLOUR <- "#B8A99A"
ROAD_UNCOVERED_COLOUR <- "#6B4226"

# Bright accent colours for difference / comparison maps (keep visible on brown chapter theme)
HIGHLIGHT_NEGATIVE_COLOUR <- "#cb181d"
HIGHLIGHT_POSITIVE_COLOUR <- "#4575b4"
COMPARISON_OVERLAP_COLOUR <- "#525252"
COMPARISON_LOCAL_ONLY_COLOUR <- "#d73027"
COMPARISON_OSMNX_ONLY_COLOUR <- "#4575b4"
ROAD_BASELINE_COLOUR <- "#c8c8c8"

LOCAL_SOURCE_COLOUR <- "#C9A27F"
OSMNX_SOURCE_COLOUR <- "#6B4226"
OVERLAP_COLOUR <- "#8C7355"
LOCAL_ONLY_COLOUR <- "#A67C52"
OSMNX_ONLY_COLOUR <- "#4D2D18"

CHAPTER_SEQ_LOW <- "#F5F0EB"
CHAPTER_SEQ_MID <- "#C9A27F"
CHAPTER_SEQ_HIGH <- "#4D2D18"

CHAPTER_DISCRETE_PALETTE <- c(
  "#4D2D18", "#6B4226", "#8B5A3C", "#A67C52", "#C9A27F",
  "#D4CCC2", "#B8956E", "#7A5C3A", "#5C4033", "#A89279",
  "#8C7355", "#D9C4A9", "#6F4E37", "#C4A882", "#9E7B56"
)

# Light → dark browns for composition charts (largest slice gets brightest)
CHAPTER_PIE_PALETTE <- c(
  "#D4CCC2", "#D9C4A9", "#C9A27F", "#C4A882", "#A89279",
  "#A67C52", "#B8956E", "#9E7B56", "#8B5A3C", "#8C7355",
  "#7A5C3A", "#6B4226", "#6F4E37", "#5C4033", "#4D2D18"
)

MEDIAN_COLOUR <- "#6B4226"
MEAN_COLOUR <- "#C9A27F"
MEAN_POINT_COLOUR <- "#4D2D18"

CORR_LOW <- "#F5F0EB"
CORR_HIGH <- "#4D2D18"
CORR_EMPTY <- "#FAF8F5"
CORR_TEXT_DARK <- "#4D2D18"
CORR_TEXT_LIGHT <- "white"
CORR_LABEL <- "#6B5D52"

CHAPTER_TITLE_COLOUR <- "#2f2f2f"
CHAPTER_SUBTITLE_COLOUR <- "#6B5D52"
CHAPTER_CAPTION_COLOUR <- "#8C8078"

# Shared heatmap palette (validation confusion matrices, correlation heatmaps)
CHOCOLATE_PALETTE <- c("#fafafa", "#E5C8A9", "#C9A27F", "#8B5E3C", "#6B4226")
CHOCOLATE_EMPTY <- "#fafafa"
CHOCOLATE_TEXT_DARK <- "#2f2f2f"
CHOCOLATE_TEXT_LIGHT <- "white"

# White labels on darker chocolate fills; dark text on lighter fills
chocolate_label_colour <- function(
  x,
  limits = NULL,
  trans = c("identity", "sqrt"),
  dark_threshold = 0.60
) {
  trans <- match.arg(trans)
  if (is.null(limits)) {
    limits <- range(x, na.rm = TRUE)
  }
  if (!is.finite(diff(limits)) || diff(limits) == 0) {
    return(rep(CHOCOLATE_TEXT_DARK, length(x)))
  }

  vals <- if (trans == "sqrt") sqrt(pmax(x, 0)) else x
  lo <- if (trans == "sqrt") sqrt(max(limits[1], 0)) else limits[1]
  hi <- if (trans == "sqrt") sqrt(limits[2]) else limits[2]
  norm <- (vals - lo) / (hi - lo)
  norm <- pmax(pmin(norm, 1), 0)
  ifelse(norm >= dark_threshold, CHOCOLATE_TEXT_LIGHT, CHOCOLATE_TEXT_DARK)
}

chapter_discrete_colours <- function(n) {
  setNames(CHAPTER_DISCRETE_PALETTE[seq_len(n)], seq_len(n))
}

# Assign brightest colours to the largest categories (for pie / bar composition charts)
chapter_pie_colours <- function(type_names, sizes) {
  n <- length(type_names)
  palette <- CHAPTER_PIE_PALETTE[seq_len(n)]
  rank <- rank(-sizes, ties.method = "first")
  setNames(palette[rank], type_names)
}

scale_fill_chapter_c <- function(name = NULL, ...) {
  scale_fill_gradient(
    low = CHAPTER_SEQ_LOW,
    high = CHAPTER_SEQ_HIGH,
    name = name,
    ...
  )
}

scale_colour_chapter_c <- function(name = NULL, ...) {
  scale_colour_gradient(
    low = CHAPTER_SEQ_LOW,
    high = CHAPTER_SEQ_HIGH,
    name = name,
    ...
  )
}

# ---------------------------------------------------------------------------
# Process zoom map palettes (4-panel + all-layers exemplar figures)
# Options: sage (default), mixed, earth, chapter
# ---------------------------------------------------------------------------
ZOOM_PALETTE_CHOICES <- c("mixed", "earth", "sage", "chapter", "all")

get_zoom_palette <- function(name = "mixed") {
  palettes <- list(
    mixed = list(
      label = "Mixed — peach density, sage slums, teal coverage, red gaps/waste",
      context_fill = "#F1E4DB",
      context_edge = "#D7C9BE",
      density_low = "#F7C8A4",
      density_high = "#657359",
      focus_edge = "#497889",
      hex_label = "#497889",
      slum = "#496142",
      road = "#8B775F",
      road_faint = "#D7C9BE",
      focus_fill = "#F7C8A4",
      road_covered = "#7795A2",
      road_uncovered = "#cb181d",
      svi = "#C1A59D",
      svi_light = "#F7C8A4",
      svi_buffer_fill = "#7795A2",
      svi_buffer_edge = "#497889",
      waste_pos = "#cb181d",
      waste_det = "#657359",
      focus_outline = "#497889"
    ),
    earth = list(
      label = "Earth — peach to teal sequential (#F7C8A4 … #497889)",
      context_fill = "#F1E4DB",
      context_edge = "#C1A59D",
      density_low = "#F7C8A4",
      density_high = "#497889",
      focus_edge = "#497889",
      hex_label = "#497889",
      slum = "#657359",
      road = "#979A9B",
      road_faint = "#D7C9BE",
      focus_fill = "#F7C8A4",
      road_covered = "#7795A2",
      road_uncovered = "#cb181d",
      svi = "#C1A59D",
      svi_light = "#F7C8A4",
      svi_buffer_fill = "#7795A2",
      svi_buffer_edge = "#497889",
      waste_pos = "#497889",
      waste_det = "#cb181d",
      focus_outline = "#497889"
    ),
    sage = list(
      label = "Sage — cream to olive sequential (#F1E4DB … #657359)",
      context_fill = "#F1E4DB",
      context_edge = "#D7C9BE",
      density_low = "#F1E4DB",
      density_high = "#657359",
      # Active: warm brown H3 outline (lighter than waste #4D2D18)
      focus_edge = "#8B5A3C",
      hex_label = "#8B5A3C",
      focus_outline = "#8B5A3C",
      # Archived alternative — olive-green H3 outline (see
      # Figure/2coverage_analysis/archive/Nairobi_process_zoom_h3_res8_buf50m_svi50_layers_green_outline.png):
      # focus_edge = "#657359",
      # hex_label = "#657359",
      # focus_outline = "#657359",
      slum = "#657359",
      road = "#8B775F",
      road_faint = "#D7C9BE",
      focus_fill = "#D7C9BE",
      road_covered = "#9AA582",
      road_uncovered = "#cb181d",
      # Muted variant for the 4-panel schematic, where gap segments are dense
      road_uncovered_soft = "#C05A4E",
      svi = "#D7C9BE",
      svi_light = "#F1E4DB",
      svi_buffer_fill = "#9AA582",
      svi_buffer_edge = "#657359",
      svi_buffer_edge_strong = "#3F4A35",
      waste_pos = "#4D2D18",
      waste_det = "#cb181d"
    ),
    chapter = list(
      label = "Chapter brown (legacy zoom styling)",
      context_fill = "grey96",
      context_edge = "grey82",
      density_low = CHAPTER_SEQ_LOW,
      density_high = CHAPTER_SEQ_HIGH,
      focus_edge = ROAD_COLOUR,
      hex_label = "grey10",
      slum = SLUM_FILL,
      road = ROAD_COLOUR,
      road_faint = "#ececec",
      focus_fill = CHAPTER_SEQ_LOW,
      road_covered = ROAD_COVERED_COLOUR,
      road_uncovered = HIGHLIGHT_NEGATIVE_COLOUR,
      svi = SVI_COLOUR,
      svi_light = SVI_LIGHT_COLOUR,
      svi_buffer_fill = SVI_LIGHT_COLOUR,
      svi_buffer_edge = SVI_COLOUR,
      waste_pos = WASTE_COLOUR,
      waste_det = WASTE_DARK_COLOUR,
      focus_outline = CHAPTER_AXIS_COLOUR
    )
  )

  if (!name %in% names(palettes)) {
    stop(
      "Unknown zoom palette: ", name,
      "\nChoose one of: ", paste(names(palettes), collapse = ", "), ", or all"
    )
  }
  palettes[[name]]
}

scale_fill_zoom_density <- function(pal, name = "Road density\n(km/km²)", ...) {
  scale_fill_gradient(
    low = pal$density_low,
    high = pal$density_high,
    name = name,
    ...
  )
}

zoom_layer_colours <- function(pal, svi_buffer_m = 50L) {
  buf <- as.integer(svi_buffer_m)
  # Darker than fill edge so dashed buffer rings read clearly on white/transparent maps
  buffer_edge <- if (!is.null(pal$svi_buffer_edge_strong)) {
    pal$svi_buffer_edge_strong
  } else {
    "#3F4A35"
  }
  c(
    "Focus H3 cell boundary" = pal$focus_outline,
    setNames(pal$road_covered, sprintf("Road within %d m of GSVI", buf)),
    "Road without GSVI support" = pal$road_uncovered,
    "GSVI panorama" = pal$svi,
    "Waste-positive panorama" = pal$waste_pos,
    setNames(buffer_edge, sprintf("%d m GSVI buffer", buf))
  )
}

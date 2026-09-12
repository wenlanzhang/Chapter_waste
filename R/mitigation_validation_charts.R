# Shared crowd-validation mitigation charts (binary, 3-class, overlap).
# Sourced by 3_100m/3_plot_mitigation_validation*.R after chapter_paths + map_theme.

ARM_LEVELS <- c("GSVI", "G+Self")
ARM_COLOURS <- c("GSVI" = "#C9A27F", "G+Self" = "#6B4226")
ARM_LABELS <- c(
  "GSVI" = "GSVI (Google only)",
  "G+Self" = "G+Self (Google + self-collected)"
)
METRIC_LEVELS <- c("Accuracy", "Precision", "Recall", "F1")
BINARY_KEYS <- c("binary_accuracy", "binary_precision", "binary_recall", "binary_f1")
SEVERITY_KEYS <- c(
  "severity_accuracy", "severity_precision", "severity_recall", "severity_f1"
)
DODGE_WIDTH <- 0.72
BAR_WIDTH <- 0.11
PAIR_GAP <- 0.08
BRACKET_Y <- -5
BRACKET_LABEL_Y <- -9

prepare_arm <- function(df) {
  df |>
    mutate(
      arm = case_when(
        grepl("^GSVI", predictor) ~ "GSVI",
        grepl("^G\\+Self", predictor) ~ "G+Self",
        TRUE ~ predictor
      ),
      arm = factor(arm, levels = ARM_LEVELS)
    )
}

changed_note <- function(summary_note) {
  n_changed_note <- summary_note$Note[summary_note$Topic == "Cells where G+Self differs from GSVI"]
  if (length(n_changed_note) == 0) {
    n_changed_note <- summary_note$Note[
      summary_note$Topic == "Cells where G+Self differs from submitted GSVI"
    ]
  }
  n_changed_note
}

mitigation_paths <- function(script_dir) {
  list(
    fig_dir = file.path(script_dir, "..", "Figure", "3_100m"),
    comparison_csv = file.path(
      chapter_data_root, "3_100m", "mitigation",
      "Nairobi_validation_mitigation_comparison.csv"
    ),
    summary_csv = file.path(
      chapter_data_root, "3_100m", "mitigation",
      "Nairobi_validation_mitigation_summary.csv"
    )
  )
}

build_task_panel <- function(df, panel_tag, subset_label, metric_keys) {
  n_cells <- unique(df$n_cells)
  n_label <- if (length(n_cells) == 1) comma(n_cells) else paste(comma(n_cells), collapse = ", ")

  plot_df <- prepare_arm(df) |>
    select(arm, all_of(metric_keys)) |>
    pivot_longer(
      cols = all_of(metric_keys),
      names_to = "metric_key",
      values_to = "score"
    ) |>
    mutate(
      score_pct = score * 100,
      metric = factor(metric_key, levels = metric_keys, labels = METRIC_LEVELS)
    )

  ggplot(plot_df, aes(x = metric, y = score_pct, fill = arm)) +
    geom_col(
      position = position_dodge(width = DODGE_WIDTH),
      width = 0.62,
      colour = "white",
      linewidth = 0.5
    ) +
    geom_text(
      aes(label = sprintf("%.1f%%", score_pct)),
      position = position_dodge(width = DODGE_WIDTH),
      vjust = -0.4,
      size = 3.0,
      fontface = "bold",
      colour = "#3d2b1f",
      show.legend = FALSE
    ) +
    scale_fill_manual(values = ARM_COLOURS, breaks = ARM_LEVELS, labels = ARM_LABELS) +
    scale_y_continuous(
      limits = c(0, 100),
      breaks = seq(0, 100, 25),
      expand = expansion(mult = c(0, 0.12))
    ) +
    labs(
      title = sprintf("%s %s (n = %s)", panel_tag, subset_label, n_label),
      x = NULL,
      y = "Score (%)",
      fill = "Pipeline arm"
    ) +
    map_theme() +
    theme(
      plot.title = element_text(size = 10.5, face = "bold", hjust = 0, colour = "#2f2f2f"),
      axis.text.x = element_text(size = 9.5, colour = "#4D2D18"),
      axis.text.y = element_text(size = 8.5),
      axis.title.y = element_text(size = 9.5, colour = "#4D2D18"),
      panel.grid.major.x = element_blank(),
      legend.position = "none",
      plot.margin = margin(8, 12, 6, 8)
    )
}

plot_mitigation_task <- function(task = c("binary", "severity"), script_dir) {
  task <- match.arg(task)
  paths <- mitigation_paths(script_dir)
  metric_keys <- if (task == "binary") BINARY_KEYS else SEVERITY_KEYS

  message("Reading tables...")
  comparison <- read.csv(paths$comparison_csv, stringsAsFactors = FALSE)
  summary_note <- read.csv(paths$summary_csv, stringsAsFactors = FALSE)

  missing_cols <- setdiff(metric_keys, names(comparison))
  if (length(missing_cols) > 0) {
    stop(
      "Missing metric columns in comparison CSV: ",
      paste(missing_cols, collapse = ", "),
      ". Re-run 3_mitigation_validation.py first.",
      call. = FALSE
    )
  }

  all_cells <- comparison |> filter(subset == "All validated cells")
  self_cells <- comparison |> filter(subset == "Self-collected SVI overlap")
  n_changed_note <- changed_note(summary_note)

  p_all <- build_task_panel(all_cells, "(A)", "All validated cells", metric_keys)
  p_self <- build_task_panel(self_cells, "(B)", "Self-collected overlap", metric_keys)

  panel <- p_all / p_self +
    plot_layout(guides = "collect") &
    theme(
      legend.position = "bottom",
      legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
      legend.text = element_text(size = 9, colour = "#4D2D18"),
      legend.margin = margin(t = 4)
    )

  if (task == "binary") {
    title <- "Crowd Validation: Binary Waste Classification (GSVI vs G+Self)"
    caption <- paste0(
      "Binary task: waste present vs absent. Light tan = Google Street View only; ",
      "dark brown = Google plus Faith/ZWL self-collected imagery. ",
      n_changed_note, "."
    )
    outfile <- "Validation_mitigation_accuracy.png"
    panel_b_standalone <- p_self +
      labs(
        title = sprintf("Self-collected overlap (n = %s)", comma(unique(self_cells$n_cells))),
        caption = caption
      ) +
      theme(
        plot.title = element_text(size = 12, face = "bold", hjust = 0.5, colour = "#2f2f2f"),
        legend.position = "bottom",
        legend.title = element_text(size = 9.5, face = "bold", colour = "#4D2D18"),
        legend.text = element_text(size = 9, colour = "#4D2D18"),
        legend.margin = margin(t = 4),
        plot.caption = element_text(
          size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8)
        )
      )
  } else {
    title <- "Crowd Validation: 3-Class Severity (GSVI vs G+Self)"
    caption <- paste0(
      "3-class task: severity 0 / 1 / 2. Precision, recall, and F1 are macro-averaged ",
      "over the three classes (one-vs-rest). Light tan = Google only; dark brown = Google + self-collected. ",
      n_changed_note, "."
    )
    outfile <- "Validation_mitigation_severity.png"
    panel_b_standalone <- NULL
  }

  panel <- panel +
    plot_annotation(
      title = title,
      subtitle = paste0(
        "Nairobi 100 m grid; IDEAMaps pipeline with fixed submission Jenks break points. ",
        "Each pair of bars compares the same metric under two pipeline arms (fill colour)."
      ),
      caption = caption,
      theme = theme(
        plot.title = element_text(face = "bold", size = 14, hjust = 0.5, colour = "#2f2f2f"),
        plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 10)),
        plot.caption = element_text(
          size = 8.5, hjust = 0, colour = "#7A6A5C", lineheight = 1.25, margin = margin(t = 8)
        )
      )
    )

  dir.create(paths$fig_dir, recursive = TRUE, showWarnings = FALSE)
  out_path <- file.path(paths$fig_dir, outfile)
  ggsave(out_path, plot = panel, width = 9, height = 9.5, dpi = 600, bg = "white")
  message("Wrote ", out_path)

  if (!is.null(panel_b_standalone)) {
    out_path_b <- file.path(paths$fig_dir, "Validation_mitigation_accuracy_self_overlap.png")
    ggsave(out_path_b, plot = panel_b_standalone, width = 7.5, height = 5.5, dpi = 600, bg = "white")
    message("Wrote ", out_path_b)
  }
  message("Done.")
}

assign_bar_x <- function(metric_num, task, arm) {
  is_binary <- task == "Binary"
  is_gsvi <- arm == "GSVI"
  offset <- ifelse(
    is_binary,
    ifelse(is_gsvi, -0.20 - PAIR_GAP / 2, -0.07 - PAIR_GAP / 2),
    ifelse(is_gsvi, 0.07 + PAIR_GAP / 2, 0.20 + PAIR_GAP / 2)
  )
  metric_num + offset
}

prepare_overlap_plot_data <- function(df) {
  arms <- prepare_arm(df)

  binary_long <- arms |>
    select(arm, all_of(BINARY_KEYS)) |>
    pivot_longer(-arm, names_to = "metric_key", values_to = "score") |>
    mutate(task = "Binary")

  severity_long <- arms |>
    select(arm, all_of(SEVERITY_KEYS)) |>
    pivot_longer(-arm, names_to = "metric_key", values_to = "score") |>
    mutate(task = "3-class")

  bind_rows(binary_long, severity_long) |>
    mutate(
      score_pct = score * 100,
      metric = factor(
        metric_key,
        levels = c(BINARY_KEYS, SEVERITY_KEYS),
        labels = rep(METRIC_LEVELS, 2)
      ),
      metric_num = as.numeric(metric),
      bar_x = assign_bar_x(metric_num, task, as.character(arm)),
      series = factor(
        paste(task, as.character(arm), sep = ", "),
        levels = c("Binary, GSVI", "Binary, G+Self", "3-class, GSVI", "3-class, G+Self")
      )
    )
}

overlap_bracket_df <- function(plot_df) {
  plot_df |>
    group_by(metric, metric_num) |>
    summarise(
      binary_xmin = min(bar_x[task == "Binary"]) - BAR_WIDTH * 0.75,
      binary_xmax = max(bar_x[task == "Binary"]) + BAR_WIDTH * 0.75,
      sev_xmin = min(bar_x[task == "3-class"]) - BAR_WIDTH * 0.75,
      sev_xmax = max(bar_x[task == "3-class"]) + BAR_WIDTH * 0.75,
      binary_x = mean(bar_x[task == "Binary"]),
      sev_x = mean(bar_x[task == "3-class"]),
      .groups = "drop"
    )
}

overlap_axis_theme <- function() {
  theme(
    legend.position = "top",
    legend.justification = "center",
    legend.direction = "horizontal",
    legend.background = element_blank(),
    legend.box.background = element_blank(),
    legend.box.margin = margin(0, 0, 0, 0),
    legend.text = element_text(size = 8, colour = "#4D2D18"),
    legend.key.size = unit(0.38, "cm"),
    legend.key.width = unit(0.38, "cm"),
    legend.spacing.x = unit(0.15, "cm"),
    axis.text.x = element_text(size = 10, colour = "#4D2D18", margin = margin(t = 18)),
    axis.text.y = element_text(size = 8.5),
    axis.title.y = element_text(size = 9.5, colour = "#4D2D18"),
    panel.grid.major.x = element_blank()
  )
}

add_overlap_brackets <- function(p, bracket_df) {
  p +
    geom_segment(
      data = bracket_df,
      aes(x = binary_x - 0.12, xend = binary_x + 0.12, y = BRACKET_Y, yend = BRACKET_Y),
      linewidth = 0.35,
      colour = "#9A8578"
    ) +
    geom_segment(
      data = bracket_df,
      aes(x = sev_x - 0.12, xend = sev_x + 0.12, y = BRACKET_Y, yend = BRACKET_Y),
      linewidth = 0.35,
      colour = "#9A8578"
    ) +
    geom_text(
      data = bracket_df,
      aes(x = binary_x, y = BRACKET_LABEL_Y, label = "Binary"),
      size = 3.0,
      colour = "#6B5B4F"
    ) +
    geom_text(
      data = bracket_df,
      aes(x = sev_x, y = BRACKET_LABEL_Y, label = "3-class"),
      size = 3.0,
      colour = "#6B5B4F"
    )
}

plot_mitigation_overlap <- function(style = c("colour", "pattern"), script_dir) {
  style <- match.arg(style)
  paths <- mitigation_paths(script_dir)

  message("Reading tables...")
  comparison <- read.csv(paths$comparison_csv, stringsAsFactors = FALSE)
  overlap <- comparison |> filter(subset == "Self-collected SVI overlap")
  if (nrow(overlap) != 2) {
    stop("Expected two rows for self-collected overlap subset.", call. = FALSE)
  }

  n_cells <- unique(overlap$n_cells)
  plot_df <- prepare_overlap_plot_data(overlap)
  p_chart <- if (style == "colour") {
    build_overlap_colour_chart(plot_df)
  } else {
    build_overlap_pattern_chart(plot_df)
  }

  title_grob <- ggdraw() +
    draw_label(
      sprintf(
        "Mitigation: crowd validation at self-collected SVI overlap (n = %s)",
        comma(n_cells)
      ),
      fontface = "bold",
      size = 12.5,
      colour = "#2f2f2f",
      x = 0.5,
      hjust = 0.5,
      y = if (style == "pattern") 0.55 else 0.35
    )

  caption_grob <- ggdraw() +
    draw_label(
      paste0(
        "Binary: waste present vs absent. ",
        "3-class: low, middle, high chance of seeing visible waste piles."
      ),
      size = 8.5,
      colour = "#7A6A5C",
      x = 0,
      hjust = 0,
      y = 1,
      lineheight = 1.2
    )

  if (style == "pattern") {
    panel <- plot_grid(
      title_grob, ggdraw(), p_chart, caption_grob,
      ncol = 1, rel_heights = c(0.05, 0.018, 1, 0.10), align = "v", axis = "l"
    )
    outfile <- "Validation_mitigation_self_overlap_pattern.png"
  } else {
    panel <- plot_grid(
      title_grob, p_chart, caption_grob,
      ncol = 1, rel_heights = c(0.055, 1, 0.09), align = "v", axis = "l"
    )
    outfile <- "Validation_mitigation_self_overlap.png"
  }

  dir.create(paths$fig_dir, recursive = TRUE, showWarnings = FALSE)
  out_path <- file.path(paths$fig_dir, outfile)
  ggsave(out_path, plot = panel, width = 12, height = 5.8, dpi = 600, bg = "white")
  message("Wrote ", out_path)
  message("Done.")
}

build_overlap_colour_chart <- function(plot_df) {
  series_levels <- levels(plot_df$series)
  series_colours <- c("#C9A27F", "#A8B8A3", "#6B4226", "#496142")
  names(series_colours) <- series_levels
  series_labels <- c(
    "Binary, GSVI" = "Binary, GSVI (Google only)",
    "Binary, G+Self" = "Binary, G+Self (Google + self-collected)",
    "3-class, GSVI" = "3-class, GSVI (Google only)",
    "3-class, G+Self" = "3-class, G+Self (Google + self-collected)"
  )
  bracket_df <- overlap_bracket_df(plot_df)
  bg_df <- bind_rows(
    bracket_df |> mutate(group = "Binary") |> transmute(metric_num, xmin = binary_xmin, xmax = binary_xmax, group),
    bracket_df |> mutate(group = "3-class") |> transmute(metric_num, xmin = sev_xmin, xmax = sev_xmax, group)
  ) |>
    mutate(bg_fill = if_else(group == "Binary", "#C9A27F", "#6B4226"))

  p <- ggplot() +
    geom_rect(
      data = bg_df,
      aes(xmin = xmin, xmax = xmax, ymin = 0, ymax = 100),
      fill = alpha(bg_df$bg_fill, 0.06),
      colour = NA
    ) +
    scale_fill_manual(values = series_colours, labels = series_labels, name = NULL) +
    geom_col(
      data = plot_df,
      aes(x = bar_x, y = score_pct, fill = series),
      width = BAR_WIDTH,
      colour = "white",
      linewidth = 0.45
    ) +
    geom_text(
      data = plot_df,
      aes(x = bar_x, y = score_pct, label = sprintf("%.1f%%", score_pct)),
      vjust = -0.35,
      size = 2.7,
      fontface = "bold",
      colour = "#3d2b1f"
    ) +
    guides(fill = guide_legend(nrow = 1)) +
    coord_cartesian(ylim = c(0, 100), clip = "off") +
    scale_x_continuous(
      breaks = unique(plot_df$metric_num),
      labels = METRIC_LEVELS,
      expand = expansion(mult = c(0.08, 0.08))
    ) +
    scale_y_continuous(breaks = seq(0, 100, 25), expand = expansion(mult = c(0, 0.05))) +
    labs(x = NULL, y = "Score (%)") +
    map_theme() +
    overlap_axis_theme() +
    theme(legend.margin = margin(t = 0, r = 0, b = 2, l = 0), plot.margin = margin(t = 0, r = 12, b = 28, l = 8))

  add_overlap_brackets(p, bracket_df)
}

build_overlap_pattern_chart <- function(plot_df) {
  white <- "#FFFFFF"
  light_gsvi <- "#E5C8A9"
  light_gsc <- "#C9A27F"
  stripe_gsvi <- "#C9A27F"
  stripe_gsc <- "#A67B5B"
  pattern_density <- 0.26
  pattern_spacing <- 0.028
  pattern_angle <- 45

  series_levels <- levels(plot_df$series)
  series_fills <- c(light_gsvi, light_gsc, white, light_gsc)
  names(series_fills) <- series_levels
  series_patterns <- c("none", "none", "stripe", "stripe")
  names(series_patterns) <- series_levels
  series_pattern_fills <- c(NA, NA, stripe_gsvi, stripe_gsc)
  names(series_pattern_fills) <- series_levels
  series_labels <- c(
    "Binary, GSVI" = "Binary, GSVI (Google only)",
    "Binary, G+Self" = "Binary, G+Self (Google + self-collected)",
    "3-class, GSVI" = "3-class, GSVI (Google only)",
    "3-class, G+Self" = "3-class, G+Self (Google + self-collected)"
  )

  plot_df <- plot_df |>
    mutate(
      bar_pattern = unname(series_patterns[as.character(series)]),
      bar_pattern_fill = if_else(
        bar_pattern == "none",
        unname(series_fills[as.character(series)]),
        unname(series_pattern_fills[as.character(series)])
      ),
      bar_pattern_density = if_else(bar_pattern == "none", 0, pattern_density)
    )

  bracket_df <- overlap_bracket_df(plot_df)
  bg_df <- bind_rows(
    bracket_df |> mutate(group = "Binary") |> transmute(metric_num, xmin = binary_xmin, xmax = binary_xmax, group),
    bracket_df |> mutate(group = "3-class") |> transmute(metric_num, xmin = sev_xmin, xmax = sev_xmax, group)
  ) |>
    mutate(bg_fill = if_else(group == "Binary", light_gsvi, white))

  legend_overrides <- list(
    pattern_type = unname(series_patterns[series_levels]),
    pattern_fill = c(light_gsvi, light_gsc, stripe_gsvi, stripe_gsc),
    pattern_colour = c(light_gsvi, light_gsc, stripe_gsvi, stripe_gsc),
    pattern_density = c(0, 0, pattern_density, pattern_density),
    pattern_spacing = c(0.01, 0.01, pattern_spacing, pattern_spacing),
    pattern_angle = c(0, 0, pattern_angle, pattern_angle)
  )

  p <- ggplot() +
    geom_rect(
      data = bg_df,
      aes(xmin = xmin, xmax = xmax, ymin = 0, ymax = 100),
      fill = alpha(bg_df$bg_fill, 0.06),
      colour = NA
    ) +
    scale_fill_manual(values = series_fills, labels = series_labels, name = NULL) +
    scale_pattern_type_manual(values = c(none = "none", stripe = "stripe"), guide = "none") +
    scale_pattern_fill_identity(guide = "none") +
    scale_pattern_colour_identity(guide = "none") +
    scale_pattern_density_continuous(guide = "none") +
    geom_col_pattern(
      data = plot_df,
      aes(
        x = bar_x,
        y = score_pct,
        fill = series,
        pattern_type = bar_pattern,
        pattern_fill = bar_pattern_fill,
        pattern_colour = bar_pattern_fill,
        pattern_density = bar_pattern_density
      ),
      width = BAR_WIDTH,
      colour = "white",
      linewidth = 0.45,
      pattern_spacing = pattern_spacing,
      pattern_angle = pattern_angle
    ) +
    geom_text(
      data = plot_df,
      aes(x = bar_x, y = score_pct, label = sprintf("%.1f%%", score_pct)),
      vjust = -0.35,
      size = 2.7,
      fontface = "bold",
      colour = "#3d2b1f"
    ) +
    guides(
      fill = guide_legend(nrow = 1, override.aes = legend_overrides),
      pattern_fill = "none",
      pattern_colour = "none",
      pattern_type = "none",
      pattern_density = "none"
    ) +
    coord_cartesian(ylim = c(0, 100), clip = "off") +
    scale_x_continuous(
      breaks = unique(plot_df$metric_num),
      labels = METRIC_LEVELS,
      expand = expansion(mult = c(0.08, 0.08))
    ) +
    scale_y_continuous(breaks = seq(0, 100, 25), expand = expansion(mult = c(0, 0.05))) +
    labs(x = NULL, y = "Score (%)") +
    map_theme() +
    overlap_axis_theme() +
    theme(legend.margin = margin(t = 6, r = 0, b = 2, l = 0), plot.margin = margin(t = 4, r = 12, b = 28, l = 8))

  add_overlap_brackets(p, bracket_df)
}

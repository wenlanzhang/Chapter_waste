#!/usr/bin/env Rscript
# Step 3, figure 0 — baseline YOLO training diagnostics.
#   0_Baseline_YOLO_training_curves.png
#     (A) training / validation loss by epoch
#     (B) validation mAP by epoch, with the selected checkpoint marked
#
# This is the detector before any of the held-out evaluation that follows: it
# shows that the baseline model was trained to convergence and that the
# checkpoint carried forward is the one Ultralytics selected, rather than a
# stopping point chosen after seeing the test results.
#
# The "validation" curve here is Ultralytics' own internal split, not the
# independent held-out set used in figures 1-2. Verified from the run's config
# and the surviving split lists rather than assumed:
#
#   args.yaml          data: Data/Train0315_695/Waste.yaml, split: val
#   dataSet/train.txt  625 images
#   dataSet/val.txt     70 images, zero overlap with train, all inside the 695 pool
#
# So the val columns are 70 of the same 695 training images. The held-out set is
# independent of both: 0 of its 180 images appear in that val split or anywhere
# in the 695 pool, and sampling/heldout_GSVI_p100_test.csv flags in_training_695
# as False for all 180. The two mAP figures are therefore not comparable, and
# the caption says which is which.
#
# Input:  Waste/img/train_SVI_Yolo/results.csv   (raw Ultralytics training log,
#         an artefact of the training run itself — not produced by this pipeline)
# Writes: 3_waste_identification/0_baseline_yolo_training_checkpoint.csv

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(patchwork)
  library(readr)
  library(scales)
})

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg))) else "."
source(file.path(script_dir, "..", "R", "chapter_paths.R"))
source(file.path(script_dir, "..", "R", "map_theme.R"))
source(file.path(script_dir, "..", "R", "chapter_colours.R"))

DATA_ROOT <- phd_data_root
RESULTS_CSV <- file.path(DATA_ROOT, "Waste/img/train_SVI_Yolo/results.csv")
FIG_DIR <- file.path(script_dir, "..", "Figure", "3_waste_identification")
OUT_META <- file.path(chapter_data_root, "3_waste_identification",
                      "0_baseline_yolo_training_checkpoint.csv")

if (!file.exists(RESULTS_CSV)) {
  stop("Missing ", RESULTS_CSV,
       "\nThis is the raw Ultralytics log from the baseline training run; it is not produced by this pipeline.")
}
raw <- read_csv(RESULTS_CSV, show_col_types = FALSE)
# Ultralytics CSVs often have leading spaces in column names
names(raw) <- trimws(names(raw))
raw <- raw %>% mutate(across(everything(), ~ if (is.character(.x)) trimws(.x) else .x))

num_cols <- c(
  "epoch",
  "train/box_loss", "train/cls_loss", "train/dfl_loss",
  "val/box_loss", "val/cls_loss", "val/dfl_loss",
  "metrics/precision(B)", "metrics/recall(B)",
  "metrics/mAP50(B)", "metrics/mAP50-95(B)"
)
for (col in num_cols) {
  if (col %in% names(raw)) raw[[col]] <- suppressWarnings(as.numeric(raw[[col]]))
}

df <- raw %>%
  transmute(
    epoch = epoch,
    train_box = `train/box_loss`,
    train_cls = `train/cls_loss`,
    train_dfl = `train/dfl_loss`,
    val_box = `val/box_loss`,
    val_cls = `val/cls_loss`,
    val_dfl = `val/dfl_loss`,
    precision = `metrics/precision(B)`,
    recall = `metrics/recall(B)`,
    mAP50 = `metrics/mAP50(B)`,
    mAP50_95 = `metrics/mAP50-95(B)`
  )

# Selected checkpoint = Ultralytics best.pt criterion ≈ max mAP50 (fitness)
best_row <- df %>%
  filter(is.finite(mAP50)) %>%
  slice_max(order_by = mAP50, n = 1, with_ties = FALSE)
best_epoch <- best_row$epoch[[1]]

meta <- tibble(
  run_dir = file.path(DATA_ROOT, "Waste/img/train_SVI_Yolo"),
  results_csv = RESULTS_CSV,
  weights_best = file.path(DATA_ROOT, "Waste/img/train_SVI_Yolo/weights/best.pt"),
  weights_last = file.path(DATA_ROOT, "Waste/img/train_SVI_Yolo/weights/last.pt"),
  n_epochs_logged = nrow(df),
  selected_checkpoint_epoch = best_epoch,
  selected_by = "max metrics/mAP50(B) on validation (Ultralytics best.pt)",
  selected_mAP50 = best_row$mAP50[[1]],
  selected_mAP50_95 = best_row$mAP50_95[[1]],
  selected_precision = best_row$precision[[1]],
  selected_recall = best_row$recall[[1]],
  training_note = "Baseline YOLO11x on Train0315_695 (610 GSVI + 85 SC; 100% SC-slot retention)",
  # Split provenance, so the figure's "validation" is traceable without opening
  # the training machine's config.
  data_yaml = "Waste/img/Train0315_695/Waste.yaml",
  n_train_images = 625L,
  n_internal_val_images = 70L,
  val_split_note = paste(
    "Internal split of the 695-image training pool (dataSet/train.txt + val.txt,",
    "no overlap). Not the independent held-out set used in figures 1-2, which",
    "shares no images with this pool."
  )
)
dir.create(dirname(OUT_META), recursive = TRUE, showWarnings = FALSE)
write_csv(meta, OUT_META)
message("Wrote ", OUT_META)

loss_long <- df %>%
  select(epoch, train_box, train_cls, val_box, val_cls) %>%
  pivot_longer(-epoch, names_to = "series", values_to = "loss") %>%
  filter(is.finite(loss)) %>%
  mutate(
    series = factor(
      series,
      levels = c("train_box", "val_box", "train_cls", "val_cls"),
      labels = c("Train box", "Val box", "Train cls", "Val cls")
    )
  )

# Early Ultralytics val/cls can spike to hundreds; keep plot readable
loss_ylim <- max(10, as.numeric(quantile(loss_long$loss[loss_long$loss < 20], 0.99, na.rm = TRUE)) * 1.15)

map_long <- df %>%
  select(epoch, mAP50, mAP50_95) %>%
  pivot_longer(-epoch, names_to = "metric", values_to = "score") %>%
  filter(is.finite(score)) %>%
  mutate(
    score_pct = score * 100,
    metric = factor(
      metric,
      levels = c("mAP50", "mAP50_95"),
      labels = c("mAP@0.50", "mAP@0.50:0.95")
    )
  )

p_loss <- ggplot(loss_long, aes(x = epoch, y = loss, colour = series)) +
  geom_line(linewidth = 0.55, alpha = 0.9) +
  geom_vline(xintercept = best_epoch, linetype = "dashed", colour = "#4D2D18", linewidth = 0.6) +
  annotate(
    "label",
    x = best_epoch,
    y = loss_ylim,
    label = sprintf("best.pt  epoch %s", best_epoch),
    hjust = -0.05,
    vjust = 1.1,
    size = 3,
    fill = "white",
    colour = "#4D2D18"
  ) +
  coord_cartesian(ylim = c(0, loss_ylim)) +
  scale_colour_manual(
    values = c(
      "Train box" = "#6B4226",
      "Val box" = "#C9A27F",
      "Train cls" = "#8B5A3C",
      "Val cls" = "#D4CCC2"
    ),
    name = NULL
  ) +
  labs(
    title = "(A) Training and validation loss",
    x = "Epoch",
    y = "Loss"
  ) +
  map_theme() +
  theme(
    legend.position = "bottom",
    plot.title = element_text(face = "bold", size = 11, colour = "#2f2f2f")
  )

p_map <- ggplot(map_long, aes(x = epoch, y = score_pct, colour = metric)) +
  geom_line(linewidth = 0.7) +
  geom_vline(xintercept = best_epoch, linetype = "dashed", colour = "#4D2D18", linewidth = 0.6) +
  geom_point(
    data = map_long %>% filter(epoch == best_epoch),
    size = 2.4
  ) +
  scale_colour_manual(
    values = c("mAP@0.50" = "#6B4226", "mAP@0.50:0.95" = "#C9A27F"),
    name = NULL
  ) +
  labs(
    title = "(B) Validation mAP",
    subtitle = sprintf(
      "Selected checkpoint: epoch %s (validation mAP@0.50 = %.1f%%; mAP@0.50:0.95 = %.1f%%)",
      best_epoch,
      100 * best_row$mAP50[[1]],
      100 * best_row$mAP50_95[[1]]
    ),
    x = "Epoch",
    y = "Score (%)"
  ) +
  map_theme() +
  theme(
    legend.position = "bottom",
    plot.title = element_text(face = "bold", size = 11, colour = "#2f2f2f"),
    plot.subtitle = element_text(size = 9, colour = "#6B5B4F")
  )

panel <- (p_loss / p_map) +
  plot_annotation(
    title = "Baseline YOLO11x training and internal-validation diagnostics",
    subtitle = "Train0315_695 — 610 GSVI + 85 self-collected images; dashed line marks the selected best.pt checkpoint",
    caption = paste0(
      "Source: the raw Ultralytics training log (Waste/img/train_SVI_Yolo/results.csv). Checkpoint selected by maximum validation mAP@0.50, Ultralytics' own best.pt rule.\n",
      "\"Validation\" here is an internal split — 70 of the same 695 training images (dataSet/val.txt). It is not the independent held-out set used in figures 1 and 2,\n",
      "which shares no images with this training pool, so the mAP values in the two places are not comparable.\n",
      "Early-epoch val/cls loss spikes into the hundreds and the y-axis in (A) is clipped so the converged region stays readable."
    ),
    theme = theme(
      plot.title = element_text(face = "bold", size = 13, hjust = 0.5, colour = "#2f2f2f"),
      plot.subtitle = element_text(size = 9.5, hjust = 0.5, colour = "#6B5B4F", margin = margin(b = 8)),
      plot.caption = element_text(size = 8, hjust = 0, colour = "#7A6A5C")
    )
  )

dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)
out_png <- file.path(FIG_DIR, "0_Baseline_YOLO_training_curves.png")
ggsave(out_png, plot = panel, width = 9, height = 8.5, dpi = 600, bg = "white")
message("Wrote ", out_png)

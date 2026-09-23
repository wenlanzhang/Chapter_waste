# Analysis arms for R plot scripts. Mirrors lib/arms.py (keys, labels, naming).
# Plot scripts take --arm=<key> (default "gsvi"); GSVI figure names are unchanged
# so existing figures stay put, other arms get an "_<key>" suffix.
ARM_KEYS <- c("gsvi", "gsvi_selfcollected")
ARM_LABELS <- c(
  gsvi = "GSVI only",
  gsvi_selfcollected = "GSVI + self-collected"
)
ARM_COLUMNS <- c(gsvi = "GSVI", gsvi_selfcollected = "GSVI + SC")

parse_arm_arg <- function(args = commandArgs(trailingOnly = TRUE), default = "gsvi") {
  hit <- grep("^--arm=", args, value = TRUE)
  arm <- if (length(hit)) sub("^--arm=", "", hit[1]) else default
  if (!arm %in% ARM_KEYS) {
    stop("Unknown --arm=", arm, "; expected one of: ", paste(ARM_KEYS, collapse = ", "))
  }
  arm
}

arm_label <- function(arm) ARM_LABELS[[arm]]

# Data-file tag: Step 2 style "buf50m" -> "buf50m_gsvi"
arm_tagged <- function(tag, arm) paste0(tag, "_", arm)

# Step 1 / Step 2c style "<stem>_<arm>_32737.gpkg"
arm_filename <- function(stem, arm, suffix = "_32737", ext = "gpkg") {
  paste0(stem, "_", arm, suffix, ".", ext)
}

# Figure suffix: "" for gsvi (legacy names), "_<arm>" otherwise
arm_fig_suffix <- function(arm) if (identical(arm, "gsvi")) "" else paste0("_", arm)

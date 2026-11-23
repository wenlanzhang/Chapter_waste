# Shared setup for the pop_adjusted sensitivity figures. Expects `repo_root`.
# Optional trailing arg --data-subdir=<run> (default worldpop_2020, the manuscript sample).
source(file.path(repo_root, "R", "chapter_paths.R"))
source(file.path(repo_root, "R", "chapter_colours.R"))

.subdir_arg <- grep("^--data-subdir=", commandArgs(trailingOnly = TRUE), value = TRUE)
data_subdir <- if (length(.subdir_arg)) sub("^--data-subdir=", "", .subdir_arg[[1]]) else "worldpop_2020"

POP_DIR <- file.path(chapter_data_root, "5_spatial_pattern", "Signed_distance", "pop_adjusted", data_subdir)
FIG_DIR <- file.path(repo_root, "Figure", "5_spatial_pattern", "Signed_distance", "pop_adjusted", data_subdir)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

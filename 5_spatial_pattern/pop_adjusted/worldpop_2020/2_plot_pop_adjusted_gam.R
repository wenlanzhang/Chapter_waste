#!/usr/bin/env Rscript
# Plot MDP adjusted effects for the WorldPop 2020 sensitivity run.

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

parent_plot <- normalizePath(file.path(script_dir, "..", "2_plot_pop_adjusted_gam.R"))
status <- system2(
  "Rscript",
  c(
    parent_plot,
    "--data-subdir=worldpop_2020",
    "--fig-subdir=worldpop_2020",
    paste0(
      "--pop-caption=",
      shQuote(
        "WorldPop unconstrained Kenya 2020 (ken_ppp_2020), used as a static density covariate (not matched to panorama year)."
      )
    ),
    paste0(
      "--run-hint=",
      shQuote("python 5_spatial_pattern/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py")
    )
  )
)
quit(status = status)

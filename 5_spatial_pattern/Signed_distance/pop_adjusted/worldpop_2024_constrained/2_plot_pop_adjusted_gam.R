#!/usr/bin/env Rscript
# Plot MDP adjusted effects (and the residual maps) for the WorldPop constrained
# 2024 sensitivity run. Not the manuscript sample: the parent scripts default to
# WorldPop unconstrained 2020 (worldpop_2020/).

args_cli <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_cli, value = TRUE)
script_dir <- if (length(file_arg)) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  "."
}

sub <- "worldpop_2024_constrained"
caption <- "WorldPop Constrained Kenya 2024 (100 m), used as a static density covariate (not matched to panorama year)."
hint <- "python 5_spatial_pattern/Signed_distance/pop_adjusted/worldpop_2024_constrained/1_pop_adjusted_gam.py"

for (parent in c("2_plot_pop_adjusted_gam.R", "3_plot_mdp_residual_map.R")) {
  status <- system2(
    "Rscript",
    c(
      normalizePath(file.path(script_dir, "..", parent)),
      paste0("--data-subdir=", sub),
      paste0("--fig-subdir=", sub),
      paste0("--pop-caption=", shQuote(caption)),
      paste0("--run-hint=", shQuote(hint))
    )
  )
  if (status != 0) quit(status = status)
}

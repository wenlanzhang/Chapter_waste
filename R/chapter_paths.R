# Shared data roots for Steps 0–7. Override with PHD_DATA_ROOT.
phd_data_root <- Sys.getenv(
  "PHD_DATA_ROOT",
  unset = "/Users/wenlanzhang/Downloads/PhD_UCL/Data"
)
chapter_data_root <- file.path(phd_data_root, "Chapter_waste")

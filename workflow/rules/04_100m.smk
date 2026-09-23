GRID100M = grid100_dir()
GRID100M_THESIS = GRID100M / "thesis_table"
GRID100M_FIG = FIG / "4_100m"

GRID100M_GRID = GRID100M / "1_Nairobi_indicator_grid100m_gsvi_32737.gpkg"
CROWD_VALIDATION = PHD_DATA / "Waste" / "IDEAMaps" / "260701validation" / "validation-dataset.csv"

# Only two tables go in the chapter; the rest are working outputs beside the grid.
GRID100M_DATA = [
    GRID100M_GRID,
    GRID100M_THESIS / "table_3_indicator_summary.csv",
    GRID100M_THESIS / "table_4_validation.csv",
]

GRID100M_FIGS = [
    GRID100M_FIG / "1_Nairobi_indicator_panels_grid100m_gsvi.png",
    GRID100M_FIG / "2_Nairobi_indicator_validation_grid100m_gsvi.png",
    GRID100M_FIG / "3_Nairobi_indicator_validation_map_grid100m_gsvi.png",
]


rule indicator_build:
    input:
        lambda wc: str(active_grid_gpkg()),
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    output:
        GRID100M_GRID,
        GRID100M / "1_indicator_direct.csv",
        GRID100M / "1_indicator_direct_detail.csv",
        GRID100M / "2_indicator_interpolation.csv",
        GRID100M / "2_indicator_support_distance.csv",
        GRID100M_THESIS / "table_3_indicator_summary.csv",
    shell:
        "python {REPO_ROOT}/4_100m/1_indicator_build.py"


rule indicator_validation:
    input:
        GRID100M_GRID,
        CROWD_VALIDATION,
    output:
        GRID100M / "2_Nairobi_indicator_validation_cells.csv",
        GRID100M_THESIS / "table_4_validation.csv",
        GRID100M / "4_validation_detail.csv",
        GRID100M / "5_validation_confusion.csv",
    shell:
        "python {REPO_ROOT}/4_100m/2_validation.py"


rule plot_indicator_panels:
    input:
        GRID100M_GRID,
    output:
        GRID100M_FIG / "1_Nairobi_indicator_panels_grid100m_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/4_100m/1plot_indicator_panels.R"


rule plot_indicator_validation:
    input:
        GRID100M / "4_validation_detail.csv",
        GRID100M / "5_validation_confusion.csv",
    output:
        GRID100M_FIG / "2_Nairobi_indicator_validation_grid100m_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/4_100m/2plot_validation.R"


rule plot_validation_map:
    input:
        GRID100M_GRID,
        GRID100M / "2_Nairobi_indicator_validation_cells.csv",
    output:
        GRID100M_FIG / "3_Nairobi_indicator_validation_map_grid100m_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/4_100m/3plot_validation_map.R"

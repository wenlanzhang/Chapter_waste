EXTEND_DATA = [
    EXT / "Nairobi_grid_100m_extended_32737.gpkg",
]

EXTEND_FIGS = [
    FIG / "0_extend_grid" / "Grid_extension_angela_vs_fill.png",
]


if USE_EXTENDED:

    rule extend_grid:
        input:
            PREP / "Nairobi_grid_100m_32737.gpkg",
            PREP / "Nairobi_boundary_polygon_32737.gpkg",
        output:
            EXT / "Nairobi_grid_100m_extended_32737.gpkg",
        shell:
            "python {REPO_ROOT}/0_extend_grid/1_extend_grid.py"

    rule provenance_extended:
        input:
            EXT / "Nairobi_grid_100m_extended_32737.gpkg",
            PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
            PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        output:
            EXT / "Nairobi_indicator_provenance_summary_extended.csv",
        shell:
            "python {REPO_ROOT}/0_extend_grid/2_provenance_extended.py"

    rule plot_extended_grid:
        input:
            EXT / "Nairobi_grid_100m_extended_32737.gpkg",
            EXT / "Nairobi_indicator_provenance_summary_extended.csv",
        output:
            FIG / "0_extend_grid" / "Grid_extension_angela_vs_fill.png",
        shell:
            "Rscript {REPO_ROOT}/0_extend_grid/3_plot_extended_grid.R"

EXTEND_DATA = [
    EXT / "Nairobi_grid_100m_extended_32737.gpkg",
]

EXTEND_FIGS = [
    FIG / "0_extend_grid" / "Grid_extension_angela_vs_fill.png",
    *[FIG / "0_extend_grid" / f"Indicator_provenance_100m_extended_{arm}.png" for arm in ARM_KEYS],
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
            *[arm.svi_image_gpkg() for arm in ARMS.values()],
            *[arm.waste_gpkg() for arm in ARMS.values()],
        output:
            [EXT / f"Nairobi_indicator_provenance_summary_extended_{arm}.csv" for arm in ARM_KEYS],
        shell:
            "python {REPO_ROOT}/0_extend_grid/2_provenance_extended.py"

    rule plot_extended_grid:
        input:
            EXT / "Nairobi_grid_100m_extended_32737.gpkg",
            [EXT / f"Nairobi_indicator_provenance_summary_extended_{arm}.csv" for arm in ARM_KEYS],
        output:
            EXTEND_FIGS,
        shell:
            "Rscript {REPO_ROOT}/0_extend_grid/3_plot_extended_grid.R"

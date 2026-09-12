COMPARE_DATA = [
    CMP / "thesis_table" / "Nairobi_compare_sources_table.csv",
]

COMPARE_FIGS = [
    FIG / "4_compare" / "SVI_sources_gsvi_selfcollected.png",
    FIG / "4_compare" / "Waste_sources_gsvi_selfcollected.png",
    FIG / "4_compare" / "Sources_gsvi_selfcollected_comparison.png",
]


rule compare_sources_table:
    input:
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    output:
        CMP / "thesis_table" / "Nairobi_compare_sources_table.csv",
    shell:
        "python {REPO_ROOT}/4_compare/1_compare_sources_table.py"


rule plot_svi_sources_map:
    input:
        PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        FIG / "4_compare" / "SVI_sources_gsvi_selfcollected.png",
    shell:
        "Rscript {REPO_ROOT}/4_compare/1_plot_svi_sources_map.R"


rule plot_waste_sources_map:
    input:
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        FIG / "4_compare" / "Waste_sources_gsvi_selfcollected.png",
    shell:
        "Rscript {REPO_ROOT}/4_compare/2_plot_waste_sources_map.R"


rule plot_sources_comparison_panel:
    input:
        PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        FIG / "4_compare" / "Sources_gsvi_selfcollected_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/4_compare/3_plot_sources_comparison_panel.R"

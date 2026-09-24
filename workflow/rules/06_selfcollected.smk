SC = selfcollected_dir()
SC_SOURCES = SC / "1_sources"
SC_SOURCES_THESIS = SC_SOURCES / "thesis_table"
SC_FIG = FIG / "6_selfcollected"
SC_FIG_SOURCES = SC_FIG / "1_sources"
SC_FIG_ID = SC_FIG / "2_identification"

SELFCOLLECTED_DATA = [
    SC_SOURCES / "1_Nairobi_sc_coverage_grid100m_32737.gpkg",
    SC_SOURCES / "1_Nairobi_sc_new_cells_32737.gpkg",
    SC_SOURCES / "1_Nairobi_sc_coverage_summary.csv",
    SC_SOURCES / "1_Nairobi_sc_new_cells_location.csv",
    SC_SOURCES_THESIS / "table_6_1_sc_sources.csv",
    SC_SOURCES_THESIS / "table_6_1_sc_coverage.csv",
]

SELFCOLLECTED_FIGS = [
    SC_FIG_SOURCES / "1_Sources_gsvi_selfcollected.png",
    SC_FIG_SOURCES / "2_SC_new_coverage_100m.png",
    SC_FIG_ID / "1_Heldout_sc_sensitivity_metrics.png",
    SC_FIG_ID / "1_Heldout_sc_sensitivity_bars.png",
    SC_FIG_ID / "2_Heldout_stage_comparison_metrics.png",
    SC_FIG_ID / "2_Heldout_stage_comparison_bars.png",
]


# 6.1 — what self-collected imagery adds to the observation frame ------------
rule sc_coverage:
    input:
        lambda wc: str(active_grid_gpkg()),
        PREP / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SELFCOLLECTED_DATA,
    shell:
        "python {REPO_ROOT}/6_selfcollected/1_sources/1_sc_coverage.py"


rule plot_sc_sources:
    input:
        PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_FIG_SOURCES / "1_Sources_gsvi_selfcollected.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/1_sources/1plot_sources_comparison.R"


rule plot_sc_new_coverage:
    input:
        SC_SOURCES / "1_Nairobi_sc_coverage_grid100m_32737.gpkg",
        SC_SOURCES / "1_Nairobi_sc_coverage_summary.csv",
    output:
        SC_FIG_SOURCES / "2_SC_new_coverage_100m.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/1_sources/2plot_new_coverage_map.R"


# 6.2 — the SC training mix, scored on Step 3's held-out set ------------------
rule plot_sc_sensitivity:
    input:
        WASTE_ID_THESIS / "table_4_sc_sensitivity_detail.csv",
    output:
        SC_FIG_ID / "1_Heldout_sc_sensitivity_metrics.png",
        SC_FIG_ID / "1_Heldout_sc_sensitivity_bars.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/2_identification/1plot_sc_sensitivity.R"


rule plot_sc_stage_comparison:
    input:
        WASTE_ID_THESIS / "table_4_sc_sensitivity_detail.csv",
    output:
        SC_FIG_ID / "2_Heldout_stage_comparison_metrics.png",
        SC_FIG_ID / "2_Heldout_stage_comparison_bars.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/2_identification/2plot_stage_comparison.R"

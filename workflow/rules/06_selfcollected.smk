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


# 6.3 — the 100 m indicator with self-collected imagery ----------------------
SC_IND = SC / "3_indicator"
SC_IND_THESIS = SC_IND / "thesis_table"
SC_FIG_IND = SC_FIG / "3_indicator"

SELFCOLLECTED_DATA += [
    SC_IND / "1_Nairobi_sc_indicator_grid100m_32737.gpkg",
    SC_IND / "1_sc_indicator_provenance.csv",
    SC_IND / "1_sc_indicator_class_change.csv",
    SC_IND / "1_sc_indicator_changed_cells.csv",
    SC_IND_THESIS / "table_6_3_indicator_effect.csv",
]
SELFCOLLECTED_FIGS += [SC_FIG_IND / "1_SC_indicator_effect.png"]


rule sc_indicator:
    input:
        lambda wc: str(active_grid_gpkg()),
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_IND / "1_Nairobi_sc_indicator_grid100m_32737.gpkg",
        SC_IND / "1_sc_indicator_provenance.csv",
        SC_IND / "1_sc_indicator_class_change.csv",
        SC_IND / "1_sc_indicator_changed_cells.csv",
        SC_IND_THESIS / "table_6_3_indicator_effect.csv",
    shell:
        "python {REPO_ROOT}/6_selfcollected/3_indicator/1_sc_indicator.py"


rule plot_sc_indicator:
    input:
        SC_IND / "1_Nairobi_sc_indicator_grid100m_32737.gpkg",
        SC_IND / "1_sc_indicator_provenance.csv",
    output:
        SC_FIG_IND / "1_SC_indicator_effect.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/3_indicator/1plot_sc_indicator.R"


# 6.4 — spatial pattern with self-collected imagery ---------------------------
SC_PAT = SC / "4_pattern"
SC_PAT_THESIS = SC_PAT / "thesis_table"
SC_FIG_PAT = SC_FIG / "4_pattern"

SC_HDBSCAN_OUT = [
    SC_PAT / "1_Nairobi_sc_hdbscan_gsvi_32737.gpkg",
    SC_PAT / "1_Nairobi_sc_hdbscan_gsvi_selfcollected_32737.gpkg",
    SC_PAT / "1_Nairobi_sc_hotspots_gsvi_32737.gpkg",
    SC_PAT / "1_Nairobi_sc_hotspots_gsvi_selfcollected_32737.gpkg",
    SC_PAT / "1_sc_hdbscan_new_locations.csv",
    SC_PAT_THESIS / "table_6_4_hdbscan_comparison.csv",
]
SC_PATTERN_OUT = [
    SC_PAT / "2_Nairobi_sc_gam_frame.csv",
    SC_PAT / "2_Nairobi_sc_gam_curve.csv",
    SC_PAT / "2_sc_settlement_contingency.csv",
    SC_PAT_THESIS / "table_6_4_settlement_comparison.csv",
    SC_PAT_THESIS / "table_6_4_gam_comparison.csv",
]

SELFCOLLECTED_DATA += SC_HDBSCAN_OUT + SC_PATTERN_OUT
SELFCOLLECTED_FIGS += [
    SC_FIG_PAT / "1_SC_hotspot_comparison.png",
    SC_FIG_PAT / "2_SC_settlement_gam_comparison.png",
]


rule sc_hdbscan:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    output:
        SC_HDBSCAN_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/1_sc_hdbscan.py"


rule plot_sc_hotspots:
    input:
        SC_HDBSCAN_OUT,
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_FIG_PAT / "1_SC_hotspot_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/1plot_sc_hotspots.R"


rule sc_settlement_gam:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        COV / "3_Nairobi_sviwaste_points_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_PATTERN_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/2_sc_settlement_gam.py"


rule plot_sc_settlement_gam:
    input:
        SC_PATTERN_OUT,
    output:
        SC_FIG_PAT / "2_SC_settlement_gam_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/2plot_sc_settlement_gam.R"

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
    SC_SOURCES / "1_sc_coverage_change.csv",
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
SC_VALIDATION_OUT = [
    SC_IND / "2_sc_validation_cells.csv",
    SC_IND / "2_sc_validation_confusion.csv",
    SC_IND / "2_sc_validation_detail.csv",
    SC_IND_THESIS / "table_6_3_validation_comparison.csv",
]
SELFCOLLECTED_DATA += SC_VALIDATION_OUT
SELFCOLLECTED_FIGS += [
    SC_FIG_IND / "1_SC_indicator_effect.png",
    SC_FIG_IND / "2_SC_validation_comparison.png",
]


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


rule sc_validation:
    input:
        SC_IND / "1_Nairobi_sc_indicator_grid100m_32737.gpkg",
        PREP / "Nairobi_validation_grid_32737.gpkg",
    output:
        SC_VALIDATION_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/3_indicator/2_sc_validation.py"


rule plot_sc_validation:
    input:
        SC_IND / "2_sc_validation_detail.csv",
    output:
        SC_FIG_IND / "2_SC_validation_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/3_indicator/2plot_sc_validation.R"


# 6.4 — spatial pattern with self-collected imagery ---------------------------
# Mirrors Step 5's three blocks so the two are read side by side.
SC_PAT = SC / "4_pattern"
SC_HDB = SC_PAT / "HDBSCAN"
SC_SET = SC_PAT / "settlement"
SC_SD = SC_PAT / "Signed_distance"
SC_FIG_PAT = SC_FIG / "4_pattern"

SC_HDBSCAN_OUT = [
    SC_HDB / "1_Nairobi_sc_hdbscan_gsvi_32737.gpkg",
    SC_HDB / "1_Nairobi_sc_hdbscan_gsvi_selfcollected_32737.gpkg",
    SC_HDB / "1_Nairobi_sc_hotspots_gsvi_32737.gpkg",
    SC_HDB / "1_Nairobi_sc_hotspots_gsvi_selfcollected_32737.gpkg",
    SC_HDB / "1_sc_hdbscan_new_locations.csv",
    SC_HDB / "1_sc_hdbscan_label_transitions.csv",
    SC_HDB / "1_sc_hdbscan_comparison.csv",
    SC_HDB / "thesis_table" / "table_6_4_hdbscan_stability.csv",
]
SC_CONTEXT_OUT = [
    SC_HDB / "2_Nairobi_sc_cluster_context_gsvi_32737.gpkg",
    SC_HDB / "2_Nairobi_sc_cluster_context_gsvi_selfcollected_32737.gpkg",
    SC_HDB / "2_Nairobi_sc_cluster_composition_gsvi.csv",
    SC_HDB / "2_Nairobi_sc_cluster_composition_gsvi_selfcollected.csv",
    SC_HDB / "2_sc_cluster_context_summary.csv",
    SC_HDB / "thesis_table" / "table_6_4_cluster_context.csv",
]
SC_SETTLEMENT_OUT = [
    SC_SET / "1_sc_settlement_contingency.csv",
    SC_SET / "1_sc_settlement_zone_summary.csv",
    SC_SET / "1_sc_settlement_nnr.csv",
    SC_SET / "thesis_table" / "table_6_4_settlement_comparison.csv",
]
SC_GAM_OUT = [
    SC_SD / "1_Nairobi_sc_gam_curve.csv",
    SC_SD / "1_Nairobi_sc_rate_by_band.csv",
    SC_SD / "thesis_table" / "table_6_4_gam_comparison.csv",
]

SELFCOLLECTED_DATA += SC_HDBSCAN_OUT + SC_CONTEXT_OUT + SC_SETTLEMENT_OUT + SC_GAM_OUT
SELFCOLLECTED_FIGS += [
    SC_FIG_PAT / "HDBSCAN" / "1_SC_hotspot_comparison.png",
    SC_FIG_PAT / "HDBSCAN" / "2_SC_cluster_composition.png",
    SC_FIG_PAT / "settlement" / "1_SC_settlement_comparison.png",
    SC_FIG_PAT / "Signed_distance" / "1_SC_gam_comparison.png",
]

# Both arms' Step 2c layers; the second arm is what makes the combined frame.
SC_FRAME_INPUTS = [
    COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
    COV / "3_Nairobi_sviwaste_points_gsvi_selfcollected_32737.gpkg",
    PREP / "Nairobi_slum_polygon_32737.gpkg",
]


# 6.4a clustering
rule sc_hdbscan:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    output:
        SC_HDBSCAN_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/HDBSCAN/1_sc_hdbscan.py"


rule plot_sc_hotspots:
    input:
        SC_HDBSCAN_OUT,
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_FIG_PAT / "HDBSCAN" / "1_SC_hotspot_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/HDBSCAN/1plot_sc_hotspots.R"


rule sc_cluster_context:
    input:
        SC_HDBSCAN_OUT,
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SC_CONTEXT_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/HDBSCAN/2_sc_cluster_settlement_context.py"


rule plot_sc_cluster_composition:
    input:
        SC_CONTEXT_OUT,
    output:
        SC_FIG_PAT / "HDBSCAN" / "2_SC_cluster_composition.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/HDBSCAN/2plot_sc_cluster_composition.R"


# 6.4b settlement association (2x2, zone density, observation-frame NNR)
rule sc_settlement_association:
    input:
        SC_FRAME_INPUTS,
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        SC_SETTLEMENT_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/settlement/1_sc_settlement_association.py"


rule plot_sc_settlement:
    input:
        SC_SETTLEMENT_OUT,
    output:
        SC_FIG_PAT / "settlement" / "1_SC_settlement_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/settlement/1plot_sc_settlement.R"


# 6.4c signed-distance GAM
rule sc_signed_distance_gam:
    input:
        SC_FRAME_INPUTS,
    output:
        SC_GAM_OUT,
    shell:
        "python {REPO_ROOT}/6_selfcollected/4_pattern/Signed_distance/1_sc_signed_distance_gam.py"


rule plot_sc_gam:
    input:
        SC_GAM_OUT,
    output:
        SC_FIG_PAT / "Signed_distance" / "1_SC_gam_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/6_selfcollected/4_pattern/Signed_distance/1plot_sc_gam.R"


# Step 6 anchor — the pipeline-wide mitigation summary ------------------------
SELFCOLLECTED_DATA += [SC / "thesis_table" / "table_6_0_mitigation_summary.csv"]


rule sc_mitigation_summary:
    input:
        SC_SOURCES / "1_Nairobi_sc_coverage_summary.csv",
        WASTE_ID_THESIS / "table_4_sc_sensitivity.csv",
        SC_IND / "1_sc_indicator_provenance.csv",
        SC_IND / "1_sc_indicator_changed_cells.csv",
        SC_IND_THESIS / "table_6_3_validation_comparison.csv",
        SC_HDB / "1_sc_hdbscan_comparison.csv",
        SC_SET / "thesis_table" / "table_6_4_settlement_comparison.csv",
        SC_SD / "thesis_table" / "table_6_4_gam_comparison.csv",
    output:
        SC / "thesis_table" / "table_6_0_mitigation_summary.csv",
    shell:
        "python {REPO_ROOT}/6_selfcollected/0_mitigation_summary.py"

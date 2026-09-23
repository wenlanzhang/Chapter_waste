# Step 5 — spatial pattern of waste-positive GSVI panoramas (GSVI arm only).
# The GSVI-vs-self-collected mitigation comparison stays archived: with one arm
# there is nothing to compare.
PAT_HDB = PAT / "HDBSCAN"
PAT_SET = PAT / "settlement"
PAT_SD = PAT / "Signed_distance"
PAT_POP = PAT_SD / "pop_adjusted"
PAT_HDB_PER = PAT_HDB / "period_stratified_robustness"
PAT_SD_PER = PAT_SD / "period_stratified_robustness"
PAT_POP_2020 = PAT_POP / "worldpop_2020"
PAT_FIG = FIG / "5_spatial_pattern"

SPATIAL_DATA = [
    PAT_HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    PAT_HDB / "Nairobi_waste_hdbscan_gsvi_settlement_context_32737.gpkg",
    PAT_HDB / "Nairobi_hdbscan_cluster_sizes_gsvi.csv",
    PAT_SET / "Nairobi_nnr_observation_frame_summary.csv",
    PAT_SET / "thesis_table" / "settlement_association.csv",
    PAT_SD / "Nairobi_signed_distance_gam_summary.csv",
    PAT_POP / "Nairobi_pop_adjusted_model_metrics.csv",
    # sensitivity / robustness
    PAT_HDB / "Nairobi_hdbscan_param_sweep.csv",
    PAT_HDB_PER / "Nairobi_period_hdbscan_summary.csv",
    PAT_SD_PER / "Nairobi_period_signed_distance_gam_summary.csv",
    PAT_POP_2020 / "Nairobi_pop_adjusted_model_metrics.csv",
    PAT_POP / "thesis_table" / "settlement_by_density_band.csv",
]

SPATIAL_FIGS = [
    PAT_FIG / "HDBSCAN" / "Waste_HDBSCAN_context_gsvi.png",
    PAT_FIG / "HDBSCAN" / "Cluster_Size_Distribution_gsvi.png",
    PAT_FIG / "HDBSCAN" / "Cluster_Composition_By_Distance_gsvi.png",
    PAT_FIG / "settlement" / "Settlement_waste_positive_rate.png",
    PAT_FIG / "settlement" / "Settlement_waste_positive_share.png",
    PAT_FIG / "settlement" / "Settlement_area_normalised_density.png",
    PAT_FIG / "settlement" / "Settlement_rate_vs_composition.png",
    PAT_FIG / "settlement" / "NNR_observation_frame_null.png",
    PAT_FIG / "settlement" / "Temporal_waste_positive_rate_by_year.png",
    PAT_FIG / "settlement" / "Temporal_prevalence_ratio_by_year.png",
    PAT_FIG / "Signed_distance" / "Signed_distance_gam_curve.png",
    PAT_FIG / "Signed_distance" / "Signed_distance_gam_curve_inset.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_effects.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_distance.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_population.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_mdp_residual_map.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_mdp_excess_prob_map.png",
    PAT_FIG / "HDBSCAN" / "period_stratified_robustness" / "Period_HDBSCAN_comparison.png",
    PAT_FIG / "Signed_distance" / "period_stratified_robustness" / "Period_signed_distance_gam_curve.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_gam_effects.png",
    PAT_FIG / "Signed_distance" / "pop_adjusted" / "Settlement_by_density_band.png",
]

SPATIAL_SRC = f"{REPO_ROOT}/5_spatial_pattern"


rule hdbscan_cluster:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
    output:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        PAT_HDB / "Nairobi_waste_hdbscan_summary_gsvi.csv",
    shell:
        "python {SPATIAL_SRC}/HDBSCAN/3_hdbscan_waste.py"


rule hdbscan_settlement_context:
    input:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_settlement_context_32737.gpkg",
        PAT_HDB / "Nairobi_hdbscan_cluster_distance_composition_gsvi.csv",
    shell:
        "python {SPATIAL_SRC}/HDBSCAN/7_hdbscan_settlement_context.py"


rule hdbscan_cluster_sizes:
    input:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_settlement_context_32737.gpkg",
    output:
        PAT_HDB / "Nairobi_hdbscan_cluster_sizes_gsvi.csv",
        PAT_HDB / "Nairobi_hdbscan_cluster_size_summary_gsvi.csv",
    shell:
        "python {SPATIAL_SRC}/HDBSCAN/9_cluster_size_distribution.py"


rule plot_hdbscan:
    input:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        PAT_HDB / "Nairobi_hdbscan_cluster_sizes_gsvi.csv",
        PAT_HDB / "Nairobi_hdbscan_cluster_distance_composition_gsvi.csv",
    output:
        PAT_FIG / "HDBSCAN" / "Waste_HDBSCAN_context_gsvi.png",
        PAT_FIG / "HDBSCAN" / "Cluster_Size_Distribution_gsvi.png",
        PAT_FIG / "HDBSCAN" / "Cluster_Composition_By_Distance_gsvi.png",
    shell:
        "Rscript {SPATIAL_SRC}/HDBSCAN/7_plot_hdbscan_context_map.R && "
        "Rscript {SPATIAL_SRC}/HDBSCAN/9_plot_cluster_size_distribution.R && "
        "Rscript {SPATIAL_SRC}/HDBSCAN/8_plot_cluster_distance_composition.R"


rule settlement_association:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        PAT_SET / "Nairobi_nnr_observation_frame_summary.csv",
        PAT_SET / "thesis_table" / "settlement_association.csv",
        PAT_SET / "thesis_table" / "settlement_zone_summary.csv",
    shell:
        "python {SPATIAL_SRC}/settlement/1_nnr_observation_frame.py && "
        "python {SPATIAL_SRC}/settlement/2_settlement_association.py && "
        "python {SPATIAL_SRC}/settlement/5_temporal_robustness.py"


rule plot_settlement:
    input:
        PAT_SET / "thesis_table" / "settlement_association.csv",
        PAT_SET / "Nairobi_nnr_observation_frame_summary.csv",
    output:
        PAT_FIG / "settlement" / "Settlement_waste_positive_rate.png",
        PAT_FIG / "settlement" / "Settlement_waste_positive_share.png",
        PAT_FIG / "settlement" / "Settlement_area_normalised_density.png",
        PAT_FIG / "settlement" / "Settlement_rate_vs_composition.png",
        PAT_FIG / "settlement" / "NNR_observation_frame_null.png",
        PAT_FIG / "settlement" / "Temporal_waste_positive_rate_by_year.png",
        PAT_FIG / "settlement" / "Temporal_prevalence_ratio_by_year.png",
    shell:
        "Rscript {SPATIAL_SRC}/settlement/3_plot_settlement_association.R && "
        "Rscript {SPATIAL_SRC}/settlement/6_plot_temporal_robustness.R"


rule signed_distance_gam:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        PAT_SD / "Nairobi_signed_distance_gam_summary.csv",
    shell:
        "python {SPATIAL_SRC}/Signed_distance/1_signed_distance_gam.py"


rule plot_signed_distance_gam:
    input:
        PAT_SD / "Nairobi_signed_distance_gam_summary.csv",
    output:
        PAT_FIG / "Signed_distance" / "Signed_distance_gam_curve.png",
        PAT_FIG / "Signed_distance" / "Signed_distance_gam_curve_inset.png",
    shell:
        "Rscript {SPATIAL_SRC}/Signed_distance/2_plot_signed_distance_gam.R"


# Sensitivity of the signed-distance GAM: does the gradient survive population
# density and a spatial field? Slow (thin-plate field over ~75k panoramas).
rule pop_adjusted_gam:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PAT_POP / "ken_pop_2024_CN_100m_R2025A_v1.tif",
    output:
        PAT_POP / "Nairobi_pop_adjusted_model_metrics.csv",
        PAT_POP / "Nairobi_pop_adjusted_summary.csv",
    shell:
        "python {SPATIAL_SRC}/Signed_distance/pop_adjusted/1_pop_adjusted_gam.py"


rule plot_pop_adjusted_gam:
    input:
        PAT_POP / "Nairobi_pop_adjusted_model_metrics.csv",
    output:
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_effects.png",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_distance.png",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_gam_population.png",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_mdp_residual_map.png",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Pop_adjusted_mdp_excess_prob_map.png",
    shell:
        "Rscript {SPATIAL_SRC}/Signed_distance/pop_adjusted/2_plot_pop_adjusted_gam.R && "
        "Rscript {SPATIAL_SRC}/Signed_distance/pop_adjusted/3_plot_mdp_residual_map.R"


# --- sensitivity / robustness -------------------------------------------------
rule hdbscan_param_sweep:
    input:
        PAT_HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    output:
        PAT_HDB / "Nairobi_hdbscan_param_sweep.csv",
    shell:
        "python {SPATIAL_SRC}/HDBSCAN/3b_hdbscan_param_sweep.py"


rule period_hdbscan:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
    output:
        PAT_HDB_PER / "Nairobi_period_hdbscan_summary.csv",
        PAT_FIG / "HDBSCAN" / "period_stratified_robustness" / "Period_HDBSCAN_comparison.png",
    shell:
        "python {SPATIAL_SRC}/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py && "
        "Rscript {SPATIAL_SRC}/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R"


rule period_signed_distance_gam:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        PAT_SD_PER / "Nairobi_period_signed_distance_gam_summary.csv",
        PAT_FIG / "Signed_distance" / "period_stratified_robustness" / "Period_signed_distance_gam_curve.png",
    shell:
        "python {SPATIAL_SRC}/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py && "
        "Rscript {SPATIAL_SRC}/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R"


# Same nested GAMs against unconstrained WorldPop 2020, to check the population
# control is not specific to the constrained 2024 raster.
rule pop_adjusted_gam_worldpop_2020:
    input:
        COV / "3_Nairobi_sviwaste_points_gsvi_32737.gpkg",
    output:
        PAT_POP_2020 / "Nairobi_pop_adjusted_model_metrics.csv",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_gam_effects.png",
    shell:
        "python {SPATIAL_SRC}/Signed_distance/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py && "
        "Rscript {SPATIAL_SRC}/Signed_distance/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R"


# Non-parametric companion to the nested GAMs: within equal-count density bands,
# does being inside a settlement still raise the waste rate?
rule settlement_by_density_band:
    input:
        PAT_POP / "Nairobi_pop_adjusted_gam_frame.csv",
    output:
        PAT_POP / "Nairobi_settlement_by_density_band.csv",
        PAT_POP / "thesis_table" / "settlement_by_density_band.csv",
        PAT_FIG / "Signed_distance" / "pop_adjusted" / "Settlement_by_density_band.png",
    shell:
        "python {SPATIAL_SRC}/Signed_distance/pop_adjusted/4_settlement_by_density_band.py && "
        "Rscript {SPATIAL_SRC}/Signed_distance/pop_adjusted/4plot_settlement_by_density_band.R"

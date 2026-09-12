HDB = PAT / "HDBSCAN"
SETL = PAT / "settlement"
DECAY = PAT / "Distance_decay"
SIG = PAT / "Signed_distance"
POP = PAT / "pop_adjusted"
KDE = PAT / "KDE"

SPATIAL_DATA = [
    SETL / "Nairobi_nnr_observation_frame_summary.csv",
    SETL / "Nairobi_settlement_chisquare.csv",
    SETL / "Nairobi_temporal_robustness_by_year.csv",
    DECAY / "Nairobi_negexp_params.csv",
    SIG / "Nairobi_signed_distance_gam_summary.csv",
    SIG / "period_stratified_robustness" / "Nairobi_period_signed_distance_gam_summary.csv",
    POP / "Nairobi_pop_adjusted_summary.csv",
    POP / "worldpop_2020" / "Nairobi_pop_adjusted_summary.csv",
    HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    HDB / "thesis_table" / "Nairobi_mitigation_comparison_table.csv",
    HDB / "Nairobi_hdbscan_n_positive_views_summary.csv",
    HDB / "Nairobi_hdbscan_100m_sensitivity_summary.csv",
    HDB / "Nairobi_hdbscan_settlement_context_summary_comparison.csv",
    HDB / "Nairobi_hdbscan_cluster_size_summary_comparison.csv",
    HDB / "period_stratified_robustness" / "Nairobi_period_hdbscan_summary.csv",
    KDE / "Nairobi_kde_params.csv",
]

SPATIAL_FIGS = [
    FIG / "5_spatial_pattern" / "settlement" / "NNR_observation_frame_null.png",
    FIG / "5_spatial_pattern" / "settlement" / "Temporal_waste_positive_rate_by_year.png",
    FIG / "5_spatial_pattern" / "Distance_decay" / "Distance_decay_negexp.png",
    FIG / "5_spatial_pattern" / "Distance_decay" / "NegExp_Panoids_vs_WastePositive.png",
    FIG / "5_spatial_pattern" / "Signed_distance" / "Signed_distance_gam_curve.png",
    FIG / "5_spatial_pattern" / "Signed_distance" / "period_stratified_robustness" / "Period_signed_distance_gam_curve.png",
    FIG / "5_spatial_pattern" / "pop_adjusted" / "Pop_adjusted_gam_effects.png",
    FIG / "5_spatial_pattern" / "pop_adjusted" / "Pop_adjusted_mdp_residual_map.png",
    FIG / "5_spatial_pattern" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_gam_effects.png",
    FIG / "5_spatial_pattern" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_mdp_residual_map.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Waste_HDBSCAN_gsvi.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Hotspot_area_difference_gsvi_selfcollected.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Mitigation_new_obs_stacked_bar.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "HDBSCAN_100m_cell_sensitivity.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Waste_HDBSCAN_context_gsvi.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Cluster_Composition_By_Distance_gsvi.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "Cluster_Size_Distribution_gsvi.png",
    FIG / "5_spatial_pattern" / "HDBSCAN" / "period_stratified_robustness" / "Period_HDBSCAN_comparison.png",
    FIG / "5_spatial_pattern" / "KDE" / "KDE_hotspot_comparison.png",
]


rule nnr_observation_frame:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        SETL / "Nairobi_nnr_observation_frame_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/settlement/1_nnr_observation_frame.py"


rule settlement_association:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        SETL / "Nairobi_settlement_chisquare.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/settlement/2_settlement_association.py"


rule plot_settlement_association:
    input:
        SETL / "Nairobi_nnr_observation_frame_summary.csv",
        SETL / "Nairobi_settlement_chisquare.csv",
    output:
        FIG / "5_spatial_pattern" / "settlement" / "NNR_observation_frame_null.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/settlement/3_plot_settlement_association.R"


rule temporal_robustness:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SETL / "Nairobi_temporal_robustness_by_year.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/settlement/5_temporal_robustness.py"


rule plot_temporal_robustness:
    input:
        SETL / "Nairobi_temporal_robustness_by_year.csv",
    output:
        FIG / "5_spatial_pattern" / "settlement" / "Temporal_waste_positive_rate_by_year.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/settlement/6_plot_temporal_robustness.R"


rule distance_decay:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        DECAY / "Nairobi_negexp_params.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py"


rule plot_distance_decay:
    input:
        DECAY / "Nairobi_negexp_params.csv",
    output:
        FIG / "5_spatial_pattern" / "Distance_decay" / "Distance_decay_negexp.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/Distance_decay/2_plot_distance_decay.R"


rule plot_negexp_notebook_style:
    input:
        DECAY / "Nairobi_negexp_params.csv",
    output:
        FIG / "5_spatial_pattern" / "Distance_decay" / "NegExp_Panoids_vs_WastePositive.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/Distance_decay/3_plot_negexp_notebook_style.R"


rule signed_distance_gam:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SIG / "Nairobi_signed_distance_gam_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/Signed_distance/1_signed_distance_gam.py"


rule plot_signed_distance_gam:
    input:
        SIG / "Nairobi_signed_distance_gam_summary.csv",
    output:
        FIG / "5_spatial_pattern" / "Signed_distance" / "Signed_distance_gam_curve.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/Signed_distance/2_plot_signed_distance_gam.R"


rule period_signed_distance_gam:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        SIG / "period_stratified_robustness" / "Nairobi_period_signed_distance_gam_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py"


rule plot_period_signed_distance_gam:
    input:
        SIG / "period_stratified_robustness" / "Nairobi_period_signed_distance_gam_summary.csv",
    output:
        FIG / "5_spatial_pattern" / "Signed_distance" / "period_stratified_robustness" / "Period_signed_distance_gam_curve.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R"


rule pop_adjusted_gam:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        POP / "Nairobi_pop_adjusted_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py"


rule plot_pop_adjusted_gam:
    input:
        POP / "Nairobi_pop_adjusted_summary.csv",
    output:
        FIG / "5_spatial_pattern" / "pop_adjusted" / "Pop_adjusted_gam_effects.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/pop_adjusted/2_plot_pop_adjusted_gam.R"


rule plot_mdp_residual_map:
    input:
        POP / "Nairobi_pop_adjusted_summary.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "pop_adjusted" / "Pop_adjusted_mdp_residual_map.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R"


rule pop_adjusted_gam_worldpop_2020:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        POP / "worldpop_2020" / "Nairobi_pop_adjusted_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py"


rule plot_pop_adjusted_gam_worldpop_2020:
    input:
        POP / "worldpop_2020" / "Nairobi_pop_adjusted_summary.csv",
    output:
        FIG / "5_spatial_pattern" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_gam_effects.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R"


rule plot_mdp_residual_map_worldpop_2020:
    input:
        POP / "worldpop_2020" / "Nairobi_pop_adjusted_summary.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "pop_adjusted" / "worldpop_2020" / "Pop_adjusted_mdp_residual_map.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R --data-subdir=worldpop_2020 --fig-subdir=worldpop_2020"


rule hdbscan_waste:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    output:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        HDB / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py"


rule hdbscan_mitigation_comparison:
    input:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        HDB / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        COV / "Nairobi_sviwaste_points.gpkg",
    output:
        HDB / "thesis_table" / "Nairobi_mitigation_comparison_table.csv",
        HDB / "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/4_mitigation_comparison.py"


rule hdbscan_cluster_views:
    input:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    output:
        HDB / "Nairobi_hdbscan_n_positive_views_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/5_hdbscan_cluster_views.py"


rule hdbscan_100m_sensitivity:
    input:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        HDB / "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg",
        STEP3_GRID,
        COV / "Nairobi_sviwaste_points.gpkg",
    output:
        HDB / "Nairobi_hdbscan_100m_sensitivity_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/6_hdbscan_100m_sensitivity.py"


rule hdbscan_settlement_context:
    input:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        HDB / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        HDB / "Nairobi_hdbscan_settlement_context_summary_comparison.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py"


rule hdbscan_cluster_size_distribution:
    input:
        HDB / "Nairobi_hdbscan_settlement_context_summary_comparison.csv",
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
    output:
        HDB / "Nairobi_hdbscan_cluster_size_summary_comparison.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py"


rule period_hdbscan:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
    output:
        HDB / "period_stratified_robustness" / "Nairobi_period_hdbscan_summary.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py"


rule kde_hotspots:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        KDE / "Nairobi_kde_params.csv",
    shell:
        "python {REPO_ROOT}/5_spatial_pattern/KDE/1_kde_hotspots.py"


rule plot_hdbscan_map:
    input:
        HDB / "Nairobi_waste_hdbscan_gsvi_32737.gpkg",
        HDB / "Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Waste_HDBSCAN_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/3_plot_hdbscan_map.R"


rule plot_hotspot_difference_map:
    input:
        HDB / "Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg",
        HDB / "thesis_table" / "Nairobi_mitigation_comparison_table.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Hotspot_area_difference_gsvi_selfcollected.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R"


rule plot_new_obs_stacked_bar:
    input:
        HDB / "thesis_table" / "Nairobi_mitigation_comparison_table.csv",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Mitigation_new_obs_stacked_bar.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/4_plot_new_obs_stacked_bar.R"


rule plot_hdbscan_100m_sensitivity:
    input:
        HDB / "Nairobi_hdbscan_100m_sensitivity_summary.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "HDBSCAN_100m_cell_sensitivity.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/6_plot_hdbscan_100m_sensitivity.R"


rule plot_hdbscan_context_map:
    input:
        HDB / "Nairobi_hdbscan_settlement_context_summary_comparison.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Waste_HDBSCAN_context_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R"


rule plot_cluster_distance_composition:
    input:
        HDB / "Nairobi_hdbscan_settlement_context_summary_comparison.csv",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Cluster_Composition_By_Distance_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R"


rule plot_cluster_size_distribution:
    input:
        HDB / "Nairobi_hdbscan_cluster_size_summary_comparison.csv",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "Cluster_Size_Distribution_gsvi.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R"


rule plot_period_hdbscan:
    input:
        HDB / "period_stratified_robustness" / "Nairobi_period_hdbscan_summary.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "HDBSCAN" / "period_stratified_robustness" / "Period_HDBSCAN_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R"


rule plot_kde_comparison:
    input:
        KDE / "Nairobi_kde_params.csv",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "5_spatial_pattern" / "KDE" / "KDE_hotspot_comparison.png",
    shell:
        "Rscript {REPO_ROOT}/5_spatial_pattern/KDE/2_plot_kde_comparison.R"

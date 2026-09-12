STEP3_GRID = (
    EXT / "Nairobi_grid_100m_extended_32737.gpkg"
    if USE_EXTENDED
    else PREP / "Nairobi_grid_100m_32737.gpkg"
)

GRID_DATA = [
    GRID100 / "grid" / "Nairobi_grid_coverage_cell_counts.csv",
    GRID100 / "validation" / "Nairobi_validation_summary.csv",
    GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    GRID100 / "grid" / "Nairobi_indicator_provenance_summary.csv",
    GRID100 / "thesis_table" / "table_validation_by_provenance.csv",
]

GRID_FIGS = [
    FIG / "3_100m" / "Grid_coverage_summary.png",
    FIG / "3_100m" / "Validation_confusion_matrix.png",
    FIG / "3_100m" / "Validation_mitigation_accuracy.png",
    FIG / "3_100m" / "Validation_mitigation_severity.png",
    FIG / "3_100m" / "Validation_mitigation_self_overlap.png",
    FIG / "3_100m" / "Indicator_provenance_100m.png",
]


rule grid_coverage:
    input:
        STEP3_GRID,
        PREP / "Nairobi_road_line_32737.gpkg",
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    output:
        GRID100 / "grid" / "Nairobi_grid_coverage_cell_counts.csv",
    shell:
        "python {REPO_ROOT}/3_100m/1_grid_coverage.py"


rule plot_grid_coverage:
    input:
        GRID100 / "grid" / "Nairobi_grid_coverage_cell_counts.csv",
    output:
        FIG / "3_100m" / "Grid_coverage_summary.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/1_plot_grid_coverage_matrix.R"


rule validation_analysis:
    input:
        PREP / "Nairobi_validation_grid_32737.gpkg",
    output:
        GRID100 / "validation" / "Nairobi_validation_summary.csv",
    shell:
        "python {REPO_ROOT}/3_100m/2_validation_analysis.py"


rule plot_validation_confusion:
    input:
        GRID100 / "validation" / "Nairobi_validation_summary.csv",
    output:
        FIG / "3_100m" / "Validation_confusion_matrix.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/2_plot_validation_confusion_matrix.R"


rule mitigation_validation:
    input:
        STEP3_GRID,
        PREP / "Nairobi_validation_grid_32737.gpkg",
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    output:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    shell:
        "python {REPO_ROOT}/3_100m/3_mitigation_validation.py"


rule plot_mitigation_validation:
    input:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    output:
        FIG / "3_100m" / "Validation_mitigation_accuracy.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/3_plot_mitigation_validation.R"


rule plot_mitigation_validation_severity:
    input:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    output:
        FIG / "3_100m" / "Validation_mitigation_severity.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/3_plot_mitigation_validation_severity.R"


rule plot_mitigation_validation_overlap:
    input:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    output:
        FIG / "3_100m" / "Validation_mitigation_self_overlap.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/3_plot_mitigation_validation_overlap.R"


rule indicator_provenance:
    input:
        STEP3_GRID,
        PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    output:
        GRID100 / "grid" / "Nairobi_indicator_provenance_summary.csv",
    shell:
        "python {REPO_ROOT}/3_100m/4_indicator_provenance.py"


rule plot_indicator_provenance:
    input:
        GRID100 / "grid" / "Nairobi_indicator_provenance_summary.csv",
        STEP3_GRID,
    output:
        FIG / "3_100m" / "Indicator_provenance_100m.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/4_plot_indicator_provenance_map.R"


rule validation_by_provenance:
    input:
        GRID100 / "grid" / "Nairobi_indicator_provenance_summary.csv",
        PREP / "Nairobi_validation_grid_32737.gpkg",
        GRID100 / "validation" / "Nairobi_validation_summary.csv",
    output:
        GRID100 / "thesis_table" / "table_validation_by_provenance.csv",
    shell:
        "python {REPO_ROOT}/3_100m/5_validation_by_provenance.py"


rule mitigation_validation_sensitivity:
    input:
        STEP3_GRID,
        PREP / "Nairobi_validation_grid_32737.gpkg",
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    output:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_sensitivity_comparison.csv",
    shell:
        "python {REPO_ROOT}/3_100m/3_mitigation_validation_sensitivity.py"


rule plot_mitigation_overlap_pattern:
    input:
        GRID100 / "mitigation" / "Nairobi_validation_mitigation_comparison.csv",
    output:
        FIG / "3_100m" / "Validation_mitigation_self_overlap_pattern.png",
    shell:
        "Rscript {REPO_ROOT}/3_100m/3_plot_mitigation_validation_overlap_pattern.R"

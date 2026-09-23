WASTE_ID = waste_id_dir()
WASTE_ID_YOLO = WASTE_ID / "yolo"
WASTE_ID_QWEN = WASTE_ID / "qwen"
WASTE_ID_THESIS = WASTE_ID / "thesis_table"
WASTE_ID_FIG = FIG / "3_waste_identification"

# Held-out inputs are produced outside this pipeline: the YOLO val runs write
# yolo/, the Qwen notebooks write qwen/qwen_labels_<scenario>.csv.
HELDOUT_SUMMARY = WASTE_ID_YOLO / "heldout_GSVI_val_summary.csv"
HELDOUT_PREDICTIONS = WASTE_ID_YOLO / "heldout_GSVI_p100_image_level_predictions.csv"
HELDOUT_QWEN_LABELS = sorted(WASTE_ID_QWEN.glob("qwen_labels_sc_*.csv"))

WASTE_ID_DATA = [
    WASTE_ID_THESIS / "table_1_yolo_detection.csv",
    WASTE_ID_THESIS / "table_2_yolo_qwen_heldout.csv",
    WASTE_ID_THESIS / "table_2_yolo_qwen_heldout_ci.csv",
    WASTE_ID_THESIS / "table_2_yolo_qwen_heldout_detail.csv",
    WASTE_ID_THESIS / "table_3_qwen_replicates.csv",
    WASTE_ID_THESIS / "table_4_sc_sensitivity.csv",
]

WASTE_ID_FIGS = [
    WASTE_ID_FIG / "1_Heldout_yolo_qwen_panel.png",
    WASTE_ID_FIG / "1_Heldout_qwen_only_panel.png",
    WASTE_ID_FIG / "2_Heldout_qwen_replicate_stability.png",
    WASTE_ID_FIG / "3_Heldout_validation_binary_metrics.png",
    WASTE_ID_FIG / "3_Heldout_validation_binary_bars.png",
    WASTE_ID_FIG / "4_Heldout_validation_stage_metrics.png",
    WASTE_ID_FIG / "4_Heldout_validation_stage_bars.png",
]


rule heldout_metrics:
    input:
        HELDOUT_SUMMARY,
        HELDOUT_PREDICTIONS,
        HELDOUT_QWEN_LABELS,
    output:
        WASTE_ID_DATA,
        WASTE_ID_THESIS / "table_1_yolo_detection_detail.csv",
        WASTE_ID_THESIS / "table_4_sc_sensitivity_detail.csv",
    shell:
        "python {REPO_ROOT}/3_waste_identification/1_heldout_metrics.py"


rule plot_heldout_panel:
    input:
        WASTE_ID_THESIS / "table_2_yolo_qwen_heldout_detail.csv",
    output:
        WASTE_ID_FIG / "1_Heldout_yolo_qwen_panel.png",
        WASTE_ID_FIG / "1_Heldout_qwen_only_panel.png",
    shell:
        "Rscript {REPO_ROOT}/3_waste_identification/1plot_heldout_panel.R"


rule plot_qwen_stability:
    input:
        WASTE_ID_THESIS / "table_3_qwen_replicates.csv",
    output:
        WASTE_ID_FIG / "2_Heldout_qwen_replicate_stability.png",
    shell:
        "Rscript {REPO_ROOT}/3_waste_identification/2plot_qwen_stability.R"


rule plot_sc_sensitivity:
    input:
        WASTE_ID_THESIS / "table_4_sc_sensitivity_detail.csv",
    output:
        WASTE_ID_FIG / "3_Heldout_validation_binary_metrics.png",
        WASTE_ID_FIG / "3_Heldout_validation_binary_bars.png",
    shell:
        "Rscript {REPO_ROOT}/3_waste_identification/3plot_sc_sensitivity.R"


rule plot_stage_comparison:
    input:
        WASTE_ID_THESIS / "table_4_sc_sensitivity_detail.csv",
    output:
        WASTE_ID_FIG / "4_Heldout_validation_stage_metrics.png",
        WASTE_ID_FIG / "4_Heldout_validation_stage_bars.png",
    shell:
        "Rscript {REPO_ROOT}/3_waste_identification/4plot_stage_comparison.R"

# Step 7 — Held-out GSVI validation

Independent **180-image GSVI held-out** evaluation of Step 6 YOLO (`sc_100pct`) and YOLO→Qwen.

Canonical images:  
`$PHD_DATA_ROOT/Waste/img/7_heldout_validation/20260807_heldout_GSVI_p100_label/`

---

## Layout

```
7_heldout_validation/
├── 0_run_all.py                              # one-shot regenerate
├── 1_build_training_inventory.py
├── 2_prepare_heldout_gsvi.py
├── 3_Qwen_heldout_validation.ipynb           # main pipeline: Qwen on YOLO FPs only
├── 4_Qwen_yolo_positives_replicates.ipynb    # stability: Qwen ×3 on all 115 YOLO+
├── 5_build_outputs.py                        # thesis tables (+ Wilson CIs)
├── 6_plot_outputs.R                          # figures (`R/chapter_paths.R`)
├── paths.py                                  # wraps chapter_paths.py
└── README.md
```

---

## What is “main” vs “stability”

| | Main confusion matrix / thesis panel | Replication / stability |
| --- | --- | --- |
| Script | Notebook `3_` + `5_build_outputs.py` | Notebook `4_` + stability CSV |
| Qwen scope | **30 YOLO FPs** only; YOLO TPs kept | All **115 YOLO positives**, 3 runs |
| Outputs | `yolo_vs_qwen_heldout_*.csv`, CM plots | `yolo_qwen_yolo_pos_replicates.csv` (+ 3-run majority as summary) |

---

## Data

**Main pipeline inputs** (`Validation/`):

| Path | Role |
| --- | --- |
| `heldout_GSVI_p100_val_summary.csv` | YOLO box mAP + confusion counts |
| `heldout_GSVI_p100_sc100pct_fp_conf001.csv` | YOLO FP list (n=30) |
| `qwen2_vl_72b_segmind_results.csv` | Qwen Yes/No on those FPs |
| `heldout_GSVI_p100_test.csv` | Held-out inventory |

**Stability input:**

| Path | Role |
| --- | --- |
| `heldout_GSVI_p100_image_level_predictions_with_qwen.csv` | 180 rows + `Qwen2_1/2/3` |

**Outputs** (`$PHD_DATA_ROOT/Chapter_waste/7_heldout_validation/thesis_table/`):

| File | Role |
| --- | --- |
| `yolo_heldout_detection.csv` | Box mAP |
| `yolo_vs_qwen_heldout_display.csv` | **Main** metrics |
| `yolo_vs_qwen_heldout_ci_table.csv` | **Main** + Wilson CIs |
| `yolo_vs_qwen_heldout_detail.csv` | **Main** CM counts |
| `yolo_qwen_yolo_pos_replicates.csv` | Stability across Qwen2_1/2/3 + 3-run majority |
| `yolo_qwen_citywide_funnel.csv` | Citywide funnel |

**Figures:** `Figure/7_heldout_validation/`

| Figure | Content |
| --- | --- |
| `Heldout_yolo_qwen_panel.png` | **Main** metrics + CM (FP-only Qwen) |
| `Heldout_qwen_replicate_stability.png` | Repeated-inference stability on 115 YOLO+ |

---

## Run

```bash
python 7_heldout_validation/0_run_all.py
python 7_heldout_validation/0_run_all.py --skip-plots
python 7_heldout_validation/0_run_all.py --skip-stability
```

External steps:

1. Colab YOLO val → summary + FP CSV into `Validation/`
2. `3_Qwen_heldout_validation.ipynb` → main FP audit CSV
3. (Optional) `4_Qwen_yolo_positives_replicates.ipynb` → `*_with_qwen.csv` for stability
4. `python 7_heldout_validation/0_run_all.py`

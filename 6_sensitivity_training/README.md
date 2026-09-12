# Step 6 — YOLO training-mix sensitivity

**Question:** Does the waste detector depend on how much **self-collected (SC)** imagery is in **training**?

This step changes the **training set** only. Evaluation on held-out images is Step 7.

## Design (previous swap, kept)

- Fixed size: **695** images; same waste/background totals.
- Switchable **SC slots** from the original training mix (**85 SC** = 38 waste + 47 background).
- Scenarios = **% of SC slots retained**:

| Scenario | Meaning |
| --- | --- |
| `sc_100pct` | **Baseline — model used in the main chapter** (all SC kept: 610 GSVI + 85 SC) |
| `sc_75pct` / `sc_50pct` / `sc_25pct` | Fewer SC slots; replaced by GSVI |
| `sc_0pct` | **No SC** in training (SC slots filled with GSVI) |

## Scripts

- `1_training_dataset_pipeline.ipynb` — inventory, swap pools, scenario folders `sc_*pct/`
- `7_plot_baseline_training_curves.R` — baseline (`sc_100pct`) YOLO loss/mAP curves (`R/chapter_paths.R` for `PHD_DATA_ROOT`)

## Paths

| Kind | Path |
| --- | --- |
| Tables | `$PHD_DATA_ROOT/Chapter_waste/6_sensitivity_training/` |
| YOLO scenario folders | `$PHD_DATA_ROOT/Waste/img/6_sensitivity_training/sc_*pct/` (symlinks to archive) |
| Figures | `Figure/6_sensitivity_training/` |
| Frozen full dump | `6_sensitivity_archive/` + `…/6_sensitivity_archive/` + `…/sensitivity_archive/` |

## Related

- **Step 7** (`7_heldout_validation/`) — independent 180-image GSVI held-out used to **score** these trained models.

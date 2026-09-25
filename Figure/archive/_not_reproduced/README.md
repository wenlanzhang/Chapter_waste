# Archived figures with no live equivalent

Final state of the audit. Everything else under `Figure/archive/2026-09-21/`
has been rebuilt in Steps 0–6, or excluded by an explicit decision.

| File | Verdict |
| --- | --- |
| `5_spatial_pattern~HDBSCAN~Cluster_Size_Distribution_gsvi_selfcollected.png` | **Open.** The self-collected counterpart to Step 5a's cluster-size distribution; Step 6.4a has no size figure. Small gap — the merge it would show is already legible in the label transition matrix. |

Resolved since the first pass:
- `3_100m~Grid_coverage_summary.png` → rebuilt as
  `Figure/2coverage_analysis/0_Nairobi_grid_coverage_funnel.png`, on Step 2's
  current definitions rather than the archived ≥25 m road rule.
- `99_optional_SE_analysis~*` (6) → dropped. Socio-economic correlates at
  admin-unit level are a separate question from the representation-gap
  argument; the code remains in `archive/2026-09-21/99_optional_SE_analysis/`.
- `3_100m~Validation_mitigation_*` (5) → reproduced by Step 6.3b, whose
  numbers match them exactly.
- `7_heldout_validation~Heldout_validation_map_metrics.png` → the n = 107
  self-collected held-out set, excluded.

Delete this folder once the last call is made.

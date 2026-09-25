# Archived figures with no live equivalent

A last look before the archive is dropped. Everything else under
`Figure/archive/2026-09-21/` has either been rebuilt in Steps 0–6 or was
excluded by an explicit decision (KDE, distance decay, the n = 107
self-collected held-out set, `Waste_HDBSCAN_gsvi`, `HDBSCAN_100m_cell_sensitivity`).

| File | Verdict |
| --- | --- |
| `3_100m~Grid_coverage_summary.png` | **Worth rebuilding.** The City → Road → SVI → Waste funnel on the 100 m grid, as counts and as a nested share matrix. That cascade is Step 2's entire narrative and Step 2 has no figure of it — only `table_0_coverage_headline.csv`. Would need rebuilding on current definitions: the archived version uses a ≥25 m road-length rule (43,863 cells) rather than Step 2a's 50 m road-accessibility rule (56,120 cells), and the strict cell-assignment rule (22,672). |
| `5_spatial_pattern~HDBSCAN~Cluster_Size_Distribution_gsvi_selfcollected.png` | **Optional.** The self-collected counterpart to Step 5a's cluster-size distribution. Step 6.4a has no size figure. Small gap; the merge it would show is already visible in the label transition matrix. |
| `99_optional_SE_analysis~*` (6 figures) | **Out of scope, not a gap.** Socio-economic correlates of the waste rate at admin-unit level (population density r = 0.68, GRDI r = 0.39, buildings r = −0.32, RWI r = −0.20). A separate question from the representation-gap argument, never part of Steps 0–6, and its code is still in `archive/2026-09-21/99_optional_SE_analysis/` if it is ever wanted as an appendix. |

Delete this folder once the calls are made.

# Chapter_waste — Nairobi waste & SVI spatial analysis

Pipeline for cleaning, harmonising, and analysing street-view imagery (SVI), waste detections, roads, and slums in Nairobi. Python handles data processing; R produces publication-style maps.

**Study area:** Nairobi constituency boundary  
**Projected CRS:** EPSG:32737 (UTM zone 37S)

---

## Folder structure

```
Chapter_waste/
├── README.md
├── Snakefile                         # Thin wrap of Steps 0–5 (see Workflow (Snakemake))
├── chapter_paths.py                  # PHD_DATA_ROOT / Step dirs / active 100 m grid
├── lib/                              # Shared Python plumbing (CLI scripts bootstrap repo root)
│   ├── panoids.py                    # Panoid loaders (+ year, n_positive_views)
│   ├── periods.py                    # 2015–2019 / 2021–2022 capture eras
│   ├── hdbscan_fit.py                # Cluster params + fit helpers
│   ├── gam.py                        # Spline/bootstrap constants + year FE
│   ├── provenance.py                 # Direct / interpolated / unsupported labels
│   ├── road_coverage.py              # Buffer points → split road metres → H3
│   ├── roads.py                      # Road cleaning, noding, comparison
│   ├── h3_grid.py                    # H3 grid helpers
│   ├── thesis_tables.py              # Publication-style thesis tables
│   └── ideamaps.py                   # EB ratio + spatial fill + Jenks
├── workflow/
│   ├── config.yaml                   # phd_data_root, extended grid, buffers
│   ├── Snakefile
│   ├── export_dag.sh                 # rulegraph PDF
│   └── rules/                        # 00_extend_grid … 05_spatial
├── R/
│   ├── chapter_paths.R               # PHD_DATA_ROOT helper for R plots
│   ├── chapter_colours.R           # Shared brown chapter palette (maps + validation charts)
│   ├── map_theme.R                 # Shared ggplot2 theme, north arrow, scale bar, legend
│   ├── mitigation_map_theme.R      # Source/cluster map styling (4_compare, 5_spatial_pattern)
│   ├── mitigation_validation_charts.R  # Shared Step 3c mitigation chart builders
│   └── compare_sources_maps.R      # Shared SVI/waste source map builders (4_compare)
│
├── 0_extend_grid/                  # Optional: Mollweide 100 m fill of Angela grid gaps
│   ├── 1_extend_grid.py            # Keep Angela cells; fill constituency gaps (ESRI:54009)
│   ├── 2_provenance_extended.py    # Indicator provenance on extended grid (standalone)
│   └── 3_plot_extended_grid.R      # Angela-vs-fill + extended provenance maps
│
├── 1prepare_chapter_data/
│   ├── 1_prepare_chapter_data.py   # Step 1: clean & export harmonised layers
│   ├── export_validation_only.py     # Re-export validation gpkgs without full Step 1 rerun
│   ├── 2_prepare_osmnx_roads.py    # Step 1 (cont.): OSMnx roads + local vs OSMnx comparison
│   ├── road_utils.py               # Shim → lib.roads
│   ├── plot_maps.R                 # Step 1 layer preview maps (waste, SVI, slums…)
│   ├── plot_road_figures.R         # Five numbered road network figures (01–05)
│   ├── plot_road_type_composition.R
│   ├── plot_road_type_composition_osmnx.R
│   └── plot_road_network_comparison.R
│
├── 2coverage_analysis/
│   ├── h3_utils.py                 # Shim → lib.h3_grid
│   ├── thesis_tables.py            # Shim → lib.thesis_tables
│   ├── 1cityroad.py                # City → road metrics on H3 grid
│   ├── 1plot_cityroad_maps.R       # H3 choropleths + Spearman correlation figures
│   ├── 1plot_cityroad_analysis.R   # H3 metric distribution violin/histogram panels
│   ├── 2roadsvi.py                 # Road → SVI coverage by road metre (+ H3 ratios)
│   ├── 2plot_roadsvi_maps.R        # SVI gap map + H3 choropleth + hist/scatter (75/100 → buffer/)
│   ├── 3sviwaste.py                # SVI → waste-positive panoids
│   ├── 3plot_sviwaste_maps.R
│   ├── 4roadwaste.py               # Road → waste-positive panoid coverage (metres + H3)
│   └── plot_process_zoom_map.R     # Zoomed pipeline schematic (panels + layers)
│
├── 3_100m/                         # Step 3: 100 m grid coverage & validation
│   ├── output_paths.py                   # Wraps chapter_paths (active 100 m grid)
│   ├── ideamaps_grid_pipeline.py         # Shim → lib.ideamaps
│   ├── grid_classification.py            # Fixed-band ratio helpers (0.024 / 0.164 thresholds; reference only)
│   ├── 1_grid_coverage.py                # Grid cell counts + nested coverage matrix
│   ├── 1_plot_grid_coverage_matrix.R     # Bar chart + heatmap figure
│   ├── 2_validation_analysis.py          # Crowd validation vs IDEAMaps model (confusion matrices)
│   ├── 2_plot_validation_confusion_matrix.R
│   ├── 3_mitigation_validation.py        # GSVI vs G+Self on validated cells (Nairobi grid)
│   ├── 3_mitigation_validation_sensitivity.py  # Full pipeline vs raw ratio (robustness)
│   ├── 3_plot_mitigation_validation.R            # Binary metrics, all validated cells
│   ├── 3_plot_mitigation_validation_severity.R     # 3-class metrics, all validated cells
│   ├── 3_plot_mitigation_validation_overlap.R      # Combined binary + 3-class (self-overlap n=133)
│   ├── 3_plot_mitigation_validation_overlap_pattern.R  # Pattern variant (stripes = 3-class)
│   ├── 4_indicator_provenance.py         # Direct / interpolated / unsupported provenance
│   ├── 4_plot_indicator_provenance_map.R # Provenance choropleth
│   └── 5_validation_by_provenance.py     # Crowd metrics: all cells vs direct-observation subset
│
├── 4_compare/                      # Step 4: GSVI vs GSVI + self-collected source comparison
│   ├── 1_compare_sources_table.py     # Image-level counts by source (thesis table)
│   ├── 1_plot_svi_sources_map.R       # SVI imagery by source (Step 1 gpkgs)
│   ├── 2_plot_waste_sources_map.R     # Waste detections by source (Step 1 gpkgs)
│   └── 3_plot_sources_comparison_panel.R  # Two-panel A/B source comparison map
│
├── 5_spatial_pattern/              # Step 5: panoid pattern + hotspots
│   ├── panoid_locations.py           # Shim → lib.panoids
│   ├── settlement/                   # Urban-poor boundary association + NNR + temporal
│   │   ├── 1_nnr_observation_frame.py
│   │   ├── 2_settlement_association.py     # χ² / rates / density / zone table
│   │   ├── 3_plot_settlement_association.R
│   │   ├── 5_temporal_robustness.py
│   │   └── 6_plot_temporal_robustness.R
│   ├── Distance_decay/               # ECDF / NegExp distance-decay modelling
│   │   ├── 1_distance_decay_negexp.py
│   │   ├── 2_plot_distance_decay.R
│   │   └── 3_plot_negexp_notebook_style.R
│   ├── Signed_distance/              # Signed-distance logistic GAM
│   │   ├── 1_signed_distance_gam.py
│   │   ├── 2_plot_signed_distance_gam.R
│   │   └── period_stratified_robustness/
│   │       ├── 1_period_signed_distance_gam.py
│   │       └── 2_plot_period_signed_distance_gam.R
│   ├── pop_adjusted/                 # Population-adjusted signed-distance GAMs (Reviewer 3)
│   │   ├── 1_pop_adjusted_gam.py
│   │   ├── 2_plot_pop_adjusted_gam.R
│   │   ├── 3_plot_mdp_residual_map.R # Excess-occurrence residual map (MDP)
│   │   └── worldpop_2020/            # Sensitivity: unconstrained WorldPop 2020
│   │       ├── 1_pop_adjusted_gam.py
│   │       └── 2_plot_pop_adjusted_gam.R
│   ├── HDBSCAN/
│   │   ├── 3_hdbscan_waste.py            # Exp 4: HDBSCAN on panoid locations
│   │   ├── 4_mitigation_comparison.py    # gsvi vs gsvi_selfcollected
│   │   ├── 5_hdbscan_cluster_views.py    # n_positive_views descriptives
│   │   ├── 6_hdbscan_100m_sensitivity.py # 100 m-cell HDBSCAN sensitivity
│   │   ├── 3_plot_hdbscan_map.R
│   │   ├── 4_plot_new_obs_stacked_bar.R
│   │   ├── 5_plot_hotspot_difference_map.R
│   │   ├── 6_plot_hdbscan_100m_sensitivity.R
│   │   ├── 7_hdbscan_settlement_context.py   # Cluster × urban-poor distance bins
│   │   ├── 7_plot_hdbscan_context_map.R      # Context map (slums, Dandora, majors)
│   │   ├── 8_plot_cluster_distance_composition.R  # Stacked composition by distance
│   │   ├── 9_cluster_size_distribution.py         # Cluster sizes × inside/outside + silhouette
│   │   ├── 9_plot_cluster_size_distribution.R     # Violin + histogram (notebook panel)
│   │   └── period_stratified_robustness/ # Period-stratified HDBSCAN (capture eras)
│   │       ├── 1_period_hdbscan.py
│   │       └── 2_plot_period_hdbscan.R
│   └── KDE/
│       ├── 1_kde_hotspots.py             # Supplementary robustness
│       └── 2_plot_kde_comparison.R
│
├── 6_sensitivity_training/         # Step 6: SC share in YOLO *training* (0% = no SC … 100% = baseline)
│   ├── README.md
│   ├── 1_training_dataset_pipeline.ipynb  # Inventory + GSVI↔SC training swaps → sc_*pct/
│   └── 7_plot_baseline_training_curves.R  # Baseline (sc_100pct) training curves
│
├── 7_heldout_validation/           # Step 7: independent 180-image GSVI held-out *evaluation*
│   ├── README.md
│   ├── paths.py
│   ├── 0_run_all.py                # one-shot: tables + figures
│   ├── 1_build_training_inventory.py / 2_prepare_heldout_gsvi.py  # optional prep
│   ├── 3_Qwen_heldout_validation.ipynb       # legacy FP-only Qwen
│   ├── 4_Qwen_yolo_positives_replicates.ipynb  # Qwen on 115 YOLO+ ×3
│   ├── 5_build_outputs.py          # thesis tables (Wilson CIs)
│   └── 6_plot_outputs.R            # all Step 7 figures
│
├── 6_sensitivity_archive/          # Frozen previous Step 6 dump (gitignored; do not extend)
│
├── 99_optional_SE_analysis/        # Optional: admin-unit socio-economic vs waste-positive rate (not in Snakemake all)
│   ├── README.md
│   ├── 1_admin_se_waste_join.py    # Join GSVI panoids → SE admin polygons; correlations / Moran’s I
│   ├── 2_plot_se_maps.R            # Choropleths + covariate panel
│   └── 3_plot_se_correlations.R    # Correlation bars + scatter panel
│
├── del/                            # Local archive (gitignored): legacy notebooks + 3_100m_backup scripts
│
├── Figure/                         # All map outputs (PNG)
│   ├── 0_extend_grid/
│   │   ├── Grid_extension_angela_vs_fill.png
│   │   └── Indicator_provenance_100m_extended.png
│   ├── 1prepare_chapter_data/
│   ├── 2coverage_analysis/
│   ├── 3_100m/
│   │   ├── Grid_coverage_summary.png
│   │   ├── Indicator_provenance_100m.png
│   │   ├── Validation_confusion_matrix.png          # combined 3-class + binary panel
│   │   ├── Validation_confusion_matrix_severity.png
│   │   ├── Validation_confusion_matrix_binary.png
│   │   ├── Validation_mitigation_accuracy.png
│   │   ├── Validation_mitigation_severity.png
│   │   ├── Validation_mitigation_self_overlap.png
│   │   └── Validation_mitigation_self_overlap_pattern.png
│   ├── 4_compare/
│   ├── 5_spatial_pattern/
│   │   ├── settlement/
│   │   ├── Distance_decay/
│   │   ├── Signed_distance/
│   │   ├── pop_adjusted/
│   │   │   └── worldpop_2020/
│   │   ├── HDBSCAN/
│   │   └── KDE/
│   ├── 6_sensitivity_training/     # Baseline YOLO training curves
│   ├── 7_heldout_validation/       # Held-out binary / mAP charts
│   ├── 99_optional_SE_analysis/    # Optional admin SE choropleths / correlations
│   ├── 6_sensitivity_archive/      # Frozen dump figures (gitignored)
│   └── 3_100m_backup/              # Previous waste-ratio figures (gitignored)
```

**Processed data** (not in this repo) lives under:

```
/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/
├── 0_extend_grid/                  # Extended 100 m grid + standalone provenance CSVs
├── 1prepare_chapter_data/          # Harmonised GeoPackages (+ Angela grid + validation layers)
├── 2coverage_analysis/             # Coverage CSVs & GeoPackages
├── 3_100m/                         # Grid coverage, provenance, validation & mitigation (grid/, validation/, mitigation/, thesis_table/)
├── 4_compare/                      # Source comparison table (thesis_table/)
├── 5_spatial_pattern/              # Pattern analysis processed outputs
│   ├── settlement/                 # Urban-poor boundary stats + thesis_table/
│   ├── Distance_decay/             # ECDF / NegExp + thesis_table/
│   ├── Signed_distance/            # GAM (+ period) + thesis_table/
│   ├── pop_adjusted/               # WorldPop 2024 CN + pop-adjusted GAM outputs + thesis_table/
│   │   └── worldpop_2020/          # Unconstrained WorldPop 2020 sensitivity + thesis_table/
│   ├── HDBSCAN/
│   └── KDE/
├── 6_sensitivity_training/         # Training inventory + SC swap tables / scenarios/
├── 7_heldout_validation/           # 180 GSVI held-out CSVs + val summaries
└── 6_sensitivity_archive/          # Frozen previous dump
```

Previous waste-ratio scripts are archived in `del/3_100m_backup/` (local only, gitignored). Previous figures remain in `Figure/3_100m_backup/`. Previous processed outputs (tables, GeoPackages, CSVs) are archived in `Data/Chapter_waste/3_100m_backup/`.

Raw inputs are read-only from `PhD_UCL/Data/Waste/`, `Shp/`, etc.

**Shared paths:** `chapter_paths.py` (Python) and `R/chapter_paths.R` own `PHD_DATA_ROOT` (default `/Users/wenlanzhang/Downloads/PhD_UCL/Data`) and Step 0–7 output dirs. Override with `export PHD_DATA_ROOT=…`. The active 100 m grid is `chapter_paths.active_grid_gpkg()` (`USE_EXTENDED_GRID` unset keeps the exists() fallback). Snakemake sets `PYTHONPATH` to the repo root; CLI scripts add it themselves so `python path/to/script.py` still works.

**Shared Python:** import from `lib/` (`lib.roads`, `lib.panoids`, `lib.road_coverage`, …). Thin shims (`1prepare_chapter_data/road_utils.py`, `5_spatial_pattern/panoid_locations.py`, `2coverage_analysis/h3_utils.py`, `2coverage_analysis/thesis_tables.py`, `3_100m/ideamaps_grid_pipeline.py`) re-export the same names so older imports keep working.

**Shared R:** plots source `R/chapter_paths.R`. Step 3c mitigation wrappers (`3_100m/3_plot_mitigation_validation*.R`) call `R/mitigation_validation_charts.R`.

Processed GeoPackages/CSVs belong under `$PHD_DATA_ROOT/Chapter_waste/`, not next to the scripts.

---

## Workflow overview

```
Raw CSVs & shapefiles
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 1 — Data preparation (1prepare_chapter_data/)               │
│  • Harmonise waste, SVI, boundary, slums, 100 m grid, validation → GeoPackages │
│  • Build local OSM & OSMnx road layers                           │
│  • Compare sources & select road layer for downstream analysis   │
└──────────────────────────────────────────────────────────────────┘
        │
        ├──────────────────────────────────────────────────────────┐
        ▼                                                          ▼
┌──────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│ Step 0 — Extend grid (0_extend_grid/)    │   │ Step 2 — Coverage (2coverage_analysis/) │
│  [optional; after Step 1]                │   │  city → roads → SVI → waste             │
│  Mollweide 100 m fill of Angela gaps     │   └──────────────────────────────────────────┘
│  → preferred grid for Step 3 when present│              │
└──────────────────────────────────────────┘              ▼
        │                                    ┌───────────────────┐
        │                                    │ 2a. cityroad      │
        │                                    └───────────────────┘
        │                                              │
        │                                              ▼
        │                                    ┌───────────────────┐
        │                                    │ 2b. roadsvi       │
        │                                    └───────────────────┘
        │                                              │
        │                                              ▼
        │                                    ┌───────────────────┐
        │                                    │ 2c. sviwaste      │
        │                                    └───────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 3 — 100 m grid (3_100m/)                                    │
│  coverage → crowd validation → mitigation → provenance           │
│  (uses Mollweide-extended grid if 0_extend_grid outputs exist)   │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│ Step 4 — Compare  │  GSVI vs GSVI + self-collected source maps (4_compare/)
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Step 5 — Pattern │  Observation-frame NNR, settlement association, HDBSCAN/KDE (5_spatial_pattern/)
└───────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 6 — YOLO training sensitivity (6_sensitivity_training/)     │
│  SC-slot retention in *training*: 0% = no SC … 100% = baseline │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 7 — Held-out GSVI validation (7_heldout_validation/)        │
│  Independent 180-image GSVI test (does not change training)      │
└──────────────────────────────────────────────────────────────────┘
```

**Coverage hierarchy:** city (boundary) → roads → SVI sampling → waste detections

The local vs OSMnx road comparison lives inside **Step 1** — it supports choosing which cleaned road layer to feed into Step 2, not a separate analysis track.

**Grid for Step 3:** `chapter_paths.active_grid_gpkg()` (via `3_100m/output_paths.py`) prefers `0_extend_grid/Nairobi_grid_100m_extended_32737.gpkg` when present; otherwise falls back to the Angela-only Step 1 clip. Existing Angela `cell_id` values are preserved in the extension.

---

## Step 0 — Extend 100 m grid (optional)

Standalone fill of constituency gaps left by Angela’s clipped IDEAMaps grid. Does **not** overwrite Step 1 outputs; writes under `Data/Chapter_waste/0_extend_grid/`.

**Method:** Angela’s `IDEAmaps_grid-boundary-nairobi.gpkg` is an exact 100 m lattice in Mollweide / GHSL (`ESRI:54009`). This step keeps existing clipped Angela cells and `cell_id` values, then fills remaining constituency area with new Mollweide 100 m cells whose centroids fall inside the Nairobi boundary and outside the Angela clip.

| Output | Description |
| --- | --- |
| `Nairobi_grid_100m_extended_32737.gpkg` | Angela + extension cells (`grid_source`, `cell_id`) |
| `Nairobi_grid_100m_extension_cells_32737.gpkg` | Extension cells only |
| `Nairobi_grid_extension_summary.csv` | Cell counts + uncovered % before/after |

Example (current run): Angela 57,013 → +12,930 extension → **69,943** total; uncovered area ~18.7% → ~0.3%.

```bash
# Requires Step 1 (Angela clip + boundary)
python 0_extend_grid/1_extend_grid.py
python 0_extend_grid/2_provenance_extended.py   # standalone provenance on extended grid
Rscript 0_extend_grid/3_plot_extended_grid.R
```

**Figures:** `Figure/0_extend_grid/Grid_extension_angela_vs_fill.png`, `Indicator_provenance_100m_extended.png`

`2_provenance_extended.py` reuses the Step 3 IDEAMaps pipeline helpers but writes only to `0_extend_grid/` (does not touch `3_100m/` tables). For thesis provenance on the same grid used by Step 3, prefer `3_100m/4_indicator_provenance.py` after the extension exists.

---

## Step 1 — Data preparation

### 1a. Harmonised layers

**Script:** `1prepare_chapter_data/1_prepare_chapter_data.py`

Reads raw sources, applies consistent cleaning, clips to Nairobi boundary, reprojects to EPSG:32737, and writes GeoPackages.


| Output | Description | Approx. count |
| --- | --- | --- |
| `Nairobi_Waste_point_gsvi_32737.gpkg` | Waste detections, **gsvi** arm (Google only) | 3,236 |
| `Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg` | Waste detections, **gsvi_selfcollected** arm (Google + Faith/ + ZWL/) | 3,385 |
| `Nairobi_SVI_point_gsvi_32737.gpkg` | SVI panoids, **gsvi** arm (unique by `panoid`) | 76,605 |
| `Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg` | SVI panoids, **gsvi_selfcollected** arm | 79,584 |
| `Nairobi_SVI_image_gsvi_32737.gpkg` | SVI **images**, **gsvi** arm (unique by `lat`, `lon`, `img_name`) | — |
| `Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg` | SVI **images**, **gsvi_selfcollected** arm (same dedupe) | — |
| `Nairobi_boundary_polygon_32737.gpkg` | Study-area boundary | 1 |
| `Nairobi_slum_polygon_32737.gpkg` | Informal settlement polygons | 1,988 |
| `Nairobi_slum_cluster_polygon_32737.gpkg` | Merged touching slum clusters | 101 |
| `Nairobi_grid_100m_32737.gpkg` | Angela 100 m grid clipped to Nairobi boundary (centroid within) | varies |
| `Nairobi_validation_point_32737.gpkg` | IDEAMaps crowd validation clicks (lat/lon + labels), with `cell_id` | varies |
| `Nairobi_validation_grid_32737.gpkg` | One row per validated grid cell (max severity when 2+ clicks) | varies |

**Grid prep:** Raw `Waste/Angela/IDEAmaps_grid-boundary-nairobi.gpkg` is intersected with the constituency boundary and filtered to cells whose centroids fall inside the study area, then reprojected to EPSG:32737. Used by Step 3 (`3_100m/`). Optional Step 0 (`0_extend_grid/`) fills remaining constituency gaps with Mollweide 100 m cells while preserving Angela `cell_id` values; when that extended gpkg exists, Step 3 prefers it.

**Validation prep:** Raw clicks from `Waste/IDEAMaps/260701validation/validation-dataset.csv` are clipped to Nairobi, joined to the 100 m grid, and aggregated to one row per cell. When multiple validators click the same cell, both `validation_result` and `model_result` use **max severity** (0 = no waste, 1 = medium, 2 = high). Binary flags `is_waste` / `model_is_waste` are derived as `result > 0`. To re-export validation layers without rerunning all of Step 1, use `export_validation_only.py`.

**Arm vocabulary** (used in filenames throughout the pipeline):

| Slug | Meaning |
| --- | --- |
| `gsvi` | Google Street View only — excludes `Faith/` and `ZWL/` |
| `gsvi_selfcollected` | Google + Faith/ + ZWL/ self-collected imagery |

**Cleaning rules:**

- **gsvi arm:** exclude `ZWL/` and `Faith/`; waste dedupe on `lat`, `lon`, `img_name`; SVI panoid layers dedupe on `panoid`; SVI **image** layers dedupe on `lat`, `lon`, `img_name`
- **gsvi_selfcollected arm:** no dir filter; waste dedupe on `lat`, `lon`, `img_name`; SVI panoid layers use panoid (GSVI) + image key (self-collected); SVI **image** layers dedupe on `lat`, `lon`, `img_name` for all sources
- All point layers include a `source` column (`Google`, `Faith`, or `ZWL`)
- Slum clusters: connected adjacent polygons merged

```bash
conda activate geo_env_LLM
python 1prepare_chapter_data/1_prepare_chapter_data.py
Rscript 1prepare_chapter_data/plot_maps.R
```

### 1b. Local OSM roads

**Source:** `OSM_NAI_AOI.gpkg` (local OSM extract)

Three road layers are produced from the local file:


| File                                       | Processing                                        | Segments | Length    |
| ------------------------------------------ | ------------------------------------------------- | -------- | --------- |
| `Nairobi_road_01_local_raw_32737.gpkg`     | Clip + project only                               | ~45,207  | ~7,573 km |
| `Nairobi_road_03_local_cleaned_32737.gpkg` | Explode multipart lines, clip, standardise schema | ~45,209  | ~7,573 km |
| `Nairobi_road_03_local_noded_32737.gpkg`   | Cleaned → **intersection-based noding**           | ~94,584  | ~7,573 km |


**Segmentation:**

- **Geometry-based** (`local_cleaned`): one row per OSM way (or clipped piece). Used for figure 03 and local vs OSMnx comparison.
- **Intersection-based** (`local_noded`): Shapely `node()` splits every line at junctions; each row is one link between two intersections. Attributes (`osm_id`, `type`, `name`) are transferred by longest overlap.

Legacy alias: `Nairobi_road_line_32737.gpkg` → same as `local_noded`.

Shared logic lives in `lib.roads` (`clean_road_segments`, `node_road_segments`, `build_cleaned_comparison`; shim: `1prepare_chapter_data/road_utils.py`).

### 1c. OSMnx roads & comparison

**Script:** `1prepare_chapter_data/2_prepare_osmnx_roads.py` (run after step 1a)

Downloads Nairobi roads via OSMnx (`network_type='all'`), producing:


| File                                       | Processing                                | Segments | Length     |
| ------------------------------------------ | ----------------------------------------- | -------- | ---------- |
| `Nairobi_road_02_osmnx_raw_32737.gpkg`     | Download, project, truncate (no simplify) | ~587,562 | ~14,917 km |
| `Nairobi_road_04_osmnx_cleaned_32737.gpkg` | `simplify_graph` + `clean_road_segments`  | ~181,287 | ~14,917 km |

**Used by all step-2 coverage scripts:** `Nairobi_road_03_local_cleaned_32737.gpkg` (`ROAD_FILES["coverage"]` in `lib.roads`).


Also writes comparison tables and a spatial overlap layer:

- `Nairobi_road_05_cleaned_comparison_32737.gpkg` — overlap / local only / OSMnx only (3 classes)
- `Nairobi_road_comparison_summary.csv`, `Nairobi_road_type_comparison.csv`
- `Nairobi_road_05_cleaned_comparison_summary.csv`

```bash
python 1prepare_chapter_data/2_prepare_osmnx_roads.py
Rscript 1prepare_chapter_data/plot_road_figures.R
Rscript 1prepare_chapter_data/plot_road_type_composition.R
Rscript 1prepare_chapter_data/plot_road_type_composition_osmnx.R
Rscript 1prepare_chapter_data/plot_road_network_comparison.R
```

### 1d. Road figures (numbered set)

**Script:** `1prepare_chapter_data/plot_road_figures.R`


| Figure    | File                                                 | Content                                                                 |
| --------- | ---------------------------------------------------- | ----------------------------------------------------------------------- |
| 01        | `Nairobi_road_01_local_raw_32737.png`                | Local OSM, raw                                                          |
| 02        | `Nairobi_road_02_osmnx_raw_32737.png`                | OSMnx, raw                                                              |
| 03        | `Nairobi_road_03_local_cleaned_32737.png`            | Local OSM, geometry-cleaned                                             |
| 04        | `Nairobi_road_04_osmnx_cleaned_32737.png`            | OSMnx, cleaned                                                          |
| 05        | `Nairobi_road_05_cleaned_comparison_32737.png`       | 3-colour overlap map (grey = both, red = local only, blue = OSMnx only) |
| 05 hi-res | `Nairobi_road_05_cleaned_comparison_32737_hires.png` | Same as 05 at 20×20 in, 600 dpi                                         |


`plot_maps.R` covers waste, SVI, boundary, and slum layers only; road maps use `plot_road_figures.R`.

---

## Step 2 — Coverage analysis

All step-2 scripts read from `Chapter_waste/1prepare_chapter_data/` and write to `Chapter_waste/2coverage_analysis/`. Figures go to `Figure/2coverage_analysis/`.

**Road input:** `Nairobi_road_03_local_cleaned_32737.gpkg` (local OSM cleaned segments; from step 1a).

### 2a. `1cityroad.py` — City → road (H3 grid)

Road network characterisation on an **H3 hex grid** (default resolution 8, ~863 cells in Nairobi).

**Per-cell metrics:**

- Road length density (km/km²)
- Road segment count
- Intersection count & density (lightweight endpoint snapping)
- Road coverage ratio (share of cell area within road buffer)
- Road-type composition (`primary`, `secondary`, `tertiary`, `residential`, `service`, `unclassified`)

Network centrality (betweenness, closeness) was intentionally omitted — too slow at city scale.

```bash
python 2coverage_analysis/1cityroad.py
python 2coverage_analysis/1cityroad.py --h3-res 9 --road-buffer-m 50
Rscript 2coverage_analysis/1plot_cityroad_maps.R --h3-res 8 --road-buffer-m 50
Rscript 2coverage_analysis/1plot_cityroad_analysis.R --h3-res 8 --road-buffer-m 50
```

**Outputs:** `Nairobi_cityroad_grid_h3_res8_buf50m.{csv,gpkg}`, `Nairobi_cityroad_summary_h3_res8_buf50m.csv`, `Nairobi_cityroad_correlation_spearman_h3_res8_buf50m.csv`

**Figures (`1plot_cityroad_maps.R`):** 4 H3 choropleths (density, coverage, intersections, segments) plus:

- `Nairobi_cityroad_correlation_spearman_*.png` — lower-triangle Spearman heatmap
- `Nairobi_cityroad_correlation_spearman_*_scatter.png` — upper-triangle pairwise scatter matrix (3–2–1 layout)

**Distribution figure (`1plot_cityroad_analysis.R`):** `Nairobi_cityroad_analysis_h3_res8_buf50m.png` — violin + histogram per metric.

---

### 2b. `2roadsvi.py` — Road → SVI (metre level + H3 ratios)

**Unit:** Road metres within local cleaned OSM segments (one row per OSM way segment), plus H3 cell aggregates.

Each SVI panoid is buffered (default **50 m**). For each road segment, nearby buffers are unioned and the line is split into **covered** and **uncovered** parts (`segment ∩ zone` and `segment − zone`). Partially covered segments contribute metre length to both classes — uncovered sub-parts appear as gaps on the map. Covered/uncovered parts are then intersected with an H3 grid (default res **8**) to give per-cell **road-length SVI coverage ratios** (`covered_m / total_road_m`).

```bash
python 2coverage_analysis/2roadsvi.py
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 50 --h3-res 8
# If metre coverage already exists, aggregate to H3 only:
python 2coverage_analysis/2roadsvi.py --h3-only --svi-buffer-m 50 --h3-res 8
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 50 --h3-res 8
```

**Sensitivity analysis** (75 / 100 m buffers → figures under `Figure/2coverage_analysis/buffer/`):

```bash
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 75
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 100
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 75
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 100
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m 75
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m 100
```

**Outputs** (metre outputs tagged by buffer, e.g. `buf50m`; H3 by `h3_res8_buf50m`):

- `Nairobi_roadsvi_coverage_buf50m.{gpkg,csv}` — covered/uncovered line parts (for maps)
- `Nairobi_roadsvi_segments_buf50m.{gpkg,csv}` — per-segment length breakdown (`covered_length_m`, `uncovered_length_m`, `partially_covered`)
- `Nairobi_roadsvi_grid_h3_res8_buf50m.{gpkg,csv}` — per-cell road length + `svi_coverage_ratio`
- `Nairobi_roadsvi_summary_buf50m.csv` — citywide metres + H3 summary stats

**Figures (`2plot_roadsvi_maps.R`):** main (50 m) in `Figure/2coverage_analysis/`; sensitivity (75 / 100 m) in `Figure/2coverage_analysis/buffer/`
- Uncovered roads: light grey = all road metres; red = metres outside SVI buffers (`Nairobi_roadsvi_uncovered_buf50m.png`, + `_hires`)
- H3 choropleth: `svi_coverage_ratio` for cells with road (`Nairobi_roadsvi_coverage_h3_res8_buf50m.png`)
- H3 analysis: histogram + road-length scatter (`Nairobi_roadsvi_analysis_h3_res8_buf50m.png`)

**Process schematic (`plot_process_zoom_map.R`):**

- **`_panels.png`** — 2×2 step-by-step (A: H3 density, B: roads, C: SVI coverage by metre, D: waste); default 3 focus H3 cells
- **`_layers.png`** — single hex zoom with all layers; 1 focus cell, neighbour hex outlines, example SVI buffer circles, larger points

```bash
Rscript 2coverage_analysis/plot_process_zoom_map.R                      # both outputs
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=panel     # panels only
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers    # combined layers only
```

**Output:** `Nairobi_process_zoom_h3_res8_buf50m_svi50_panels.png`, `Nairobi_process_zoom_h3_res8_buf50m_svi50_layers.png`

---

### 2c. `3sviwaste.py` — SVI → waste (panoid level)

**Unit:** SVI panoid (sampling point).

Each SVI panoid is labelled **waste-positive** if its `panoid` appears in the waste dataset.


| Summary                | Value         |
| ---------------------- | ------------- |
| SVI sampling panoids   | 76,605        |
| Waste-positive panoids | 2,696 (3.52%) |
| Waste detections (raw) | 3,236         |


```bash
python 2coverage_analysis/3sviwaste.py
Rscript 2coverage_analysis/3plot_sviwaste_maps.R
```

**Outputs:** `Nairobi_sviwaste_points.{gpkg,csv}`, `Nairobi_sviwaste_summary.csv`, `thesis_table/table_3_sviwaste.csv`

**Figure:** light blue = all SVI sampling points; red = waste-positive panoids. Subtitle shows total SVI count.

### 2d. `4roadwaste.py` — Road → waste-positive panoid (metre level)

**Unit:** Road metres; same split logic as `2roadsvi.py` (`lib.road_coverage`), but buffers only the **2,696 waste-positive** GSVI panoids (not all 76,605 sampling panoids).

```bash
python 2coverage_analysis/4roadwaste.py
python 2coverage_analysis/4roadwaste.py --buffer-m 50 --h3-res 8
# Sensitivity:
python 2coverage_analysis/4roadwaste.py --buffer-m 75
python 2coverage_analysis/4roadwaste.py --buffer-m 100
```

**Outputs** (`Data/.../2coverage_analysis/`):

- `Nairobi_roadwaste_coverage_buf50m.{gpkg,csv}` — covered/uncovered line parts
- `Nairobi_roadwaste_segments_buf50m.{gpkg,csv}` — per-segment length breakdown
- `Nairobi_roadwaste_grid_h3_res8_buf50m.{gpkg,csv}` — per-cell `waste_coverage_ratio`
- `Nairobi_roadwaste_summary_buf50m.csv` — citywide metres + optional all-GSVI reference %
- `thesis_table/table_4_roadwaste_buf50m.csv`

---

## Step 3 — 100 m grid coverage & validation

Analyses on the **100 m IDEAMaps grid** used by Step 3 scripts via `chapter_paths.active_grid_gpkg()` (`output_paths.GRID_GPKG`): Mollweide-extended constituency grid when `0_extend_grid/` outputs exist, otherwise the Angela-only Step 1 clip. Blocks: (3a) nested coverage, (3b) crowd validation vs the IDEAMaps submission model, (3c) mitigation validation (GSVI vs G+Self), (3d) indicator provenance, (3e) validation metrics by provenance.

### 3a. Grid coverage

Assigns Step 1 layers to the grid and summarises how many cells fall in each coverage context: city → road → SVI → waste. Uses the **GSVI arm** (Google SVI images + waste detections) as the baseline.

| Context | Rule (per grid cell) |
| --- | --- |
| City | All cells in the active Step 3 grid |
| Road | `road_length_m ≥ 25` (local noded roads from Step 1; `Nairobi_road_line_32737.gpkg`) |
| SVI | `svi_images ≥ 1` |
| Waste | `waste_images ≥ 1` |

### Run order

```bash
# Step 1 must be run first (grid + point layers + validation)
python 1prepare_chapter_data/1_prepare_chapter_data.py

# Optional but recommended: Mollweide fill so Step 3 uses the extended grid
python 0_extend_grid/1_extend_grid.py

python 3_100m/1_grid_coverage.py
Rscript 3_100m/1_plot_grid_coverage_matrix.R

python 3_100m/2_validation_analysis.py
Rscript 3_100m/2_plot_validation_confusion_matrix.R

python 3_100m/3_mitigation_validation.py
Rscript 3_100m/3_plot_mitigation_validation.R
Rscript 3_100m/3_plot_mitigation_validation_severity.R
Rscript 3_100m/3_plot_mitigation_validation_overlap.R

python 3_100m/4_indicator_provenance.py
Rscript 3_100m/4_plot_indicator_provenance_map.R
python 3_100m/5_validation_by_provenance.py
```

### Cell count table

**Script:** `3_100m/1_grid_coverage.py`

One row per context; single column `Grid cells` (comma-formatted integers).

**Output:** `3_100m/grid/Nairobi_grid_coverage_cell_counts.csv`

Example (current run on **Mollweide-extended** grid):

| Context | Grid cells |
| --- | --- |
| City | 69,943 |
| Road (≥25 m) | 43,863 |
| SVI (≥1 image) | 22,672 |
| Waste (≥1 detection) | 2,065 |

*(Angela-only clip was 57,013 city cells; re-run after deleting or renaming the extended gpkg to reproduce that baseline.)*

### Nested coverage matrix

Same script writes a **row / column percentage matrix** based on cell counts:

\[
\text{matrix}[\text{row}, \text{col}] = \frac{n(\text{row} \cap \text{col})}{n(\text{col})} \times 100
\]

Diagonal entries are 100%. Off-diagonal entries show how much of each column context is captured by the row context (e.g. road / city ≈ share of city cells with ≥25 m road).

**Outputs:**

- `3_100m/grid/Nairobi_grid_coverage_matrix_pct.csv` — wide matrix (thesis)
- `3_100m/grid/Nairobi_grid_coverage_matrix_long.csv` — long format (plotting / QA)
- `3_100m/grid/Nairobi_grid_coverage_32737.gpkg` — grid geometry + per-cell counts and flags

### Figure

**Script:** `3_100m/1_plot_grid_coverage_matrix.R`

Two-panel summary: **(A)** bar chart of grid cells by context, **(B)** nested coverage heatmap.

**Figure:** `Figure/3_100m/Grid_coverage_summary.png`

### 3b. Crowd validation — IDEAMaps model vs human labels

**Script:** `3_100m/2_validation_analysis.py`

Baseline check on validated grid cells: compares crowd `validation_result` against the IDEAMaps submission `model_result` from the validation CSV (not recomputed from Nairobi layers).

| Task | Truth | Prediction |
| --- | --- | --- |
| 3-class severity | `validation_result` (0/1/2) | `model_result` (0/1/2) |
| Binary waste | `is_waste` | `model_is_waste` |

**Outputs:**

- `3_100m/validation/Nairobi_validation_grid.csv` — validated cells (attributes only)
- `3_100m/validation/Nairobi_validation_confusion_severity.csv`
- `3_100m/validation/Nairobi_validation_confusion_binary.csv`
- `3_100m/validation/Nairobi_validation_metrics.csv`
- `3_100m/validation/Nairobi_validation_summary.csv`

**Figure (`2_plot_validation_confusion_matrix.R`):** three outputs — combined two-panel (`Validation_confusion_matrix.png`), plus separate 3-class and binary heatmaps.

| Figure | Content |
| --- | --- |
| `Validation_confusion_matrix.png` | Combined 3-class + binary panel |
| `Validation_confusion_matrix_severity.png` | 3-class only |
| `Validation_confusion_matrix_binary.png` | Binary only |

```bash
python 3_100m/2_validation_analysis.py
Rscript 3_100m/2_plot_validation_confusion_matrix.R
```

### 3c. Mitigation validation — GSVI vs G+Self on Nairobi grid

**Scripts:** `lib.ideamaps` (shared; shim `3_100m/ideamaps_grid_pipeline.py`), `3_100m/3_mitigation_validation.py`

Re-runs the IDEAMaps 100 m indicator pipeline on the **active Step 3 grid** (`chapter_paths.active_grid_gpkg()`: extended when available) for both arms, using **identical Jenks break points** from the GSVI submission (`GSVI_SUBMISSION_JENKS_BREAKS` in `lib.ideamaps`). Only the input SVI/waste GeoPackages differ:

| Arm | SVI input | Waste input |
| --- | --- | --- |
| GSVI | `Nairobi_SVI_image_gsvi_32737.gpkg` | `Nairobi_Waste_point_gsvi_32737.gpkg` |
| G+Self | `Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg` | `Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg` |

**Pipeline steps** (matches `SVI_IDEAMaps.ipynb` submission logic):

1. Count SVI images and waste detections per cell (spatial join, `within`)
2. Empirical Bayes smoothed waste/SVI ratio
3. Linear spatial interpolation on cell centroids
4. Classify with fixed Jenks upper bounds → `result` 0/1/2 (low / medium / high)

Crowd labels on validated cells are compared to both arms. Subsets reported in the comparison table:

| Subset | Definition |
| --- | --- |
| All validated cells | Every cell with crowd validation |
| Self-collected SVI overlap | Validated cells with ≥1 Faith or ZWL SVI image (n ≈ 133) |
| Prediction changed | Cells where G+Self `result` ≠ GSVI `result` |
| Self overlap AND prediction changed | Intersection of the above |

Metrics per subset × arm: binary and 3-class accuracy, precision, recall, F1. The IDEAMaps CSV `model_result` is retained for reference but is **not** used as the GSVI arm in this comparison.

**Outputs:**

- `3_100m/mitigation/Nairobi_validation_selfcollected_overlap.csv`
- `3_100m/mitigation/Nairobi_validation_mitigation_method.csv`
- `3_100m/mitigation/Nairobi_validation_mitigation_cells.csv`
- `3_100m/mitigation/Nairobi_validation_mitigation_comparison.csv`
- `3_100m/mitigation/Nairobi_validation_mitigation_summary.csv`
- `3_100m/thesis_table/table_waste_observation_mitigation.csv` — binary metrics thesis table (all cells + self-overlap n ≈ 133)

**Figures:**

| Script | Figure | Content |
| --- | --- | --- |
| `3_plot_mitigation_validation.R` | `Validation_mitigation_accuracy.png` | Binary metrics, all validated cells |
| `3_plot_mitigation_validation_severity.R` | `Validation_mitigation_severity.png` | 3-class metrics, all validated cells |
| `3_plot_mitigation_validation_overlap.R` | `Validation_mitigation_self_overlap.png` | **Primary figure** — self-overlap subset; binary + 3-class in one chart |
| `3_plot_mitigation_validation_overlap_pattern.R` | `Validation_mitigation_self_overlap_pattern.png` | Same as above; solid = binary, brown stripes = 3-class (optional variant) |

Shared chart code is `R/mitigation_validation_charts.R`; the four `3_plot_mitigation_validation*.R` scripts are thin wrappers (same CLI paths).

The overlap figure encodes **lightness = task** (light = binary, dark = 3-class) and **hue = arm** (brown = GSVI, green = G+Self). The pattern variant uses brown/white only (solid = binary, stripes = 3-class).

```bash
python 3_100m/3_mitigation_validation.py
Rscript 3_100m/3_plot_mitigation_validation.R
Rscript 3_100m/3_plot_mitigation_validation_severity.R
Rscript 3_100m/3_plot_mitigation_validation_overlap.R
Rscript 3_100m/3_plot_mitigation_validation_overlap_pattern.R   # optional
```

**Sensitivity (optional):** `3_mitigation_validation_sensitivity.py` repeats the comparison using raw cell waste/SVI ratios (no Empirical Bayes, no spatial fill) with the same fixed Jenks breaks. Writes `3_100m/mitigation/Nairobi_validation_mitigation_sensitivity_comparison.csv`.

### 3d. Indicator provenance

**Scripts:** `3_100m/4_indicator_provenance.py`, `3_100m/4_plot_indicator_provenance_map.R`

Classifies every city-grid cell (GSVI arm, same IDEAMaps pipeline as mitigation: EB + spatial fill + fixed Jenks) into one of three provenance classes:

| Provenance | Definition |
| --- | --- |
| Direct observation | ≥1 GSVI image in the cell |
| Interpolated support | No local imagery; value from spatial fill |
| Unsupported, platform-coded low | Still missing after interpolation; encoded as zero because IDEAMaps required a complete categorical map |

Example shares on the extended grid (current run): Direct ~32.4% | Interpolated ~65.3% | Unsupported ~2.3% (n = 69,943).

**Outputs:**

- `3_100m/grid/Nairobi_indicator_provenance_cells.csv` — per-cell ratios + `indicator_provenance`
- `3_100m/grid/Nairobi_indicator_provenance_summary.csv`
- `3_100m/thesis_table/table_indicator_provenance.csv`

**Figure:** `Figure/3_100m/Indicator_provenance_100m.png` (choropleth; prefers extended-grid geometry when present)

```bash
python 3_100m/4_indicator_provenance.py
Rscript 3_100m/4_plot_indicator_provenance_map.R
```

### 3e. Crowd validation by provenance

**Script:** `3_100m/5_validation_by_provenance.py`

Joins crowd-validated cells to provenance labels and reports binary waste metrics (`is_waste` vs IDEAMaps `model_is_waste`) for:

- All crowd-validation cells
- Cells with direct GSVI observations (main contrast)

An intermediate “evidence-supported (direct + interpolated)” row is kept in the numeric summary CSV for archive/appendix. Metrics apply only to the validation sample (not all Nairobi cells).

**Outputs:**

- `3_100m/validation/Nairobi_validation_by_provenance.csv`
- `3_100m/thesis_table/table_validation_by_provenance.csv`

```bash
python 3_100m/5_validation_by_provenance.py
```

---

## Step 4 — Compare GSVI vs GSVI + self-collected

Visual comparison of the two **arms** from Step 1 — no clustering required. Uses harmonised Step 1 GeoPackages only.

| Arm slug | Definition |
| --- | --- |
| `gsvi` | Google Street View only |
| `gsvi_selfcollected` | Google + Faith/ + ZWL/ self-collected |

### Run order

```bash
# Step 1 must be run first (creates gsvi / gsvi_selfcollected gpkgs)
python 1prepare_chapter_data/1_prepare_chapter_data.py

python 4_compare/1_compare_sources_table.py
Rscript 4_compare/1_plot_svi_sources_map.R
Rscript 4_compare/2_plot_waste_sources_map.R
Rscript 4_compare/3_plot_sources_comparison_panel.R
```

### 4a. Source summary table

**Script:** `4_compare/1_compare_sources_table.py`

Image-level counts from Step 1 `Nairobi_SVI_image_*` and `Nairobi_Waste_point_*` GeoPackages (dedupe key: `lat`, `lon`, `img_name`).

| Column | Meaning |
| --- | --- |
| `Data source` | GSVI, Self-collected, or GSVI + Self-collected |
| `SVI images` | Street-view image files sampled |
| `Waste-positive images` | Image files with a waste detection |

**Output:** `4_compare/thesis_table/Nairobi_compare_sources_table.csv`

### 4b. SVI source map

**Script:** `4_compare/1_plot_svi_sources_map.R`

All SVI panoids from `Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg`. Light brown = GSVI; darker brown highlights self-collected panoids.

**Figure:** `Figure/4_compare/SVI_sources_gsvi_selfcollected.png`

### 4c. Waste source map

**Script:** `4_compare/2_plot_waste_sources_map.R`

Waste detections from Step 1 gpkgs, layered over all SVI panoids. Layer order: all SVI → GSVI waste → self-collected waste → urban-poor fill → city boundary.

**Figure:** `Figure/4_compare/Waste_sources_gsvi_selfcollected.png`

### 4d. Combined comparison panel

**Script:** `4_compare/3_plot_sources_comparison_panel.R`

Side-by-side panel: (A) SVI imagery by source, (B) waste detections by source.

**Figure:** `Figure/4_compare/Sources_gsvi_selfcollected_comparison.png`

---

## Step 5 — Spatial pattern analysis

Panorama-level pattern tests and hotspot detection. The **primary spatial unit** is the GSVI **panorama (panoid)** from Step 2c (`Nairobi_sviwaste_points.gpkg`: 2,696 waste-positive of 76,605), not the 3,236 directional waste images. A panorama is waste-positive if **at least one** directional view is positive (`n_positive_views` is retained for sensitivity only). Shared loaders live in `lib.panoids` (shim: `5_spatial_pattern/panoid_locations.py`); period labels, HDBSCAN params, and GAM year FE are in `lib.periods`, `lib.hdbscan_fit`, and `lib.gam`.

| Experiment | Content | Primary? |
| --- | --- | --- |
| 1. Observation-conditioned clustering | NNR: 2,696 positives vs draws from 76,605 panoids | Yes |
| 2. Settlement association | P(waste\|inside) vs P(waste\|outside); χ² / PCR | Yes |
| 3. Signed-distance relationship | Logistic GAM: `logit(p)=α+s(signed_distance)+γ_year` | Yes |
| 3b. Population-adjusted distance | Nested GAMs with `s(log1p(pop_density))` (MP vs MDP) | Supplementary (R3) |
| 4. Local hotspot identification | HDBSCAN on positive panoids (+ 100 m-cell sensitivity) | Yes (HDBSCAN) |
| 5. Temporal robustness | Settlement rates / NNR by capture year | Yes |
| Supplement | Distance-decay NegExp/ECDF; KDE hotspots | No |

### Run order

```bash
# Requires Step 1 + Step 2c (sviwaste panoid labels)
python 2coverage_analysis/3sviwaste.py

# Exp 1–2: NNR + urban-poor boundary association
python 5_spatial_pattern/settlement/1_nnr_observation_frame.py
python 5_spatial_pattern/settlement/2_settlement_association.py
Rscript 5_spatial_pattern/settlement/3_plot_settlement_association.R

# Distance-decay / NegExp (supplement)
python 5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py
Rscript 5_spatial_pattern/Distance_decay/2_plot_distance_decay.R
Rscript 5_spatial_pattern/Distance_decay/3_plot_negexp_notebook_style.R

# Exp 3: signed-distance GAM (+ year FE) and period-stratified robustness
python 5_spatial_pattern/Signed_distance/1_signed_distance_gam.py
Rscript 5_spatial_pattern/Signed_distance/2_plot_signed_distance_gam.R
python 5_spatial_pattern/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py
Rscript 5_spatial_pattern/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R
python 5_spatial_pattern/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py
Rscript 5_spatial_pattern/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R

# Exp 3b: population-adjusted signed-distance GAMs (Reviewer 3)
python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py
Rscript 5_spatial_pattern/pop_adjusted/2_plot_pop_adjusted_gam.R
Rscript 5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R
# Sensitivity: unconstrained WorldPop 2020
python 5_spatial_pattern/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py
Rscript 5_spatial_pattern/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R
Rscript 5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R --data-subdir=worldpop_2020 --fig-subdir=worldpop_2020

# Exp 5: temporal robustness
python 5_spatial_pattern/settlement/5_temporal_robustness.py
Rscript 5_spatial_pattern/settlement/6_plot_temporal_robustness.R

# Exp 4: HDBSCAN + mitigation + sensitivities
python 5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py
python 5_spatial_pattern/HDBSCAN/4_mitigation_comparison.py
python 5_spatial_pattern/HDBSCAN/5_hdbscan_cluster_views.py
python 5_spatial_pattern/HDBSCAN/6_hdbscan_100m_sensitivity.py
Rscript 5_spatial_pattern/HDBSCAN/3_plot_hdbscan_map.R
Rscript 5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R
Rscript 5_spatial_pattern/HDBSCAN/4_plot_new_obs_stacked_bar.R
Rscript 5_spatial_pattern/HDBSCAN/6_plot_hdbscan_100m_sensitivity.R
python 5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py
Rscript 5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R
Rscript 5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R
python 5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py
Rscript 5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R

# Supplementary: KDE
python 5_spatial_pattern/KDE/1_kde_hotspots.py
Rscript 5_spatial_pattern/KDE/2_plot_kde_comparison.R
```

### 5a. Observation-frame NNR

**Script:** `5_spatial_pattern/settlement/1_nnr_observation_frame.py`

Primary null preserves the GSVI road/platform frame: compare mean 1-NN distance among the 2,696 waste-positive panoids with 999 random draws of 2,696 locations from the 76,605 available GSVI panoids.

- Observation-frame NNR = `d_obs / mean(d_null)`
- One-sided p-value = `P(d_null ≤ d_obs)`
- Clark–Evans CSR over the city polygon is reported only as an appendix row

**Outputs:** `Data/.../settlement/Nairobi_nnr_observation_frame_summary.csv`, null distances CSV, `thesis_table/nnr_observation_frame.csv`  
**Figure:** `Figure/5_spatial_pattern/settlement/NNR_observation_frame_null.png`

### 5b. Settlement association (χ², density) — urban-poor boundary stats

**Script:** `5_spatial_pattern/settlement/2_settlement_association.py`

Labels each of 76,605 GSVI panoids as inside/outside urban-poor settlements (`Nairobi_slum_polygon_32737.gpkg`).

- **Chi-square:** 2×2 among panoids (waste-positive × inside settlement); Pearson χ², Cramér’s V, odds ratio
- **Area-normalised density:** waste-positive panoids per km² inside vs outside; PCR = (waste share inside) / (settlement area share)
- **Zone table:** urban poor / non-urban poor / ratio / total

**Outputs:** contingency, χ², density under `Data/.../settlement/`; `thesis_table/{settlement_association,settlement_zone_summary}.csv`  
**Figures:** `Figure/5_spatial_pattern/settlement/Settlement_*.png`

### 5b1. Distance-decay / NegExp (supplement)

**Scripts:** `5_spatial_pattern/Distance_decay/`

- ECDF of unsigned distance to settlement (waste+ vs non+)
- NegExp \(P(x)=a(1-e^{-bx})\) for waste-positive vs all GSVI (half-distance \(\ln 2/b\))
- Distance threshold table; panoid distance export (unsigned + signed)

```bash
python 5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py
Rscript 5_spatial_pattern/Distance_decay/2_plot_distance_decay.R
Rscript 5_spatial_pattern/Distance_decay/3_plot_negexp_notebook_style.R
```

**Outputs:** `Data/.../Distance_decay/` + `thesis_table/{distance_thresholds,distance_decay_negexp}.csv`  
**Figures:**  
- `Figure/5_spatial_pattern/Distance_decay/Distance_ecdf.png`  
- `Distance_decay_negexp.png`  
- `NegExp_Panoids_vs_WastePositive.png`  
- `NegExp_derivative.png`

### 5b2. Signed-distance logistic GAM (Exp 3) — primary year-adjusted model

**Scripts:**  
- `5_spatial_pattern/Signed_distance/1_signed_distance_gam.py`  
- `5_spatial_pattern/Signed_distance/2_plot_signed_distance_gam.R`

**Primary temporal-robustness model** at panorama unit (full GSVI sample):

\[
\operatorname{logit}(p_i)=\alpha+s(\text{signed distance}_i)+\gamma_{\text{year}}
\]

This is the explicit “control for image year” specification: the settlement–distance gradient is estimated conditional on capture year.

- Sparse years (`n < 200` panoids; 2015, 2019) are pooled then reassigned to the nearest year FE with ≥1 waste-positive so that **all panoramas with valid year are retained** (no complete-separation drops).
- Nested comparison: year-only `logit(p)=α+γ_year` vs year + `s(signed_distance)` (LRT + ΔAIC).
- Figure: **year-standardised (marginal)** predicted probabilities at each signed distance, averaging over the observed capture-year FE distribution, with bootstrap 95% CI.
- Claim supported when distance remains after year adjustment: *“The signed-distance relationship remained after adjustment for panorama capture year.”*

Period-stratified curves and HDBSCAN maps are **supporting** robustness only (see below).

**Outputs:** GAM frame/curve/year-effects/LRT/summary CSVs under  
`Data/Chapter_waste/5_spatial_pattern/Signed_distance/`; thesis table  
`…/Signed_distance/thesis_table/signed_distance_gam.csv`  
**Figures:**  
- `Figure/5_spatial_pattern/Signed_distance/Signed_distance_gam_curve.png`  
- `Figure/5_spatial_pattern/Signed_distance/Signed_distance_gam_curve_inset.png` (near-edge zoom ≤ 1 km)

### 5b2c. Population-adjusted signed-distance GAMs (Reviewer 3)

**Scripts:**  
- `5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py`  
- `5_spatial_pattern/pop_adjusted/2_plot_pop_adjusted_gam.R`  
- `5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R`

Uses the same panorama unit and year FE treatment as the primary S4 model, with **static** WorldPop Constrained Kenya 2024 (`ken_pop_2024_CN_100m_R2025A_v1.tif` under `Data/.../pop_adjusted/`) as `s(log1p(pop_density))` (not temporally matched to capture year).

Nested models:

| Model | Specification |
| --- | --- |
| M0 | `logit(p)=α+year` |
| MP | `logit(p)=α+s(log1p(pop_density))+year` |
| MD | `logit(p)=α+s(signed_distance)+year` (same as S4) |
| MDP | `logit(p)=α+s(signed_distance)+s(log1p(pop_density))+year` |
| MDPS | MDP + thin-plate spatial field on `(x,y)` if residual Moran’s I is significant |

**Central test:** MP vs MDP (does signed distance still matter after population + year?). Also report MD vs MDP (how much population adds). Outputs include ΔAIC, LRT, pseudo-R², concurvity, residual Moran’s I, 5-fold spatial-block CV (Brier / log-loss), and waste+ deduplication at 50 m / 100 m.

**Residual / excess-occurrence map:** panorama-level MDP residuals (`y − μ` and Pearson) aggregated to hex cells. Complements the two-panel adjusted-effects figure: effects ask *what the adjusted smooths look like*; the residual map asks *where the model still under- or over-predicts* after population, settlement proximity, and year (landmarks for orientation only).

```bash
python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py
Rscript 5_spatial_pattern/pop_adjusted/2_plot_pop_adjusted_gam.R
# Residual map only (reuses saved frame; skips bootstrap / CV):
python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py --residuals-only
Rscript 5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R
```

**Outputs:** `Data/Chapter_waste/5_spatial_pattern/pop_adjusted/` (+ `thesis_table/pop_adjusted_gam.csv`; residual CSV `Nairobi_pop_adjusted_mdp_residuals.csv`)  
**Figures:**  
- `Figure/5_spatial_pattern/pop_adjusted/Pop_adjusted_gam_effects.png` (two-panel adjusted effects)  
- `Figure/5_spatial_pattern/pop_adjusted/Pop_adjusted_mdp_residual_map.png` (hex mean Pearson residual)  
- `Figure/5_spatial_pattern/pop_adjusted/Pop_adjusted_mdp_excess_prob_map.png` (hex mean response residual)

**Sensitivity — WorldPop unconstrained 2020** (`ken_ppp_2020.tif`): same nested models / year FE / robustness suite, written under `…/pop_adjusted/worldpop_2020/` (scripts in `5_spatial_pattern/pop_adjusted/worldpop_2020/`).

```bash
python 5_spatial_pattern/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py
Rscript 5_spatial_pattern/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R
```

**Outputs:** `Data/.../pop_adjusted/worldpop_2020/` (+ `thesis_table/pop_adjusted_gam_worldpop_2020.csv`)  
**Figures:**  
- `Figure/5_spatial_pattern/pop_adjusted/worldpop_2020/Pop_adjusted_gam_effects.png`  
- `Figure/5_spatial_pattern/pop_adjusted/worldpop_2020/Pop_adjusted_mdp_residual_map.png`  
- `Figure/5_spatial_pattern/pop_adjusted/worldpop_2020/Pop_adjusted_mdp_excess_prob_map.png`

### 5b2b. Period-stratified robustness (signed distance + HDBSCAN)

Because individual years are extremely uneven (e.g. 2015 = 5; 2019 = 73), capture years are grouped into two nearly balanced periods for stratified spatial analysis. The GSVI observation frame is **2015–2022 excluding 2020** (n = 76,605). There are **no 2023 panoramas**.

| Period | Years | GSVI panoramas |
| --- | --- | ---: |
| Early | 2015–2019 | 36,446 |
| Later | 2021–2022 | 40,159 |

**A. Period signed-distance GAM** — scripts: `5_spatial_pattern/Signed_distance/period_stratified_robustness/`

Within each period (no year FE; stratification is the temporal control):

\[
\operatorname{logit}\{P(\text{Waste}=1)\}=\alpha+s(\text{signed distance})
\]

Bootstrap 95% CIs on a shared distance grid. Addresses whether the settlement-distance gradient appears in both capture eras.

**B. Period HDBSCAN** — scripts: `5_spatial_pattern/HDBSCAN/period_stratified_robustness/`

Waste-positive panoramas only, same parameters as the main analysis (`min_cluster_size=25`, `min_samples=6`). Two-panel map; report clusters and `% waste points clustered`. Caption (not on-figure): period-specific concentrations, **not** temporal persistence.

```bash
python 5_spatial_pattern/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py
Rscript 5_spatial_pattern/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R
python 5_spatial_pattern/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py
Rscript 5_spatial_pattern/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R
```

**Outputs — signed distance:** `…/Signed_distance/period_stratified_robustness/` (frame/curves/summaries, thesis table)  
**Outputs — HDBSCAN:** `…/HDBSCAN/period_stratified_robustness/` (gpkgs, summaries, thesis table)  

**Figures:**  
- `Figure/5_spatial_pattern/Signed_distance/period_stratified_robustness/Period_signed_distance_gam_curve.png`  
- `…/Period_signed_distance_gam_curve_near_edge.png`  
- `Figure/5_spatial_pattern/HDBSCAN/period_stratified_robustness/Period_HDBSCAN_comparison.png`

### 5b3. Temporal robustness (Exp 5)

**Script:** `5_spatial_pattern/settlement/5_temporal_robustness.py`

Within each capture year (rare years pooled): settlement positive rates, prevalence/odds ratios, and observation-frame NNR when ≥50 waste-positive panoramas.

**Outputs:** `Nairobi_temporal_robustness_by_year.csv`, `thesis_table/temporal_robustness.csv`  
**Figures:** `Temporal_waste_positive_rate_by_year.png`, `Temporal_prevalence_ratio_by_year.png`

### 5c. HDBSCAN clustering (panoid locations)

**Script:** `5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py`

| Parameter | Value |
| --- | --- |
| `min_cluster_size` | 25 |
| `min_samples` | 6 |
| Unit | GSVI waste-positive panoids (~2,696); + Faith/ZWL locations for self-collected arm (~2,845) |
| Coordinate space | EPSG:32737 |

**Outputs (processed data):**

- `Nairobi_waste_hdbscan_gsvi_32737.gpkg`, `Nairobi_waste_hdbscan_summary_gsvi.csv`
- `Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg`, `Nairobi_waste_hdbscan_summary_gsvi_selfcollected.csv`
- `Nairobi_waste_hdbscan_summary_comparison.csv`

**Script:** `5_spatial_pattern/HDBSCAN/3_plot_hdbscan_map.R`

**Figures:**

- `Waste_HDBSCAN_gsvi.png` — gsvi arm clusters
- `Waste_HDBSCAN_gsvi_selfcollected.png` — gsvi_selfcollected arm clusters
- `Waste_HDBSCAN_comparison.png` — side-by-side (A/B) comparison

Map styling: chocolate-brown HDBSCAN clusters, grey noise points, black city boundary, repelled cluster ID labels, north arrow, scale bar, inside bottom-right legend.

**Context map + cluster–settlement composition** (from notebook logic in `del/SVI_distance_use.ipynb`):

```bash
python 5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py
Rscript 5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R
Rscript 5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R
python 5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py
Rscript 5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R
```

- Distance bins (panoid/location unit): Within Urban Poor | 0–250 m | 250–500 m | >500 m
- Figures:
  - `Waste_HDBSCAN_context_gsvi.png` / `Waste_HDBSCAN_context_gsvi_selfcollected.png` — clusters + urban-poor polygons + major areas (Kibera, Mukuru, Mathare, Kawangware) + Dandora
  - `Cluster_Composition_By_Distance_gsvi.png` / `…_gsvi_selfcollected.png` — 100% stacked bars per cluster
  - `Cluster_Size_Distribution_gsvi.png` / `…_gsvi_selfcollected.png` — violin (associated with urban-poor settlements vs other clusters; any-overlap rule) + cluster-size histogram

### 5c2. HDBSCAN sensitivities (`n_positive_views`, 100 m cells)

**Scripts:**

- `5_hdbscan_cluster_views.py` — join `n_positive_views` after clustering; per-cluster descriptives only (does **not** re-weight HDBSCAN)
- `6_hdbscan_100m_sensitivity.py` — cell positive if ≥1 positive panorama; HDBSCAN on cell centroids; Jaccard vs panoid hotspots

**Figures:** `Figure/5_spatial_pattern/HDBSCAN/HDBSCAN_100m_cell_sensitivity.png`

### 5d. Mitigation comparison

**Script:** `5_spatial_pattern/HDBSCAN/4_mitigation_comparison.py`

Compares **gsvi** vs **gsvi_selfcollected** at panoid/location level. Hotspot area = sum of per-cluster convex-hull polygon areas (km², EPSG:32737). New locations keyed by `panoid` (Google) or `img_name`/coords (self-collected).

**Outputs:**

- `thesis_table/Nairobi_mitigation_comparison_table.csv`
- `thesis_table/Nairobi_mitigation_new_observations_table.csv`
- `Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg`
- `Nairobi_waste_hotspot_polygons_gsvi_selfcollected_32737.gpkg`

### 5e. Hotspot area difference map

**Script:** `5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R`

Requires hotspot polygon GeoPackages from `4_mitigation_comparison.py`. Unions all cluster convex hulls per arm, then maps:

- **Light grey-brown points** — all SVI panoids (`#D4CCC2`, bottom layer)
- **Light fill** — overlapping hotspot footprint (shared between gsvi and gsvi_selfcollected)
- **Dark fill** — additional footprint from adding self-collected imagery
- **Medium fill** (if present) — GSVI-only footprint lost when clusters are re-fit
- **Light brown points** — GSVI waste-positive panoids (`#C9A27F`)
- **Dark brown points** — self-collected waste locations (`#6B4226`)

```bash
Rscript 5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R
```

**Figure:** `Figure/5_spatial_pattern/HDBSCAN/Hotspot_area_difference_gsvi_selfcollected.png`

### 5f. Stacked bar

**Script:** `5_spatial_pattern/HDBSCAN/4_plot_new_obs_stacked_bar.R`

Reads `thesis_table/Nairobi_mitigation_new_observations_table.csv` — one horizontal stacked bar: inside existing hotspots vs forming new hotspots.

**Figure:** `Figure/5_spatial_pattern/HDBSCAN/Mitigation_new_obs_stacked_bar.png`

### 5g. KDE robustness (supplementary)

**Purpose:** Robustness check only — does the neighbourhood-scale hotspot pattern stay broadly similar when switching from discrete HDBSCAN clusters to a smooth KDE surface and adding supplementary self-collected observations? HDBSCAN remains the primary hotspot method; KDE does not replace it.

**Scripts:**

- `5_spatial_pattern/KDE/1_kde_hotspots.py` — KDE on panoid locations, shared threshold, union polygons, overlap metrics
- `5_spatial_pattern/KDE/2_plot_kde_comparison.R` — two-panel comparison + difference map

**Config constants** (top of `1_kde_hotspots.py`):

| Constant | Default | Meaning |
| --- | --- | --- |
| Bandwidth | `KDE_BANDWIDTH_M = 400` | Fixed isotropic Gaussian sd (m); same bandwidth for both arms |
| `GRID_CELL_M` | 150 | Regular grid cell size (m, EPSG:32737) |
| `KDE_HOTSPOT_PERCENTILE` | 2 | Top N% of gsvi density values → shared absolute threshold |

```bash
python 5_spatial_pattern/KDE/1_kde_hotspots.py
Rscript 5_spatial_pattern/KDE/2_plot_kde_comparison.R
```

**Outputs (processed data):**

```
5_spatial_pattern/KDE/
├── thesis_table/Nairobi_kde_robustness_comparison.csv
├── Nairobi_kde_hotspot_polygons_gsvi_32737.gpkg
├── Nairobi_kde_hotspot_polygons_gsvi_selfcollected_32737.gpkg
└── Nairobi_kde_params.csv
```

**Figures:**

- `Figure/5_spatial_pattern/KDE/KDE_hotspot_gsvi.png`
- `Figure/5_spatial_pattern/KDE/KDE_hotspot_gsvi_selfcollected.png`
- `Figure/5_spatial_pattern/KDE/KDE_hotspot_comparison.png` — side-by-side (A/B)
- `Figure/5_spatial_pattern/KDE/KDE_hotspot_difference.png` — overlap vs additional area

**What not to do:** no parameter-sweep narrative, no algorithm horse-race; KDE is supplementary to HDBSCAN.

---

## Step 6 — YOLO training-mix sensitivity (`6_sensitivity_training/`)

Changes **training data** only (not the spatial pipeline).

Varies **SC-slot retention** in the 695-image YOLO set (original 85 SC slots):

| Scenario | Meaning |
| --- | --- |
| `sc_100pct` | **Baseline — model used in the main chapter** (610 GSVI + 85 SC) |
| `sc_75/50/25pct` | Fewer SC slots, replaced by GSVI |
| `sc_0pct` | **No SC** in training |

See `6_sensitivity_training/README.md`. Pipeline notebook: `1_training_dataset_pipeline.ipynb`.  
Scenario image folders: `Waste/img/6_sensitivity_training/sc_*pct/` (symlinks into the archive).

Frozen messy dump of the old combined Step 6: `6_sensitivity_archive/`.

---

## Step 7 — Held-out GSVI validation (`7_heldout_validation/`)

**Evaluation only** — does not change training.

Independent GSVI test: ~100 panoids → **180 images** (90 waste + 90 background), panoid-safe vs `Train0315_695`.

Canonical labeled set (180 images):

`Waste/img/7_heldout_validation/20260807_heldout_GSVI_p100_label/`

**Thesis tables:** `Data/Chapter_waste/7_heldout_validation/thesis_table/`  
(display + Wilson CI + detail + citywide funnel). Regenerate with `python 7_heldout_validation/0_run_all.py`. See `7_heldout_validation/README.md`.

Steps 6–7 are independent of Steps 1–5. Re-run spatial analysis only if you retrain YOLO and regenerate citywide waste detections.

---

## Archived — previous 100 m waste-ratio workflow

The earlier waste/SVI ratio pipeline (Empirical Bayes smoothing, IDEAMaps fixed bands, gsvi vs g+self context maps) is preserved locally in `del/3_100m_backup/` and `Figure/3_100m_backup/` (both gitignored). See `del/SVI_IDEAMaps.ipynb` for the original notebook logic.

---

## Thesis summary tables

Each coverage Python script writes a publication-style table (Variable / Value / Unit) to:

```
Chapter_waste/2coverage_analysis/thesis_table/
├── table_1_cityroad_h3_res8_buf50m.csv
├── table_2_roadsvi_buf50m.csv
└── table_3_sviwaste.csv

Chapter_waste/3_100m/
├── grid/
│   ├── Nairobi_grid_coverage_cell_counts.csv
│   ├── Nairobi_grid_coverage_matrix_pct.csv
│   ├── Nairobi_grid_coverage_matrix_long.csv
│   ├── Nairobi_grid_coverage_32737.gpkg
│   ├── Nairobi_indicator_provenance_cells.csv
│   └── Nairobi_indicator_provenance_summary.csv
├── validation/
│   ├── Nairobi_validation_grid.csv
│   ├── Nairobi_validation_confusion_severity.csv
│   ├── Nairobi_validation_confusion_binary.csv
│   ├── Nairobi_validation_metrics.csv
│   ├── Nairobi_validation_summary.csv
│   └── Nairobi_validation_by_provenance.csv
├── mitigation/
│   ├── Nairobi_validation_selfcollected_overlap.csv
│   ├── Nairobi_validation_mitigation_method.csv
│   ├── Nairobi_validation_mitigation_cells.csv
│   ├── Nairobi_validation_mitigation_comparison.csv
│   ├── Nairobi_validation_mitigation_summary.csv
│   └── Nairobi_validation_mitigation_sensitivity_*.csv
└── thesis_table/
    ├── table_waste_observation_mitigation.csv
    ├── table_indicator_provenance.csv
    └── table_validation_by_provenance.csv

Chapter_waste/0_extend_grid/
├── Nairobi_grid_100m_extended_32737.gpkg
├── Nairobi_grid_100m_extension_cells_32737.gpkg
├── Nairobi_grid_extension_summary.csv
├── Nairobi_indicator_provenance_cells_extended.csv
└── Nairobi_indicator_provenance_summary_extended.csv

Chapter_waste/4_compare/thesis_table/
└── Nairobi_compare_sources_table.csv

Chapter_waste/5_spatial_pattern/settlement/thesis_table/
├── nnr_observation_frame.csv
├── settlement_association.csv
├── settlement_zone_summary.csv
└── temporal_robustness.csv

Chapter_waste/5_spatial_pattern/Distance_decay/thesis_table/
├── distance_thresholds.csv
└── distance_decay_negexp.csv

Chapter_waste/5_spatial_pattern/Signed_distance/thesis_table/
└── signed_distance_gam.csv

Chapter_waste/5_spatial_pattern/pop_adjusted/thesis_table/
└── pop_adjusted_gam.csv

Chapter_waste/5_spatial_pattern/pop_adjusted/worldpop_2020/thesis_table/
└── pop_adjusted_gam_worldpop_2020.csv

Chapter_waste/5_spatial_pattern/Signed_distance/period_stratified_robustness/thesis_table/
└── period_signed_distance_gam.csv

Chapter_waste/5_spatial_pattern/HDBSCAN/thesis_table/
├── Nairobi_mitigation_comparison_table.csv
└── Nairobi_mitigation_new_observations_table.csv

Chapter_waste/5_spatial_pattern/KDE/thesis_table/
└── Nairobi_kde_robustness_comparison.csv
```

Tables are generated alongside the analysis outputs (not a separate script), so re-running a step refreshes its table automatically. Formatting uses rounded values and comma-separated integers.

---

## Figures (R)

All maps use `R/chapter_paths.R` for data roots, plus `R/map_theme.R` and `R/chapter_colours.R` (coverage and validation charts) or `R/mitigation_map_theme.R` (source and cluster maps in `4_compare/` and `5_spatial_pattern/`). Step 3c mitigation charts share `R/mitigation_validation_charts.R`.

- North arrow (top-right)
- Scale bar (bottom-left)
- Legend (bottom-right, inside panel)
- EPSG:32737 axis labels


| Script                                                     | Figures                                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| `0_extend_grid/3_plot_extended_grid.R`                     | Angela vs Mollweide fill + extended-grid provenance map                 |
| `1prepare_chapter_data/plot_maps.R`                        | Waste, SVI, boundary, slum preview maps                                 |
| `1prepare_chapter_data/plot_road_figures.R`                | Five numbered road maps (01–05) + hi-res comparison                     |
| `1prepare_chapter_data/plot_road_type_composition.R`       | Local road type pie chart                                               |
| `1prepare_chapter_data/plot_road_type_composition_osmnx.R` | OSMnx road type pie chart + map                                         |
| `1prepare_chapter_data/plot_road_network_comparison.R`     | Local vs OSMnx summary bar charts                                       |
| `2coverage_analysis/1plot_cityroad_maps.R`                 | 4 H3 choropleths + Spearman heatmap + scatter matrix                    |
| `2coverage_analysis/1plot_cityroad_analysis.R`             | H3 metric distribution panels (violin + histogram)                        |
| `2coverage_analysis/plot_process_zoom_map.R`               | Zoomed pipeline schematic: 4-panel + single-hex layers map              |
| `2coverage_analysis/2plot_roadsvi_maps.R`                  | Road SVI gap map + H3 choropleth + hist/scatter (75/100 → `buffer/`)      |
| `2coverage_analysis/3plot_sviwaste_maps.R`                 | SVI waste-positive map (+ `_hires` version)                             |
| `3_100m/1_plot_grid_coverage_matrix.R`                       | 100 m grid cell counts + nested coverage heatmap                        |
| `3_100m/2_plot_validation_confusion_matrix.R`              | Crowd validation confusion matrices (combined + 3-class + binary)         |
| `3_100m/3_plot_mitigation_validation.R`                      | Mitigation validation — binary metrics (all cells)                      |
| `3_100m/3_plot_mitigation_validation_severity.R`             | Mitigation validation — 3-class metrics (all cells)                       |
| `3_100m/3_plot_mitigation_validation_overlap.R`              | Mitigation validation — self-overlap subset (primary combined figure)   |
| `3_100m/3_plot_mitigation_validation_overlap_pattern.R`      | Pattern variant of self-overlap figure (optional)                         |
| `3_100m/4_plot_indicator_provenance_map.R`                   | Indicator provenance choropleth (direct / interpolated / unsupported)   |
| `4_compare/1_plot_svi_sources_map.R`                         | SVI panoids by source (GSVI vs self-collected)                          |
| `4_compare/2_plot_waste_sources_map.R`                       | Waste detections by source (GSVI vs self-collected)                     |
| `4_compare/3_plot_sources_comparison_panel.R`                | Two-panel source comparison (SVI + waste)                               |
| `5_spatial_pattern/settlement/3_plot_settlement_association.R` | NNR null, density, rates, composition |
| `5_spatial_pattern/Distance_decay/2_plot_distance_decay.R` | ECDF + NegExp distance-decay |
| `5_spatial_pattern/Distance_decay/3_plot_negexp_notebook_style.R` | NegExp cumulative + derivative pair |
| `5_spatial_pattern/HDBSCAN/3_plot_hdbscan_map.R`                     | HDBSCAN cluster maps + side-by-side comparison                          |
| `5_spatial_pattern/HDBSCAN/4_plot_new_obs_stacked_bar.R`             | New locations inside vs new hotspot bar                              |
| `5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R`          | Hotspot overlap vs additional area map                                  |
| `5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R`             | Context map (urban poor, majors, Dandora)                               |
| `5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R`    | Cluster composition by distance to urban-poor boundary                |
| `5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py`           | Cluster sizes × inside/outside + silhouette                           |
| `5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R`       | Violin + histogram of cluster sizes                                   |
| `5_spatial_pattern/KDE/2_plot_kde_comparison.R`                      | KDE hotspot comparison + difference map                                 |
| `6_sensitivity_training/7_plot_baseline_training_curves.R`           | Baseline YOLO training loss/mAP curves (sc_100pct)                      |
| `7_heldout_validation/0_run_all.py`                                  | One-shot Step 7 tables + figures                                        |
| `7_heldout_validation/2_prepare_heldout_gsvi.py`                     | 180-image GSVI held-out export (panoid-first; optional)                 |
| `7_heldout_validation/4_Qwen_yolo_positives_replicates.ipynb`        | Qwen ×3 on all YOLO held-out positives → with_qwen CSV                  |
| `7_heldout_validation/5_build_outputs.py`                            | Thesis tables (display + Wilson CIs + funnel; best Qwen2_* by F1)       |
| `7_heldout_validation/6_plot_outputs.R`                              | Held-out sensitivity charts + YOLO vs YOLO→Qwen confusion               |


Hi-res exports (`*_hires.png`) are 12,000 × 12,000 px for zooming; standard PNGs (~3,000 px) are for reports.

---

## Environment


| Tool                                             | Environment                  |
| ------------------------------------------------ | ---------------------------- |
| Python (geopandas, h3, osmnx, networkx, shapely, hdbscan) | `conda activate geo_env_LLM` |
| Python (pandas, Pillow) — Step 6 notebook only   | `conda activate geo_env_LLM` |
| Snakemake 7 + Graphviz (`dot`) — Steps 0–5 wrap  | `conda activate geo_env_LLM` (`pip install 'snakemake==7.32.4'`) |
| R (sf, ggplot2, ggspatial, ggpattern, dplyr, scales, patchwork, cowplot) | system R (`Rscript`)         |
| Data roots                                       | `PHD_DATA_ROOT` via `chapter_paths.py` / `R/chapter_paths.R` |


---

## Legacy files

Local archive under `del/` (gitignored — not synced to remote):

| File | Purpose |
| --- | --- |
| `del/SVI_IDEAMaps.ipynb` | Original 100 m grid submission workflow |
| `del/SVI_Val.ipynb` | YOLO validation split evaluation (companion to Step 6) |
| `del/1_training_dataset_csv.ipynb` | Earlier draft of the Step 6 training inventory notebook |
| `del/SVI_PPP_Stats_USE.ipynb` | Earlier PPP / stats analysis |
| `del/SVI_distance_use.ipynb` | Earlier distance analysis |
| `del/3_100m_backup/` | Previous grid waste-ratio scripts (`1_grid_waste_ratio.py`, context maps, etc.) |

The original root-level `data.py` exploratory script was superseded by `1_prepare_chapter_data.py` and has been removed.

---

## Optional: socio-economic admin analysis (`99_optional_SE_analysis/`)

Not in Snakemake `all`. Ports the core of `SVI_Waste/.../SVI_Social_economic.ipynb` onto chapter GSVI panoids:

```bash
python 99_optional_SE_analysis/1_admin_se_waste_join.py
Rscript 99_optional_SE_analysis/2_plot_se_maps.R
Rscript 99_optional_SE_analysis/3_plot_se_correlations.R
```

Outputs: `Data/Chapter_waste/99_optional_SE_analysis/` and `Figure/99_optional_SE_analysis/`.

---

## Workflow (Snakemake)

Steps 0–5 (spatial chapter + R figures) can be orchestrated with Snakemake on this branch. Steps 6–7, notebooks, Colab, and Qwen stay manual (`7_heldout_validation/0_run_all.py`).

Requires `conda activate geo_env_LLM`, plus `snakemake` and Graphviz (`dot`) for the rulegraph. The Snakefile sets `PYTHONPATH` to the repo root so `lib/` and `chapter_paths.py` import without extra setup.

```bash
# Paths: default is this machine; override with --config or PHD_DATA_ROOT
export PHD_DATA_ROOT=/Users/wenlanzhang/Downloads/PhD_UCL/Data

snakemake -n                          # dry-run
snakemake all_data --cores 1          # processed GeoPackages / CSVs only
snakemake all --cores 1               # data + figures (Steps 0–5)
snakemake dag --cores 1               # Figure/workflow/spatial_rulegraph.pdf
# or: bash workflow/export_dag.sh

# Rebuild one branch
snakemake Figure/5_spatial_pattern/HDBSCAN/Waste_HDBSCAN_gsvi.png --cores 1
```

Config lives in `workflow/config.yaml` (`phd_data_root`, `use_extended_grid`, `include_osmnx`, H3/buffer settings). Optional extras not in `all`:

```bash
snakemake mitigation_validation_sensitivity --cores 1
snakemake plot_mitigation_overlap_pattern --cores 1
```

Hand-running `python` / `Rscript` as below still works. The bash quick start is unchanged.

---

## Quick start (full pipeline)

```bash
conda activate geo_env_LLM
cd /Users/wenlanzhang/PycharmProjects/Chapter_waste

# Step 1 — harmonised layers + local roads
python 1prepare_chapter_data/1_prepare_chapter_data.py
Rscript 1prepare_chapter_data/plot_maps.R

# Step 1 — OSMnx roads, comparison, road figures
python 1prepare_chapter_data/2_prepare_osmnx_roads.py
Rscript 1prepare_chapter_data/plot_road_figures.R

# Step 0 — optional Mollweide fill (preferred grid for Step 3)
python 0_extend_grid/1_extend_grid.py
python 0_extend_grid/2_provenance_extended.py
Rscript 0_extend_grid/3_plot_extended_grid.R

# Step 2 — coverage (uses local cleaned roads from step 1a)
python 2coverage_analysis/1cityroad.py
python 2coverage_analysis/2roadsvi.py
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 75
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 100
python 2coverage_analysis/3sviwaste.py

Rscript 2coverage_analysis/1plot_cityroad_maps.R --h3-res=8 --road-buffer-m=50
Rscript 2coverage_analysis/1plot_cityroad_analysis.R --h3-res=8 --road-buffer-m=50
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m=50
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m=75
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m=100
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m=50
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m=75
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m=100
Rscript 2coverage_analysis/3plot_sviwaste_maps.R

# Step 3 — 100 m grid coverage + validation (+ provenance)
python 3_100m/1_grid_coverage.py
Rscript 3_100m/1_plot_grid_coverage_matrix.R
python 3_100m/2_validation_analysis.py
Rscript 3_100m/2_plot_validation_confusion_matrix.R
python 3_100m/3_mitigation_validation.py
Rscript 3_100m/3_plot_mitigation_validation.R
Rscript 3_100m/3_plot_mitigation_validation_severity.R
Rscript 3_100m/3_plot_mitigation_validation_overlap.R
python 3_100m/4_indicator_provenance.py
Rscript 3_100m/4_plot_indicator_provenance_map.R
python 3_100m/5_validation_by_provenance.py

# Step 4 — compare GSVI vs GSVI + self-collected (after Step 1)
python 4_compare/1_compare_sources_table.py
Rscript 4_compare/1_plot_svi_sources_map.R
Rscript 4_compare/2_plot_waste_sources_map.R
Rscript 4_compare/3_plot_sources_comparison_panel.R

# Step 5 — spatial pattern (after Step 2c; panorama unit)
python 5_spatial_pattern/settlement/1_nnr_observation_frame.py
python 5_spatial_pattern/settlement/2_settlement_association.py
python 5_spatial_pattern/Distance_decay/1_distance_decay_negexp.py
python 5_spatial_pattern/Signed_distance/1_signed_distance_gam.py
python 5_spatial_pattern/pop_adjusted/1_pop_adjusted_gam.py
python 5_spatial_pattern/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py
python 5_spatial_pattern/settlement/5_temporal_robustness.py
python 5_spatial_pattern/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py
python 5_spatial_pattern/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py
Rscript 5_spatial_pattern/settlement/3_plot_settlement_association.R
Rscript 5_spatial_pattern/Distance_decay/2_plot_distance_decay.R
Rscript 5_spatial_pattern/Distance_decay/3_plot_negexp_notebook_style.R
Rscript 5_spatial_pattern/Signed_distance/2_plot_signed_distance_gam.R
Rscript 5_spatial_pattern/pop_adjusted/2_plot_pop_adjusted_gam.R
Rscript 5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R
Rscript 5_spatial_pattern/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R
Rscript 5_spatial_pattern/pop_adjusted/3_plot_mdp_residual_map.R --data-subdir=worldpop_2020 --fig-subdir=worldpop_2020
Rscript 5_spatial_pattern/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R
Rscript 5_spatial_pattern/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R
Rscript 5_spatial_pattern/settlement/6_plot_temporal_robustness.R
python 5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py
python 5_spatial_pattern/HDBSCAN/4_mitigation_comparison.py
python 5_spatial_pattern/HDBSCAN/5_hdbscan_cluster_views.py
python 5_spatial_pattern/HDBSCAN/6_hdbscan_100m_sensitivity.py
Rscript 5_spatial_pattern/HDBSCAN/3_plot_hdbscan_map.R
Rscript 5_spatial_pattern/HDBSCAN/5_plot_hotspot_difference_map.R
Rscript 5_spatial_pattern/HDBSCAN/4_plot_new_obs_stacked_bar.R
Rscript 5_spatial_pattern/HDBSCAN/6_plot_hdbscan_100m_sensitivity.R
python 5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py
Rscript 5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R
Rscript 5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R
python 5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py
Rscript 5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R
python 5_spatial_pattern/KDE/1_kde_hotspots.py
Rscript 5_spatial_pattern/KDE/2_plot_kde_comparison.R

# Step 6 — YOLO training mix (SC in training; 100% = baseline, 0% = no SC)
jupyter notebook 6_sensitivity_training/1_training_dataset_pipeline.ipynb
Rscript 6_sensitivity_training/7_plot_baseline_training_curves.R

# Step 7 — independent 180 GSVI held-out validation
# Canonical set: Waste/img/7_heldout_validation/20260807_heldout_GSVI_p100_label/
# Colab YOLO val → 4_Qwen_yolo_positives_replicates.ipynb → python 7_heldout_validation/0_run_all.py
```


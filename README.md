# Chapter_waste — Nairobi waste & SVI spatial analysis

Street-view imagery of Nairobi is turned into a 100 m visible-waste indicator, and the gap between what was *observed* and what the indicator *claims* is measured at every stage.

```
Step 1  prepare      harmonised layers: waste, SVI, boundary, settlements, 100 m grid, roads
Step 0  extend       optional Mollweide fill of grid gaps (preferred grid downstream)
Step 2  coverage     city → road → SVI → waste, on road metres and 100 m cells
Step 3  identify     YOLO and YOLO → Qwen on the independent held-out image set
Step 4  indicator    100 m indicator: observed vs interpolated, validated against local clicks
Step 5  pattern      clustering, settlement association, signed-distance GAM
```

Steps 3–5 each report what the evidence actually supports: Step 3 the classifier's precision, Step 4 the share of the published surface that is estimated rather than measured, Step 5 whether the spatial pattern survives the observation frame.

## Folder structure

```
Chapter_waste/
├── chapter_paths.py            PHD_DATA_ROOT, step dirs, active 100 m grid
├── lib/                        shared Python (arms, paths, ideamaps, provenance, panoids, roads)
├── R/                          shared R (chapter_paths, map_theme, chapter_colours, arms)
├── workflow/                   Snakefile + rules/00–05
│
├── 0_extend_grid/              optional: Mollweide 100 m fill of grid gaps
├── 1prepare_chapter_data/      harmonised layers, local + OSMnx roads, road figures
├── 2coverage_analysis/         1cityroad / 2roadsvi / 3sviwaste / 4roadwaste / 5_gridsvi (+ plots)
├── 3_waste_identification/     held-out metrics, Qwen review, replicate notebook (+ plots)
├── 4_100m/                     indicator build, crowd validation (+ plots)
├── 5_spatial_pattern/
│   ├── HDBSCAN/                clustering + settlement context
│   ├── settlement/             association, NNR null, temporal robustness
│   └── Signed_distance/        GAM (+ pop_adjusted/ sensitivity)
│
├── Figure/<step>/              outputs, numbered by the block that produces them
├── drafts/                     scratch analyses kept out of the pipeline
└── archive/2026-09-21/         superseded scripts; nothing live reads them
```

Data lives outside the repo under `$PHD_DATA_ROOT/Chapter_waste/<step>/`, mirroring these names. Each step writes its chapter tables to `<step>/thesis_table/` and its working outputs beside them.

## Analysis arms

Two arms are defined once in `lib/arms.py`:

| Key | Tag | Sources | Step 1 layers |
| --- | --- | --- | --- |
| `gsvi` | `gsvi` | Google | `Nairobi_{Waste_point,SVI_point,SVI_image}_gsvi_32737.gpkg` |
| `gsvi_selfcollected` | `gsc` | Google + Faith + ZWL | `…_gsvi_selfcollected_32737.gpkg` |

**The chapter uses the GSVI arm throughout.** Step 1 builds both; everything downstream reports GSVI. The self-collected comparison is the observation-opportunity argument and lives in `drafts/observation_opportunity/`.

Per-arm files carry the key as infix (`arm.filename("Nairobi_grid_coverage")` → `…_gsvi_32737.gpkg`).

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
python 0_extend_grid/2_provenance_extended.py   # provenance on extended grid, both arms
Rscript 0_extend_grid/3_plot_extended_grid.R
```

**Figures:** `Figure/0_extend_grid/Grid_extension_angela_vs_fill.png`, `Indicator_provenance_100m_extended_{gsvi,gsvi_selfcollected}.png`

`2_provenance_extended.py` runs once per arm and writes `Nairobi_indicator_provenance_{cells,summary}_extended_{arm}.csv`. It reuses the same `lib/ideamaps.py` pipeline as Step 4 but writes only to `0_extend_grid/`. For the chapter's provenance numbers, use Step 4 (`4_100m/1_indicator_build.py`), which runs on the grid the rest of the chapter uses.

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

**Grid prep:** Raw `Waste/Angela/IDEAmaps_grid-boundary-nairobi.gpkg` is intersected with the constituency boundary, filtered to cells whose centroids fall inside the study area, and reprojected to EPSG:32737. Optional Step 0 fills the remaining constituency gaps with Mollweide 100 m cells while preserving Angela `cell_id` values; when that extended gpkg exists, `chapter_paths.active_grid_gpkg()` prefers it and Steps 2 and 4 follow.

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

**Naming:** every Step 2 output is prefixed with the number of the block that produces it (`1_` cityroad, `2_` roadsvi, `3_` sviwaste, `4_` roadwaste, `5_` gridsvi + cell-level analysis figures, `6_` process schematic); thesis tables are `table_1` … `table_5` plus the cross-step `table_0_coverage_headline.csv`.

**Arms:** Step 2 is computed for the **GSVI arm only** (the self-collected arm enters at Step 3 onwards). Scripts still accept `--arm gsvi_selfcollected` for ad-hoc runs (outputs then carry the arm key and figures an `_<arm>` suffix), but the pipeline, tables and figures are GSVI-only. Data files carry the arm key (`…_buf50m_gsvi.gpkg`, `3_Nairobi_sviwaste_points_gsvi_32737.gpkg`); thesis tables are `Variable | Value | Unit`. 2a (city → road) is arm-independent.

**Road input:** `Nairobi_road_03_local_cleaned_32737.gpkg` (local OSM cleaned segments; from step 1a).

### 2a. `1cityroad.py` — City → road (100 m grid)

**Unit:** the active 100 m grid (`chapter_paths.active_grid_gpkg()`, 69,943 cells). Arm independent. For each cell, three road metrics from the cleaned local OSM segments:

| Road metric | Definition | Why keep it |
| --- | --- | --- |
| Road-accessible cell (`road_accessible`) | Cell intersects a mapped road, **or** its edge lies within `--road-buffer-m` (50 m) of one | Main measure of whether a road-based observation system could potentially observe the cell |
| Road length / density (`road_length_m`, `road_density_km_per_km2`) | Total mapped road length inside the cell; km per km² | Distinguishes a cell with one tiny road segment from a highly road-connected cell |
| Distance to nearest road (`dist_road_edge_m`) | Cell polygon edge → nearest road (0 if it intersects) | Quantifies the severity of road-network exclusion for cells without roads |

Also `intersects_road`, `n_road_segments`, `cell_area_m2`, `grid_source`.

```bash
python 2coverage_analysis/1cityroad.py                      # --road-buffer-m 50
Rscript 2coverage_analysis/1plot_cityroad_maps.R
Rscript 2coverage_analysis/1plot_cityroad_analysis.R
```

**Outputs:** `1_Nairobi_cityroad_grid100m_32737.gpkg` (per cell), `1_Nairobi_cityroad_summary_buf50m.csv`, `thesis_table/table_1_cityroad_buf50m.csv`

Current run: 66.8% of cells intersect a road, 80.2% are road-accessible at 50 m, 19.8% (13,823 cells) are road-excluded — median 138 m and 90th-pct 430 m from the nearest road. Mean road density in cells with road: 16.3 km/km².

**Figures:** `1_Nairobi_cityroad_access_buf50m.png` (intersects / within 50 m / excluded), `1_Nairobi_cityroad_density_grid100m.png` (cells with road), `1_Nairobi_cityroad_distance_buf50m.png` (excluded cells), `1_Nairobi_cityroad_analysis_buf50m.png` (A density histogram, B distance histogram).

---

### 2b. `2roadsvi.py` — Road → SVI (metre level)

**Unit:** Road metres within local cleaned OSM segments (one row per OSM way segment).

Each SVI panoid is buffered (default **50 m**). For each road segment, nearby buffers are unioned and the line is split into **covered** and **uncovered** parts (`segment ∩ zone` and `segment − zone`). Partially covered segments contribute metre length to both classes — uncovered sub-parts appear as gaps on the map.

```bash
python 2coverage_analysis/2roadsvi.py                                  # GSVI, 50 m
# Rebuild only the thesis table from the existing summary:
python 2coverage_analysis/2roadsvi.py --table-only --svi-buffer-m 50
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m=50
```

The buffer distance is a parameter (`--svi-buffer-m`), but only the 50 m result is part of the pipeline; the 75/100 m sensitivity outputs were dropped (archived under `archive_2026-09-21/2coverage_analysis_buffer_sensitivity/`).

**Outputs** (tagged by buffer + arm, `buf50m_gsvi`):

- `2_Nairobi_roadsvi_coverage_buf50m_gsvi.gpkg` — covered/uncovered line parts (for maps)
- `2_Nairobi_roadsvi_grid100m_buf50m_gsvi.gpkg` — per 100 m cell: `road_m_covered`, `road_m_uncovered`, `road_m_total`, `svi_road_coverage_ratio` (NaN without road)
- `2_Nairobi_roadsvi_summary_buf50m_gsvi.csv` — citywide metres + cell-level summary
- `thesis_table/table_2_roadsvi_buf50m.csv` — `Variable | Value | Unit` (60.0% road length covered at 50 m)

**Figure (`2plot_roadsvi_maps.R`):**
- Uncovered roads: light grey = all road metres; red = metres outside SVI buffers (`2_Nairobi_roadsvi_uncovered_buf50m.png`, + `_hires`)
- `2_Nairobi_roadsvi_analysis_grid100m_buf50m.png` — per-cell coverage ratio: A distribution (bimodal: 30.9% of road cells fully covered, 38.9% uncovered, median 0.56), B road length vs ratio (binned counts + GAM, ρ = 0.30)

**Process schematic (`6plot_process_zoom_map.R`):** a compact block of 100 m cells (default 3 × 3 = 9; `--block-cols/--block-rows`, e.g. 4 × 4) chosen automatically among interior cells in the `--density-min/--density-max` road-density range (10–30 km/km²) with at least 2 sampling points per cell and ≥1 waste-positive point; override with `--seed-cell-id=<cell_id>` (bottom-left cell). The layers block additionally needs ≥ ⌊n/3⌋ waste-positive points and is distinct from the panel block. Thresholds scale with block size unless set explicitly (`--min-svi-points`, `--panel-waste-min/max`, `--layers-waste-min/max`).

- **`_panels.png`** — 2×2 step-by-step (A: 100 m grid with road density, B: roads, C: SVI-supported vs unsupported road metres, D: waste-positive points)
- **`_layers.png`** / **`_layers_inset.png`** — single map with all layers and example SVI buffers; `_inset` adds a study-area locator (top-left)

```bash
Rscript 2coverage_analysis/6plot_process_zoom_map.R                      # both outputs
Rscript 2coverage_analysis/6plot_process_zoom_map.R --layout=panel
Rscript 2coverage_analysis/6plot_process_zoom_map.R --block-cols=4 --block-rows=4
Rscript 2coverage_analysis/6plot_process_zoom_map.R --seed-cell-id=26735 --layers-seed-cell-id=26735
```

**Output:** `6_Nairobi_process_zoom_grid100m_{3x3,4x4}_svi50_{panels,layers,layers_inset}.png` (study-area inset top-left); both block sizes are pipeline targets

---

### 2c. `3sviwaste.py` — SVI → waste (sampling-point level)

**Unit:** SVI sampling point — a GSVI panoid, or a single self-collected image (Faith/ZWL images carry no panoid). Keyed by `lib.arms.observation_key` (panoid where present, else `img:<img_name>`).

Each sampling point is labelled **waste-positive** if its key appears in the waste dataset.

| Variable         | Value  | Unit |
| ---------------- | ------ | ---- |
| Total SVI        | 76,605 |      |
| Waste-positive   | 2,696  |      |
| Waste detections | 3,236  |      |
| Detection rate   | 3.5    | %    |

```bash
python 2coverage_analysis/3sviwaste.py                     # GSVI + table_3
Rscript 2coverage_analysis/3plot_sviwaste_maps.R
```

**Outputs:** `3_Nairobi_sviwaste_points_gsvi_32737.gpkg`, `3_Nairobi_sviwaste_summary_gsvi.csv`, `thesis_table/table_3_sviwaste.csv`

**Figure:** light blue = all SVI sampling points; red = waste-positive panoids. Subtitle shows total SVI count.

### 2d. `4roadwaste.py` — Road → waste-positive panoid (metre level)

**Unit:** Road metres; same split logic as `2roadsvi.py` (`lib.road_coverage`), but buffers only the **2,696 waste-positive** panoids from 2c (not all 76,605 sampling panoids).

```bash
python 2coverage_analysis/4roadwaste.py                     # GSVI, 50 m
python 2coverage_analysis/4roadwaste.py --table-only
```

**Outputs** (`Data/.../2coverage_analysis/`):

- `4_Nairobi_roadwaste_coverage_buf50m_gsvi.gpkg` — covered/uncovered line parts
- `4_Nairobi_roadwaste_summary_buf50m_gsvi.csv` — citywide metres + all-GSVI reference % (`pct_road_length_covered_all_svi`)
- `thesis_table/table_4_roadwaste_buf50m.csv` — 6.1% of road length within 50 m of a waste-positive panoid

### 2e. `5_gridsvi.py` — GSVI → analytical grid (+ headline table)

Returns from the road frame to the **100 m grid**: for every cell, GSVI images and panoramas inside it, `has_gsvi` (≥1 image), centroid distance to the nearest panorama (0 for observed cells), the 2a road metrics (`road_accessible`, `road_length_m`, `road_density_km_per_km2`, `n_road_segments`, `dist_road_edge_m`) and the 2b per-cell road coverage (`road_m_covered`, `road_m_uncovered`, `svi_road_coverage_ratio`). This is the joined cell-level analysis table.

**Sliver handling:** the Mollweide-extended grid leaves ~0.3% of the constituency uncovered along the boundary. 382 panoramas (1,528 images) fall in those slivers — inside the city, all within 64 m of a cell — and are snapped to the nearest cell (`SNAP_MAX_M = 100`), so totals reconcile with Step 1 (76,605 panoramas / 306,420 images). Note that `lib/ideamaps.py` (Step 0 provenance, Step 3 indicator) keeps the plain within-cell join to reproduce the IDEAMaps submission, so it reports 22,672 directly observed cells vs 22,725 here.

Both stages share the same denominator (all 69,943 urban cells), so the conditional coverage is direct:

*P*(GSVI | road-accessible) = *N*(road-accessible ∧ has_gsvi) / *N*(road-accessible) = 22,722 / 56,120 = **40.5%**

The 2 × 2 table (`5_Nairobi_gridsvi_road_crosstab_gsvi.csv`) is the consistency check — GSVI-observed cells that are road-excluded (cell D) should be rare, since Street View occurs on mapped roads:

| | No GSVI | GSVI | Total |
| --- | ---: | ---: | ---: |
| Road-accessible | 33,398 | 22,722 | 56,120 |
| Road-excluded | 13,820 | 3 | 13,823 |
| Total | 47,218 | 22,725 | 69,943 |

```bash
python 2coverage_analysis/5_gridsvi.py                     # --far-m 500
Rscript 2coverage_analysis/5plot_gridsvi_maps.R
```

**Outputs:** `5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg` (per cell, columns above), `5_Nairobi_gridsvi_summary_gsvi.csv`, `5_Nairobi_gridsvi_correlation_spearman_gsvi.csv`, `5_Nairobi_gridsvi_road_crosstab_gsvi.csv`, `thesis_table/table_5_gridsvi.csv`, and the chain summary `thesis_table/table_0_coverage_headline.csv` (needs the 2a and 2b summaries):

| Stage | Metric | Denominator | Value |
| --- | --- | --- | ---: |
| Urban → road frame | Cells within 50 m of mapped road | All urban 100 m cells | 80.2% |
| | Median distance to road among road-excluded cells | Road-excluded cells | 138 m |
| Road frame → GSVI | Road-accessible cells containing ≥1 GSVI panorama | Road-accessible cells | 40.5% |
| | Mapped road length with GSVI support | Total mapped road length | 60.0% |
| GSVI → analytical grid | Cells containing ≥1 direct GSVI observation | All urban 100 m cells | 32.5% |
| Observation intensity | Median panoramas per observed cell | Directly observed cells | 3 |
| Observation gaps | Cells >500 m from nearest GSVI observation | All urban 100 m cells | 18.8% |

Panoramas (not images) are the unit for observation intensity here: each panorama yields four directional images, so "12 images per cell" would overstate the number of observation locations. Images/cell (`table_5_gridsvi.csv`) becomes relevant again at the image-level classifier / indicator stage. The road-excluded share (19.8%) and the 90th-percentile distance (430 m) stay in `table_1_cityroad_buf50m.csv` for the appendix.

**Figures (`5plot_gridsvi_maps.R`):** `5_Nairobi_gridsvi_observed_grid100m.png` (≥1 image vs none), `5_Nairobi_gridsvi_distance_grid100m.png` (distance to nearest panorama, unobserved cells).

**Cell-level correlations (`5plot_gridsvi_analysis.R`, cells with mapped road, n = 46,702):** `5_Nairobi_gridsvi_correlation_spearman_grid100m.png` / `_scatter.png` — Spearman matrix over road density, road segments, GSVI panoramas and SVI road-coverage ratio (heatmap + binned pairwise panels). Road density ↔ segments ρ = 0.84; panoramas ↔ coverage ratio ρ = 0.80; road density ↔ coverage ratio only ρ = 0.30.

---

## Step 3 — Waste identification (YOLO + VLM)

Image-level evaluation of the waste detector on the **independent GSVI held-out set** (manual QA labels, balanced waste / background). The detector was retrained at several shares of self-collected (SC) imagery in its training set — one `sc_<share>pct` scenario per share — and every model is validated on the same images. Two stages are scored:

1. **YOLO only** — the detector's image-level prediction
2. **YOLO → Qwen** — a YOLO positive is kept only if Qwen2-VL also answers *Yes*; where several replicates exist the reported run is the one with the highest F1

The scenario set, the sample size and the headline scenario are all read from the data, not fixed in the scripts: `1_heldout_metrics.py --scenario` chooses the headline (default `sc_100pct`), and the plotting scripts derive their axes, labels, fills and captions from the table they are given.

```bash
python 3_waste_identification/2_qwen_review.py --dry-run   # plan the Qwen calls (no API use)
python 3_waste_identification/2_qwen_review.py             # label the remaining scenarios
python 3_waste_identification/1_heldout_metrics.py
Rscript 3_waste_identification/1plot_heldout_panel.R
Rscript 3_waste_identification/2plot_qwen_stability.R
Rscript 3_waste_identification/3plot_sc_sensitivity.R
Rscript 3_waste_identification/4plot_stage_comparison.R
```

**Inputs** (`Data/Chapter_waste/3_waste_identification/`, produced outside this pipeline). YOLO results and Qwen results live in separate folders:

```
3_waste_identification/
├── sampling/                                 # how the held-out set was drawn
│   ├── heldout_GSVI_p100_units.csv           #   one row per sampled panorama
│   └── heldout_GSVI_p100_test.csv            #   the images they expand to, with labels + img_dir
├── yolo/                                     # YOLO val runs
│   ├── heldout_GSVI_val_summary.csv          #   one row per scenario: box mAP + counts
│   ├── heldout_GSVI_p100_image_level_predictions.csv  # one row per image × scenario
│   └── heldout_GSVI_p100_sc_<share>pct_fp_conf001.csv # that scenario's false positives
├── qwen/                                     # Qwen answers
│   ├── qwen_responses_by_scenario.csv        #   2_qwen_review.py's raw response per scenario × image
│   └── qwen_labels_sc_<share>pct.csv         #   image_name, scenario, one column per replicate
└── thesis_table/                             # 1_heldout_metrics.py's output
```

`sampling/` records what the held-out set is and how it was drawn: sampling happens at **panorama** level so the directional views of one location cannot straddle train and test, then each panorama expands to its retained views. Its `class`, `bg_kind`, `sample_seed` and `in_training_695` columns are the audit trail for the balance, the hard-negative share, reproducibility, and the guarantee that nothing was seen in training. `2_qwen_review.py` also reads its `img_dir` column to locate each JPG on disk (falling back to the Google panorama tree) — the same files YOLO was validated on. For the current draw: 100 panoramas → 180 images, 90 waste / 90 background, 63 easy + 27 hard-negative backgrounds, seed `20260807`.

### Running the Qwen pass (`2_qwen_review.py`)

Two Qwen routes exist, deliberately. Both live in `3_waste_identification/` and call Qwen2-VL-72B via Segmind with the **same prompt and the same image files**, so their answers are comparable; only the replicate count differs.

| | Replicates | Scenarios | Role |
| --- | --- | --- | --- |
| `3_qwen_replicates.ipynb` | 3 | the headline scenario | source of the repeated-inference stability result (`table_3`) |
| `2_qwen_review.py` | 1 | every scenario in the predictions file | fills in each detector's `YOLO → Qwen` row |

**Each scenario is reviewed independently.** Every YOLO-positive row gets its own API call, keyed by `(scenario, image_name)`, so an image that two detectors both call positive is queried once for each of them. `--dry-run` reports the call count before anything is spent.

Answers go to `qwen/qwen_responses_by_scenario.csv` as they arrive, so a run can be interrupted and resumed; failed or empty responses are retried automatically. That file is the script's own output — it never reads Qwen results produced anywhere else.

The script reviews **all** YOLO positives, not only the false positives — the cascade is `YOLO positive AND Qwen Yes`, so Qwen's verdict on a *true* positive matters too: a *No* there turns a TP into an FN, and that is the recall cost the figures report. Reviewing only false positives would measure the precision gain while silently assuming the recall cost was zero.

Images come from the sampling inventory's `img_dir`, falling back to the Google panorama tree. The YOLO val runs also exported a folder of false-positive JPGs per scenario; those were byte-identical copies of images already in the Google tree, and only covered the false positives (171 of the 601 rows queried), so they have been deleted. The `*_fp_conf001.csv` files stay — `1_heldout_metrics.py` reads them to report how many false positives a scenario has waiting when it has no Qwen labels yet.

Two guards against half-finished work, learned the hard way:

- a scenario is skipped only when its label file is **complete**; a partial file is reported as `redo` and picked back up, and an incomplete scenario is never written out (a stale partial is removed so nothing downstream reads it)
- the notebook's export cell refuses to write when the replicate columns are still blank

Start with `--dry-run` (reports the call count, makes none), then `--limit 3` as a smoke test. The key is read from `SEGMIND_API_KEY`, or prompted for interactively — never stored in the repo. Superseded single-scenario inputs live in `Data/Chapter_waste/archive/2026-09-23/3_waste_identification/`; no script reads that folder.


**Results.** The numbers below are the current run; `thesis_table/*.csv` is the source of truth and every figure caption is generated from it.

| Independent GSVI test | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| YOLO only | 80.6% (74.2–85.7) | 73.9% (65.2–81.1) | 94.4% (87.6–97.6) | 82.9% (77.2–87.5) |
| YOLO → Qwen | 92.8% (88.0–95.7) | 94.3% (87.2–97.5) | 91.1% (83.4–95.4) | 92.7% (87.8–95.7) |

Headline scenario `sc_100pct`, Wilson binomial 95% CIs, n = 180 (`table_2_yolo_qwen_heldout_ci.csv`). The VLM pass removes 25 of 30 YOLO false positives at the cost of 3 true positives — precision +20 pp for −3 pp recall.

**Sensitivity to the SC share of the YOLO training set** (`table_1_yolo_detection.csv` box level, `table_4_sc_sensitivity.csv` image level):

| YOLO training set | mAP@0.50 | mAP@0.50:0.95 | Accuracy | Precision | Recall | F1 | YOLO FPs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0% self-collected | 39.1% | 14.5% | 75.6% | 68.5% | 94.4% | 79.4% | 39 |
| 25% self-collected | 40.0% | 14.9% | 78.9% | 71.0% | 97.8% | 82.2% | 36 |
| 50% self-collected | 40.5% | 16.1% | 77.8% | 70.8% | 94.4% | 81.0% | 35 |
| 75% self-collected | 39.8% | 15.4% | 81.1% | 73.7% | 96.7% | 83.7% | 31 |
| **100% self-collected** | **45.0%** | **17.5%** | **80.6%** | **73.9%** | **94.4%** | **82.9%** | **30** |

Adding self-collected imagery mainly buys **precision**: false positives fall from 39 to 30 and mAP@0.50 gains ~6 pp, while recall stays in the 94–98% band throughout.

**Stability** (`table_3_qwen_replicates.csv`, from the notebook): the three independent Qwen calls on all 115 `sc_100pct` YOLO-positive images agree unanimously on 108/115 (93.9–97.4% pairwise); per-run F1 91.4 / 92.7 / 92.1%, 3-run majority 92.7%. This is the one place a multi-replicate run exists, which is why `sc_100pct` is flattered by roughly a point of F1 relative to the single-pass scenarios — the figure captions state this automatically, read off the `qwen_status` column.

**Figures** (`Figure/3_waste_identification/`):

| Figure | Script | Shows |
| --- | --- | --- |
| `1_Heldout_yolo_qwen_panel.png` | `1plot_heldout_panel.R` | Headline scenario, **both stages**: metric bars with 95% CI + two confusion matrices |
| `1_Heldout_qwen_only_panel.png` | `1plot_heldout_panel.R` | Same, **YOLO + Qwen alone** — the final result without the baseline beside it |
| `2_Heldout_qwen_replicate_stability.png` | `2plot_qwen_stability.R` | Per-replicate metrics, Yes/No votes, unanimity, pairwise agreement |
| `3_Heldout_validation_binary_metrics.png` / `3_Heldout_validation_binary_bars.png` | `3plot_sc_sensitivity.R` | **YOLO + Qwen only**, across every SC share in the table (lines and grouped bars) |
| `4_Heldout_validation_stage_metrics.png` / `4_Heldout_validation_stage_bars.png` | `4plot_stage_comparison.R` | **Both stages side by side**, faceted by metric, across every SC share |

Figures 3 and 4 replace the archived Step 7 `Heldout_validation_binary_*` charts, which had a second panel for a self-collected held-out set; that panel is dropped, so the GSVI set is the whole figure. Adding or removing a scenario needs no edit to either script — levels, labels, fills, x-axis breaks, the detector count and the replicate note are all derived from the input table.

**The VLM gain**, YOLO + Qwen minus YOLO only, in percentage points — `4plot_stage_comparison.R` recomputes and prints this on every run:

| SC share | Accuracy | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| 0% | +15.5 | +22.6 | −3.3 | +11.7 |
| 25% | +15.5 | +22.5 | −2.2 | +12.3 |
| 50% | +15.5 | +24.5 | −3.3 | +12.2 |
| 75% | +12.8 | +21.7 | −4.5 | +10.1 |
| 100% | +12.2 | +20.4 | −3.3 | +9.8 |

The cascade can only remove positives, so precision always rises and recall always falls. The gain is **largest where the detector is weakest** (+11.7 to +12.3 pp F1 at 0–50% SC, +9.8 pp at 100%), which is why the post-cascade curves in figure 3 are nearly flat: the VLM substitutes for the self-collected training data rather than compounding with it.

---

## Step 4 — The 100 m visible-waste indicator (`4_100m/`)

Turns the image-level waste classifications of Step 3 into the 100 m cell indicator that was submitted to IDEAMaps, and keeps **measurement separate from estimation** throughout. The pipeline (`lib/ideamaps.py`, matching `SVI_IDEAMaps.ipynb`) is:

1. count GSVI images and waste-positive detections per cell
2. raw waste/image ratio, then an Empirical Bayes shrunk ratio
3. **linear spatial interpolation** of that ratio over cell centroids (`scipy.interpolate.griddata`)
4. Jenks k=3 using the fixed IDEAMaps submission break points

Steps 1-2 are measurement; step 3 is estimation. Every cell is therefore labelled (`lib/provenance.py`):

| Provenance | Definition |
| --- | --- |
| Direct observation | ≥1 GSVI image in the cell |
| Interpolated support | no imagery; ratio estimated by the spatial fill |
| Unsupported, platform-coded low | outside the interpolation hull, so NaN → 0 |

Only two of the outputs are chapter tables — `thesis_table/table_3_indicator_summary.csv` (the indicator summary) and `thesis_table/table_4_validation.csv` (agreement by provenance). Everything else lands beside the grid in `4_100m/` as a working output: the descriptive breakdowns, the support-distance robustness check, and the numbers behind each figure.

```bash
python 4_100m/1_indicator_build.py
python 4_100m/2_validation.py
Rscript 4_100m/1plot_indicator_panels.R
Rscript 4_100m/2plot_validation.R
```

### 4a. What the directly observed indicator looks like (`1_indicator_direct.csv`)

Of 69,943 grid cells, **22,672 (32.4%) contain ≥1 GSVI image**, carrying 304,892 images (median 12 per observed cell, IQR 8-16). Only **2,065 observed cells (9.1%) contain any waste detection**, from 3,228 detections. The cell measure is strongly zero-inflated: 90.9% of observed cells have a ratio of exactly 0, so quantiles over all observed cells are uninformative and the table reports the zero mass separately from the distribution among waste-positive cells (median ratio 0.083, IQR 0.050-0.125).

### 4b. What changes when the indicator is interpolated (`2_indicator_*.csv`)

| Provenance | Cells | Share of grid | Distance to nearest observed cell |
| --- | --- | --- | --- |
| Direct observation | 22,672 | 32.4% | — |
| Interpolated support | 45,677 | 65.3% | median 210 m, p90 1,003 m, max 3,133 m |
| Unsupported, coded low | 1,594 | 2.3% | median 982 m |

**Two-thirds of the published surface is estimated rather than measured**: of the 68,349 represented cells, only 33.2% rest on direct evidence. The 1,594 unsupported cells fall outside the convex hull of observed cells, so `griddata` returns NaN and `.fillna(0)` encodes them as the *lowest* class — absence of evidence published as evidence of absence.

`2_indicator_support_distance.csv` reports what a maximum support distance would cost. Nothing is capped by default:

| Cap | Interpolated retained | Grid represented | Direct share of represented |
| --- | --- | --- | --- |
| 100 m | 11,998 | 49.6% | 65.4% |
| 200 m | 21,816 | 63.6% | 51.0% |
| 500 m | 34,237 | 81.4% | 39.8% |
| none (as published) | 45,677 | 97.7% | 33.2% |

### 4c. Does the indicator agree with the local dataset? (`table_4_validation.csv`)

2,374 of 2,768 IDEAMaps crowd clicks fall inside the grid, covering 2,286 cells (one row per cell, maximum severity across validators). Agreement with the **recomputed** indicator, split by provenance:

| Validated subset | Cells | Agreement | Precision | Recall | Kappa |
| --- | --- | --- | --- | --- | --- |
| All validated | 2,286 | 73.2% | 62.0% | 47.9% | 0.291 |
| **Direct observation** | 1,016 | **77.5%** | **92.8%** | 52.4% | **0.461** |
| **Interpolated support** | 1,270 | **69.8%** | **38.7%** | 41.6% | **0.129** |

Precision separates the two most sharply: when the indicator calls a cell waste **on the strength of imagery collected there it is right 93% of the time; on interpolation alone, 39%**. Kappa falls from 0.461 to 0.129. The table also bands interpolated cells by distance from evidence; the >500 m band (n = 82) is small and behaves erratically, so it should not be over-read.

### Figures (`Figure/4_100m/`)

| Figure | Script | Shows |
| --- | --- | --- |
| `1_Nairobi_indicator_panels_grid100m_gsvi.png` | `1plot_indicator_panels.R` | **A** directly observed indicator, **B** after interpolation, **C** published 3-class surface. A and B share a colour scale capped at the 99th percentile |
| `2_Nairobi_indicator_validation_grid100m_gsvi.png` | `2plot_validation.R` | **A** agreement / precision / recall by provenance, **B** 3-class crowd × indicator confusion matrix |
| `3_Nairobi_indicator_validation_map_grid100m_gsvi.png` | `3plot_validation_map.R` | Validated cells mapped over **A** the indicator surface and **B** indicator provenance, coloured by agreement |

Figure 1 is the centrepiece: panel A is patchy and follows the road network, panel B is a continuous surface. The reader can see directly where the indicator is evidence and where it is estimate.

---

## Step 5 — Spatial pattern of visible waste (`5_spatial_pattern/`)

Takes the **2,696 waste-positive GSVI panoramas** (of 76,605 available) and asks where they fall: are they clustered, are they associated with urban-poor settlements, and does that association survive controls. **GSVI arm only** — the self-collected comparison is the mitigation story and stays in `drafts/observation_opportunity/`.

```
5_spatial_pattern/
├── HDBSCAN/           hotspots, settlement context, cluster sizes, 100 m sensitivity
├── settlement/        2×2 association, observation-frame NNR null, temporal robustness
└── Signed_distance/   year-adjusted logistic GAM
    └── pop_adjusted/  sensitivity: does the gradient survive population density + a spatial field
```

### 5a. Clustering (`HDBSCAN/`)

HDBSCAN (min_cluster_size 25, min_samples 6) on the 2,696 positives gives **24 clusters**, 767 noise points (28.4%), silhouette 0.496. **22 of the 24 clusters contain at least one positive inside a mapped urban-poor settlement**; 501 positives (18.6%) fall inside one.

### 5b. Settlement association (`settlement/`)

| Zone | Area | GSVI panoids | Waste-positive | Rate | Density |
| --- | --- | --- | --- | --- | --- |
| Urban poor | 19.9 km² | 3,757 | 501 | **13.3%** | 25.2 /km² |
| Non-urban-poor | 675.2 km² | 72,848 | 2,195 | **3.0%** | 3.3 /km² |

The **observation-frame NNR** is the important control. Rather than comparing against complete spatial randomness over the city polygon — which would only re-discover that Street View follows roads — it draws 2,696 panoramas at random from the 76,605 that were actually available. Observed mean 1-NN distance is **106.3 m against a null of 189.1 m (NNR 0.562, p = 0.001, 999 permutations)**. Waste positives are clustered *relative to where the platform could see*, not merely relative to the map. (The classic Clark-Evans figure, NNR 0.419, is kept as an appendix number and should not be the headline.)

### 5c. Signed-distance GAM (`Signed_distance/`)

`logit P(waste) = α + s(signed distance to nearest settlement) + year FE`, on all 76,605 panoramas. Against a year-only null: **LRT χ² = 2,216.7 (df 7), p < 0.001**, pseudo-R² 0.114. The gradient is not an artefact of *when* imagery was captured.

**Sensitivity (`pop_adjusted/`)** — nested models on 74,882 panoramas with WorldPop density:

| Model | Terms | AIC | Pseudo-R² |
| --- | --- | --- | --- |
| M0 | year | 22,754 | 0.020 |
| MP | + population | 20,964 | 0.098 |
| MD | + distance | 20,681 | 0.110 |
| MDP | distance + population | 20,117 | 0.135 |
| MDPS | + thin-plate spatial field | 19,720 | 0.154 |

Adding distance to a population-only model improves AIC by ~850, so the settlement gradient is **not** just population density. The distance curve correlates 0.92 between MDP and MDPS, so it also survives a residual spatial field.

### 5d. Sensitivity and robustness

| Check | Question it answers | Result |
| --- | --- | --- |
| `HDBSCAN/3b_hdbscan_param_sweep.py` | Are the 24 clusters a tuning artefact? | Silhouette 0.496–0.517 across min_cluster_size 15–40 × min_samples 4–10. The chosen (25, 6) sits on a flat ridge, not a lucky peak. |
| `HDBSCAN/period_stratified_robustness/` | Do the hotspots depend on one capture campaign? | Same parameters per period: 2015–2019 → 19 clusters, 77.6% clustered; 2021–2022 → 9 clusters, 79.9% clustered. Same areas, near-identical clustered share. Fewer clusters later follows from fewer positives (980 vs 1,716). |
| `Signed_distance/period_stratified_robustness/` | Does the distance gradient hold in both periods? | Yes, in each period separately. Pseudo-R² 0.118 (2015–2019) vs 0.071 (2021–2022). |
| `settlement/5_temporal_robustness.py` | Do settlement rates drift by year? | Year-by-year positive rates and prevalence ratios (`Temporal_*_by_year.png`). |
| `Signed_distance/pop_adjusted/` | Is the gradient just population density? | No — adding distance to a population-only model gains ~850 AIC; distance curve correlates 0.92 between MDP and MDPS. |
| `HDBSCAN/5_hdbscan_cluster_views.py` | Do repeat views of one site inflate clusters? | Per-cluster `n_positive_views` descriptives; clustering itself stays one point per panorama. |
| `pop_adjusted/4_settlement_by_density_band.py` | Is the settlement association just density, without assuming a model? | No. Within equal-count density bands the inside-settlement rate exceeds outside in **7 of 7** reportable bands, from **11.1× down to 1.6×**. The gap narrows as density rises, so density carries real weight at the top end but never accounts for the association. |
| `pop_adjusted/worldpop_2020/` | Does the population control depend on which raster? | Repeats the nested GAMs with unconstrained WorldPop 2020 (n = 76,578) instead of constrained 2024 (n = 74,882). Model ordering is unchanged and MDP still beats MP, so the distance effect is not raster-specific. |

```bash
python  5_spatial_pattern/HDBSCAN/3b_hdbscan_param_sweep.py
python  5_spatial_pattern/HDBSCAN/period_stratified_robustness/1_period_hdbscan.py
Rscript 5_spatial_pattern/HDBSCAN/period_stratified_robustness/2_plot_period_hdbscan.R
python  5_spatial_pattern/Signed_distance/period_stratified_robustness/1_period_signed_distance_gam.py
Rscript 5_spatial_pattern/Signed_distance/period_stratified_robustness/2_plot_period_signed_distance_gam.R
python  5_spatial_pattern/Signed_distance/pop_adjusted/4_settlement_by_density_band.py
Rscript 5_spatial_pattern/Signed_distance/pop_adjusted/4plot_settlement_by_density_band.R
python  5_spatial_pattern/Signed_distance/pop_adjusted/worldpop_2020/1_pop_adjusted_gam.py   # slow
Rscript 5_spatial_pattern/Signed_distance/pop_adjusted/worldpop_2020/2_plot_pop_adjusted_gam.R
```

### Run order

The blocks are independent of each other; within each, the Python script must run before its plotting script. The pop-adjusted GAM is slow (thin-plate spatial field over ~75k panoramas, several minutes).

```bash
# 5a. clustering
python  5_spatial_pattern/HDBSCAN/3_hdbscan_waste.py
python  5_spatial_pattern/HDBSCAN/7_hdbscan_settlement_context.py
python  5_spatial_pattern/HDBSCAN/9_cluster_size_distribution.py
Rscript 5_spatial_pattern/HDBSCAN/7_plot_hdbscan_context_map.R
Rscript 5_spatial_pattern/HDBSCAN/9_plot_cluster_size_distribution.R
Rscript 5_spatial_pattern/HDBSCAN/8_plot_cluster_distance_composition.R

# 5b. settlement association
python  5_spatial_pattern/settlement/1_nnr_observation_frame.py
python  5_spatial_pattern/settlement/2_settlement_association.py
python  5_spatial_pattern/settlement/5_temporal_robustness.py
Rscript 5_spatial_pattern/settlement/3_plot_settlement_association.R
Rscript 5_spatial_pattern/settlement/6_plot_temporal_robustness.R

# 5c. signed-distance GAM
python  5_spatial_pattern/Signed_distance/1_signed_distance_gam.py
Rscript 5_spatial_pattern/Signed_distance/2_plot_signed_distance_gam.R

# 5c sensitivity: population-adjusted GAM (slow)
python  5_spatial_pattern/Signed_distance/pop_adjusted/1_pop_adjusted_gam.py
Rscript 5_spatial_pattern/Signed_distance/pop_adjusted/2_plot_pop_adjusted_gam.R
Rscript 5_spatial_pattern/Signed_distance/pop_adjusted/3_plot_mdp_residual_map.R
```

Or `snakemake all`, which resolves the same order.

### Figures (`Figure/5_spatial_pattern/`)

24 figures across `HDBSCAN/`, `settlement/` and `Signed_distance/` (the pop-adjusted sensitivity figures sit under `Signed_distance/pop_adjusted/`, mirroring the scripts). Three archived figures are **not** rebuilt — `Waste_HDBSCAN_comparison.png`, `Hotspot_area_difference_gsvi_selfcollected.png` and `Mitigation_new_obs_stacked_bar.png` — because each exists only to set GSVI beside GSVI+self-collected. Their scripts (`4_mitigation_comparison.py`, `4b_mitigation_param_sensitivity.py`, `5_plot_hotspot_difference_map.R`) stay in `archive/2026-09-21/5_spatial_pattern/HDBSCAN/`.

`Waste_HDBSCAN_gsvi.png` is also dropped: `Waste_HDBSCAN_context_gsvi.png` shows the same 24 clusters with the same numbering and parameters, plus settlement boundaries, named settlements and the Dandora landfill — the plain version added nothing. Its script `3_plot_hdbscan_map.R` is removed.

KDE and distance-decay/NegExp are also excluded by choice; they remain archived under `Distance_decay/` and `KDE/`.

---

---

## Environment


| Tool                                             | Environment                  |
| ------------------------------------------------ | ---------------------------- |
| Python (geopandas, osmnx, shapely, hdbscan, statsmodels, rasterio) | `conda activate geo_env_LLM` |
| Qwen review (`segmind`) — Step 3, paid API | `pip install 'segmind>=1.1.0'`, key in `SEGMIND_API_KEY` |
| Snakemake 7 — Steps 0–5 wrap | `conda activate geo_env_LLM` (`pip install 'snakemake==7.32.4'`) |
| R (sf, ggplot2, ggspatial, ggpattern, dplyr, scales, patchwork, cowplot) | system R (`Rscript`)         |
| Data roots                                       | `PHD_DATA_ROOT` via `chapter_paths.py` / `R/chapter_paths.R` |


---

## Workflow (Snakemake)

```bash
conda activate geo_env_LLM

snakemake -n all                 # dry run
snakemake -c1 all                # everything
snakemake -c1 --forcerun <rule>  # rebuild one rule
snakemake -c1 all_figures        # figures only
```

Paths default to this machine; override with `PHD_DATA_ROOT` or `--config`. Tunables (`road_buffer_m`, `svi_buffer_m`, `use_extended_grid`, `include_osmnx`) are in `workflow/config.yaml`; everything else is derived from `chapter_paths.py`.

Rules are grouped per step in `workflow/rules/`, and `all` collects every step's data and figure targets.

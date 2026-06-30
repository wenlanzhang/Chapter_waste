# Chapter_waste — Nairobi waste & SVI spatial analysis

Pipeline for cleaning, harmonising, and analysing street-view imagery (SVI), waste detections, roads, and slums in Nairobi. Python handles data processing; R produces publication-style maps.

**Study area:** Nairobi constituency boundary  
**Projected CRS:** EPSG:32737 (UTM zone 37S)

---

## Folder structure

```
Chapter_waste/
├── README.md
├── R/
│   └── map_theme.R                 # Shared ggplot2 theme, north arrow, scale bar, legend
│
├── 1prepare_chapter_data/
│   ├── 1_prepare_chapter_data.py   # Step 1: clean & export harmonised layers
│   ├── 2_prepare_osmnx_roads.py    # Step 1 (cont.): OSMnx roads + local vs OSMnx comparison
│   ├── road_utils.py               # Shared road cleaning, noding, comparison
│   ├── plot_maps.R                 # Step 1 layer preview maps (waste, SVI, slums…)
│   ├── plot_road_figures.R         # Five numbered road network figures (01–05)
│   ├── plot_road_type_composition.R
│   ├── plot_road_type_composition_osmnx.R
│   └── plot_road_network_comparison.R
│
├── 2coverage_analysis/
│   ├── h3_utils.py                 # Shared H3 grid helpers
│   ├── 1cityroad.py                # City → road metrics on H3 grid
│   ├── 1plot_cityroad_maps.R       # H3 choropleths + Spearman correlation figures
│   ├── 1plot_cityroad_analysis.R   # H3 metric distribution violin/histogram panels
│   ├── 2roadsvi.py                 # Road → SVI coverage by road metre
│   ├── 2plot_roadsvi_maps.R        # City-wide SVI gap map
│   ├── 3sviwaste.py                # SVI → waste-positive panoids
│   ├── 3plot_sviwaste_maps.R
│   └── plot_process_zoom_map.R     # Zoomed pipeline schematic (panels + layers)
│
├── 3_cluster_mitigation/
│   ├── 3_hdbscan_waste.py            # HDBSCAN clustering (both arms)
│   ├── 4_mitigation_comparison.py    # Google SVI vs gsvi_selfcollected tables
│   ├── 1_plot_svi_sources_map.R    # SVI imagery by source (Step 1 gpkgs)
│   ├── 2_plot_waste_sources_map.R  # Waste detections by source (Step 1 gpkgs)
│   ├── 3_plot_hdbscan_map.R        # HDBSCAN cluster maps
│   ├── 4_plot_new_obs_stacked_bar.R  # New-obs inside vs new-hotspot bar
│   ├── 5_plot_hotspot_difference_map.R  # Hotspot overlap vs additional area map
│   └── robustness_kde/
│       ├── 1_kde_hotspots.py         # KDE surfaces → hotspot polygons + metrics
│       └── 2_plot_kde_comparison.R   # Two-panel + difference KDE maps
│
├── Figure/                         # All map outputs (PNG)
│   ├── 1prepare_chapter_data/
│   ├── 2coverage_analysis/
│   └── 3_cluster_mitigation/
│       └── robustness_kde/
│
└── *.ipynb                         # Original Jupyter notebooks (legacy)
```

**Processed data** (not in this repo) lives under:

```
/Users/wenlanzhang/Downloads/PhD_UCL/Data/Chapter_waste/
├── 1prepare_chapter_data/          # Harmonised GeoPackages
├── 2coverage_analysis/             # Coverage CSVs & GeoPackages
└── 3_cluster_mitigation/           # HDBSCAN outputs, hotspot gpkgs, thesis_table/
    └── robustness_kde/             # KDE robustness polygons, params, thesis_table/
```

Raw inputs are read-only from `PhD_UCL/Data/Waste/`, `Shp/`, etc.

---

## Workflow overview

```
Raw CSVs & shapefiles
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 1 — Data preparation (1prepare_chapter_data/)               │
│  • Harmonise waste, SVI, boundary, slums → GeoPackages           │
│  • Build local OSM & OSMnx road layers                           │
│  • Compare sources & select road layer for downstream analysis   │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│ Step 2 — Coverage analysis (2coverage_analysis/)                 │
│  city → roads → SVI → waste                                      │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│ 2a. cityroad      │  H3 grid road metrics (city scale)
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 2b. roadsvi       │  Road-metre SVI coverage
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 2c. sviwaste      │  Waste-positive SVI panoids
└───────────────────┘
```

**Coverage hierarchy:** city (boundary) → roads → SVI sampling → waste detections

The local vs OSMnx road comparison lives inside **Step 1** — it supports choosing which cleaned road layer to feed into Step 2, not a separate analysis track.

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
| `Nairobi_boundary_polygon_32737.gpkg` | Study-area boundary | 1 |
| `Nairobi_slum_polygon_32737.gpkg` | Informal settlement polygons | 1,988 |
| `Nairobi_slum_cluster_polygon_32737.gpkg` | Merged touching slum clusters | 101 |

**Arm vocabulary** (used in filenames throughout the pipeline):

| Slug | Meaning |
| --- | --- |
| `gsvi` | Google Street View only — excludes `Faith/` and `ZWL/` |
| `gsvi_selfcollected` | Google + Faith/ + ZWL/ self-collected imagery |

**Cleaning rules:**

- **gsvi arm:** exclude `ZWL/` and `Faith/`; waste dedupe on `lat`, `lon`, `img_name`; SVI dedupe on `panoid`
- **gsvi_selfcollected arm:** no dir filter; waste dedupe on `lat`, `lon`, `img_name`; SVI GSVI rows dedupe on `panoid`, self-collected rows dedupe on `lat`, `lon`, `img_name`
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

Shared logic lives in `road_utils.py` (`clean_road_segments`, `node_road_segments`, `build_cleaned_comparison`).

### 1c. OSMnx roads & comparison

**Script:** `1prepare_chapter_data/2_prepare_osmnx_roads.py` (run after step 1a)

Downloads Nairobi roads via OSMnx (`network_type='all'`), producing:


| File                                       | Processing                                | Segments | Length     |
| ------------------------------------------ | ----------------------------------------- | -------- | ---------- |
| `Nairobi_road_02_osmnx_raw_32737.gpkg`     | Download, project, truncate (no simplify) | ~587,562 | ~14,917 km |
| `Nairobi_road_04_osmnx_cleaned_32737.gpkg` | `simplify_graph` + `clean_road_segments`  | ~181,287 | ~14,917 km |

**Used by all step-2 coverage scripts:** `Nairobi_road_03_local_cleaned_32737.gpkg` (`ROAD_FILES["coverage"]` in `road_utils.py`).


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

### 2b. `2roadsvi.py` — Road → SVI (metre level)

**Unit:** Road metres within local cleaned OSM segments (one row per OSM way segment).

Each SVI panoid is buffered (default **50 m**). For each road segment, nearby buffers are unioned and the line is split into **covered** and **uncovered** parts (`segment ∩ zone` and `segment − zone`). Partially covered segments contribute metre length to both classes — uncovered sub-parts appear as gaps on the map.

```bash
python 2coverage_analysis/2roadsvi.py
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 50
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 50
```

**Sensitivity analysis** (repeat Python + R plotting for other buffer distances):

```bash
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 75
python 2coverage_analysis/2roadsvi.py --svi-buffer-m 100
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 75
Rscript 2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m 100
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m 75
Rscript 2coverage_analysis/plot_process_zoom_map.R --layout=layers --svi-buffer-m 100
```

**Outputs** (tagged by buffer, e.g. `buf50m`):

- `Nairobi_roadsvi_coverage_buf50m.{gpkg,csv}` — covered/uncovered line parts (for maps)
- `Nairobi_roadsvi_segments_buf50m.{gpkg,csv}` — per-segment length breakdown (`covered_length_m`, `uncovered_length_m`, `partially_covered`)
- `Nairobi_roadsvi_summary_buf50m.csv`

**Figure (`2plot_roadsvi_maps.R`):** light grey = all road metres; red = metres outside SVI buffers. Report + hi-res PNGs (`Nairobi_roadsvi_uncovered_buf50m.png`).

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

---

## Step 3 — Cluster analysis & mitigation

Compares two **arms** from Step 1 waste GeoPackages using HDBSCAN and mitigation metrics:

| Arm slug | Definition |
| --- | --- |
| `gsvi` | Google Street View waste detections only |
| `gsvi_selfcollected` | Google + Faith/ + ZWL/ self-collected waste detections |

Both arms use identical HDBSCAN settings on harmonised Step 1 inputs (EPSG:32737).

### Run order

```bash
# Step 1 must be run first (creates gsvi / gsvi_selfcollected gpkgs)
python 1prepare_chapter_data/1_prepare_chapter_data.py

# Source maps (Step 1 gpkgs only — no HDBSCAN required)
Rscript 3_cluster_mitigation/1_plot_svi_sources_map.R
Rscript 3_cluster_mitigation/2_plot_waste_sources_map.R

# Clustering + comparison tables
python 3_cluster_mitigation/3_hdbscan_waste.py
python 3_cluster_mitigation/4_mitigation_comparison.py

# Cluster maps + stacked bar
Rscript 3_cluster_mitigation/3_plot_hdbscan_map.R
Rscript 3_cluster_mitigation/5_plot_hotspot_difference_map.R
Rscript 3_cluster_mitigation/4_plot_new_obs_stacked_bar.R

# KDE robustness (Step 1 gpkgs only — supplementary to HDBSCAN)
python 3_cluster_mitigation/robustness_kde/1_kde_hotspots.py
Rscript 3_cluster_mitigation/robustness_kde/2_plot_kde_comparison.R
```

### 3a. SVI source map

**Script:** `3_cluster_mitigation/1_plot_svi_sources_map.R`

All SVI panoids from `Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg`. Light brown = GSVI; darker brown highlights self-collected panoids.

**Figure:** `Figure/3_cluster_mitigation/SVI_sources_gsvi_selfcollected.png`

### 3b. Waste source map

**Script:** `3_cluster_mitigation/2_plot_waste_sources_map.R`

Waste detections from Step 1 gpkgs, layered over all SVI panoids. Layer order: all SVI → GSVI waste → self-collected waste → urban-poor fill → city boundary.

**Figure:** `Figure/3_cluster_mitigation/Waste_sources_gsvi_selfcollected.png`

### 3c. HDBSCAN clustering

**Script:** `3_cluster_mitigation/3_hdbscan_waste.py`

| Parameter | Value |
| --- | --- |
| `min_cluster_size` | 25 |
| `min_samples` | 6 |
| Coordinate space | EPSG:32737 (projected easting/northing) |

**Outputs (processed data):**

- `Nairobi_waste_hdbscan_gsvi_32737.gpkg`, `Nairobi_waste_hdbscan_summary_gsvi.csv`
- `Nairobi_waste_hdbscan_gsvi_selfcollected_32737.gpkg`, `Nairobi_waste_hdbscan_summary_gsvi_selfcollected.csv`
- `Nairobi_waste_hdbscan_summary_comparison.csv`

**Script:** `3_cluster_mitigation/3_plot_hdbscan_map.R`

**Figures:**

- `Waste_HDBSCAN_gsvi.png` — gsvi arm clusters
- `Waste_HDBSCAN_gsvi_selfcollected.png` — gsvi_selfcollected arm clusters
- `Waste_HDBSCAN_comparison.png` — side-by-side (A/B) comparison

Map styling: chocolate-brown HDBSCAN clusters, grey noise points, black city boundary, repelled cluster ID labels, north arrow, scale bar, inside bottom-right legend.

### 3d. Mitigation comparison

**Script:** `3_cluster_mitigation/4_mitigation_comparison.py`

Compares **gsvi** vs **gsvi_selfcollected**. Hotspot area = sum of per-cluster convex-hull polygon areas (km², EPSG:32737).

**Outputs:**

- `thesis_table/Nairobi_mitigation_comparison_table.csv`
- `thesis_table/Nairobi_mitigation_new_observations_table.csv`
- `Nairobi_waste_hotspot_polygons_gsvi_32737.gpkg`
- `Nairobi_waste_hotspot_polygons_gsvi_selfcollected_32737.gpkg`

### 3e. Hotspot area difference map

**Script:** `3_cluster_mitigation/5_plot_hotspot_difference_map.R`

Requires hotspot polygon GeoPackages from `4_mitigation_comparison.py`. Unions all cluster convex hulls per arm, then maps:

- **Light grey-brown points** — all SVI panoids (`#D4CCC2`, bottom layer)
- **Light fill** — overlapping hotspot footprint (shared between gsvi and gsvi_selfcollected)
- **Dark fill** — additional footprint from adding self-collected imagery
- **Medium fill** (if present) — GSVI-only footprint lost when clusters are re-fit
- **Light brown points** — GSVI waste detections (`#C9A27F`, matches waste source map)
- **Dark brown points** — self-collected waste detections (`#6B4226`)

Legend shows km² per zone (union-based; matches the spatial +5.4 km² net change in the comparison table).

```bash
Rscript 3_cluster_mitigation/5_plot_hotspot_difference_map.R
```

**Figure:** `Figure/3_cluster_mitigation/Hotspot_area_difference_gsvi_selfcollected.png`

### 3f. Stacked bar

**Script:** `3_cluster_mitigation/4_plot_new_obs_stacked_bar.R`

Reads `thesis_table/Nairobi_mitigation_new_observations_table.csv` — one horizontal stacked bar: inside existing hotspots vs forming new hotspots.

**Figure:** `Figure/3_cluster_mitigation/Mitigation_new_obs_stacked_bar.png`

### 3g. KDE robustness (supplementary)

**Purpose:** Robustness check only — does the neighbourhood-scale hotspot pattern stay broadly similar when switching from discrete HDBSCAN clusters to a smooth KDE surface and adding supplementary self-collected observations? HDBSCAN remains the primary method; KDE does not replace it.

**Scripts:**

- `3_cluster_mitigation/robustness_kde/1_kde_hotspots.py` — KDE surfaces, shared threshold, union hotspot polygons, overlap metrics
- `3_cluster_mitigation/robustness_kde/2_plot_kde_comparison.R` — two-panel comparison + difference map

**Config constants** (top of `1_kde_hotspots.py`):

| Constant | Default | Meaning |
| --- | --- | --- |
| Bandwidth | `KDE_BANDWIDTH_M = 400` | Fixed isotropic Gaussian sd (m); Scott on city-wide points over-smooths (~1.7 km) — same bandwidth for both arms |
| `GRID_CELL_M` | 150 | Regular grid cell size (m, EPSG:32737) |
| `KDE_HOTSPOT_PERCENTILE` | 2 | Top N% of gsvi density values → one shared absolute threshold for both arms (tune after inspecting test maps) |

**Run order** (after Step 1 only):

```bash
python 3_cluster_mitigation/robustness_kde/1_kde_hotspots.py
Rscript 3_cluster_mitigation/robustness_kde/2_plot_kde_comparison.R
```

**Outputs (processed data):**

```
3_cluster_mitigation/robustness_kde/
├── thesis_table/Nairobi_kde_robustness_comparison.csv
├── Nairobi_kde_hotspot_polygons_gsvi_32737.gpkg
├── Nairobi_kde_hotspot_polygons_gsvi_selfcollected_32737.gpkg
└── Nairobi_kde_params.csv
```

**Figures:**

- `Figure/3_cluster_mitigation/robustness_kde/KDE_hotspot_gsvi.png`
- `Figure/3_cluster_mitigation/robustness_kde/KDE_hotspot_gsvi_selfcollected.png`
- `Figure/3_cluster_mitigation/robustness_kde/KDE_hotspot_comparison.png` — side-by-side (A/B)
- `Figure/3_cluster_mitigation/robustness_kde/KDE_hotspot_difference.png` — overlap vs additional area

**What to report in thesis** (three bullets only):

- Main hotspot locations remain similar or shift when self-collected imagery is added
- Hotspot footprint expands or contracts (union polygon area change)
- Supplementary observations reinforce existing density peaks vs create new ones (difference map + waste point overlay)

**What not to do:** no parameter-sweep narrative, no algorithm horse-race; KDE is supplementary to HDBSCAN.

---

## Thesis summary tables

Each coverage Python script writes a publication-style table (Variable / Value / Unit) to:

```
Chapter_waste/2coverage_analysis/thesis_table/
├── table_1_cityroad_h3_res8_buf50m.csv
├── table_2_roadsvi_buf50m.csv
└── table_3_sviwaste.csv

Chapter_waste/3_cluster_mitigation/thesis_table/
├── Nairobi_mitigation_comparison_table.csv
└── Nairobi_mitigation_new_observations_table.csv

Chapter_waste/3_cluster_mitigation/robustness_kde/thesis_table/
└── Nairobi_kde_robustness_comparison.csv
```

Tables are generated alongside the analysis outputs (not a separate script), so re-running a step refreshes its table automatically. Formatting uses rounded values and comma-separated integers.

---

## Figures (R)

All maps use `R/map_theme.R`:

- North arrow (top-right)
- Scale bar (bottom-left)
- Legend (bottom-right, inside panel)
- EPSG:32737 axis labels


| Script                                                     | Figures                                                                 |
| ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| `1prepare_chapter_data/plot_maps.R`                        | Waste, SVI, boundary, slum preview maps                                 |
| `1prepare_chapter_data/plot_road_figures.R`                | Five numbered road maps (01–05) + hi-res comparison                     |
| `1prepare_chapter_data/plot_road_type_composition.R`       | Local road type pie chart                                               |
| `1prepare_chapter_data/plot_road_type_composition_osmnx.R` | OSMnx road type pie chart + map                                         |
| `1prepare_chapter_data/plot_road_network_comparison.R`     | Local vs OSMnx summary bar charts                                       |
| `2coverage_analysis/1plot_cityroad_maps.R`                 | 4 H3 choropleths + Spearman heatmap + scatter matrix                    |
| `2coverage_analysis/1plot_cityroad_analysis.R`             | H3 metric distribution panels (violin + histogram)                        |
| `2coverage_analysis/plot_process_zoom_map.R`               | Zoomed pipeline schematic: 4-panel + single-hex layers map              |
| `2coverage_analysis/2plot_roadsvi_maps.R`                  | Road SVI gap map (+ `_hires` version; repeat per buffer tag)              |
| `2coverage_analysis/3plot_sviwaste_maps.R`                 | SVI waste-positive map (+ `_hires` version)                             |


Hi-res exports (`*_hires.png`) are 12,000 × 12,000 px for zooming; standard PNGs (~3,000 px) are for reports.

---

## Environment


| Tool                                             | Environment                  |
| ------------------------------------------------ | ---------------------------- |
| Python (geopandas, h3, osmnx, networkx, shapely, hdbscan) | `conda activate geo_env_LLM` |
| R (sf, ggplot2, ggspatial, ggpattern, dplyr, scales, patchwork) | system R (`Rscript`)         |


---

## Legacy files

- `SVI_PPP_Stats_USE.ipynb`, `SVI_distance_use.ipynb` — earlier notebook analyses; kept for reference

The original root-level `data.py` exploratory script was superseded by `1_prepare_chapter_data.py` and has been removed.

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
```


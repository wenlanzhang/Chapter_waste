# Optional: socio-economic (admin-unit) analysis

**Not part of the main chapter pipeline / Snakemake `all`.**

Joins GSVI panoids from Step 2c to Nairobi admin-5 socio-economic polygons
(`Waste/SE/cleaned_Nairobi_2019.csv`, same source as
`SVI_Waste/Code/SVI/SVI_Social_economic.ipynb`) and reports waste–SE associations
at the admin-unit level.

Primary outcome: **waste-positive rate** among GSVI panoids in each unit
(`waste_positive_panoids / panoid_count`), which adjusts for SVI sampling effort
(unlike raw waste counts).

## Run

```bash
conda activate geo_env_LLM
cd /Users/wenlanzhang/PycharmProjects/Chapter_waste

python 99_optional_SE_analysis/1_admin_se_waste_join.py
Rscript 99_optional_SE_analysis/2_plot_se_maps.R
Rscript 99_optional_SE_analysis/3_plot_se_correlations.R
```

Optional: also write a 2023 SE join (same panoids, different SE table):

```bash
python 99_optional_SE_analysis/1_admin_se_waste_join.py --year 2023
```

## Outputs

Processed (under `Data/Chapter_waste/99_optional_SE_analysis/`):

- `Nairobi_admin_se_waste_2019.gpkg` / `.csv` — admin polygons + waste metrics + SE
- `thesis_table/se_waste_correlations_2019.csv` — Pearson r / p vs waste-positive rate
- `thesis_table/se_waste_summary_2019.csv` — unit counts and outcome descriptives
- `thesis_table/se_moran_2019.csv` — global Moran’s I on waste-positive rate (if computable)

Figures (`Figure/99_optional_SE_analysis/`):

- choropleths (waste-positive rate, GRDI, population density)
- correlation bar chart + selected scatter panels

ROAD_CLEANED = PREP / "Nairobi_road_03_local_cleaned_32737.gpkg"
BOUNDARY = PREP / "Nairobi_boundary_polygon_32737.gpkg"
THESIS = COV / "thesis_table"


# Step 2 runs the GSVI arm only. The scripts accept --arm gsvi_selfcollected
# for ad-hoc runs, but nothing in the pipeline depends on the SC arm here.
STEP2_ARM = "gsvi"
ZOOM_BLOCK_SIZES = (3, 4)  # n x n cell blocks for the process schematic


def sviwaste_gpkg(arm):
    return COV / ARMS[arm].filename("3_Nairobi_sviwaste_points")


COVERAGE_DATA = [
    COV / "1_Nairobi_cityroad_grid100m_32737.gpkg",
    THESIS / f"table_1_cityroad_{ROAD_TAG}.csv",
    sviwaste_gpkg(STEP2_ARM),
    COV / f"2_Nairobi_roadsvi_coverage_buf{SVI_BUF}m_{STEP2_ARM}.gpkg",
    COV / f"4_Nairobi_roadwaste_coverage_buf{SVI_BUF}m_{STEP2_ARM}.gpkg",
    THESIS / "table_3_sviwaste.csv",
    THESIS / f"table_2_roadsvi_buf{SVI_BUF}m.csv",
    THESIS / f"table_4_roadwaste_buf{SVI_BUF}m.csv",
    COV / "5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg",
    THESIS / "table_5_gridsvi.csv",
    THESIS / "table_0_coverage_headline.csv",
]

COVERAGE_FIGS = (
    [
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_access_{ROAD_TAG}.png",
        FIG / "2coverage_analysis" / "1_Nairobi_cityroad_density_grid100m.png",
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_distance_{ROAD_TAG}.png",
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_analysis_{ROAD_TAG}.png",
        FIG / "2coverage_analysis" / "3_Nairobi_sviwaste_positive.png",
        FIG / "2coverage_analysis" / f"2_Nairobi_roadsvi_uncovered_buf{SVI_BUF}m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_observed_grid100m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_distance_grid100m.png",
        FIG / "2coverage_analysis" / f"2_Nairobi_roadsvi_analysis_grid100m_buf{SVI_BUF}m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_correlation_spearman_grid100m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_correlation_spearman_grid100m_scatter.png",
    ]
    + [
        FIG / "2coverage_analysis" / f"6_Nairobi_process_zoom_grid100m_{n}x{n}_svi{SVI_BUF}_{k}.png"
        for n in ZOOM_BLOCK_SIZES
        for k in ("panels", "layers", "layers_inset")
    ]
)


# --- 2a. city -> road on the 100 m grid (arm independent) --------------------
CITYROAD_GRID = COV / "1_Nairobi_cityroad_grid100m_32737.gpkg"


rule cityroad:
    input:
        ROAD_CLEANED,
        lambda wc: str(active_grid_gpkg()),
    output:
        CITYROAD_GRID,
        COV / f"1_Nairobi_cityroad_summary_{ROAD_TAG}.csv",
        THESIS / f"table_1_cityroad_{ROAD_TAG}.csv",
    params:
        road_buffer_m=ROAD_BUF,
    shell:
        "python {REPO_ROOT}/2coverage_analysis/1cityroad.py --road-buffer-m {params.road_buffer_m}"


rule plot_cityroad_maps:
    input:
        CITYROAD_GRID,
        COV / f"1_Nairobi_cityroad_summary_{ROAD_TAG}.csv",
        BOUNDARY,
    output:
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_access_{ROAD_TAG}.png",
        FIG / "2coverage_analysis" / "1_Nairobi_cityroad_density_grid100m.png",
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_distance_{ROAD_TAG}.png",
    params:
        road_buffer_m=ROAD_BUF,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/1plot_cityroad_maps.R --road-buffer-m={params.road_buffer_m}"


rule plot_cityroad_analysis:
    input:
        CITYROAD_GRID,
        COV / f"1_Nairobi_cityroad_summary_{ROAD_TAG}.csv",
    output:
        FIG / "2coverage_analysis" / f"1_Nairobi_cityroad_analysis_{ROAD_TAG}.png",
    params:
        road_buffer_m=ROAD_BUF,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/1plot_cityroad_analysis.R --road-buffer-m={params.road_buffer_m}"


# --- 2b. road -> SVI, per arm ------------------------------------------------
rule roadsvi:
    input:
        ROAD_CLEANED,
        BOUNDARY,
        lambda wc: ARMS[wc.arm].svi_point_gpkg(),
        lambda wc: str(active_grid_gpkg()),
    output:
        COV / "2_Nairobi_roadsvi_coverage_buf{buffer}m_{arm}.gpkg",
        COV / "2_Nairobi_roadsvi_grid100m_buf{buffer}m_{arm}.gpkg",
        COV / "2_Nairobi_roadsvi_summary_buf{buffer}m_{arm}.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/2roadsvi.py --svi-buffer-m {wildcards.buffer} --arm {wildcards.arm}"


rule roadsvi_table:
    input:
        COV / "2_Nairobi_roadsvi_coverage_buf{buffer}m_gsvi.gpkg",
    output:
        THESIS / "table_2_roadsvi_buf{buffer}m.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/2roadsvi.py --svi-buffer-m {wildcards.buffer} --table-only"


rule plot_roadsvi_maps:
    input:
        COV / "2_Nairobi_roadsvi_coverage_buf{buffer}m_gsvi.gpkg",
        COV / "2_Nairobi_roadsvi_grid100m_buf{buffer}m_gsvi.gpkg",
        COV / "2_Nairobi_roadsvi_summary_buf{buffer}m_gsvi.csv",
        BOUNDARY,
    output:
        FIG / "2coverage_analysis" / "2_Nairobi_roadsvi_uncovered_buf{buffer}m.png",
        FIG / "2coverage_analysis" / "2_Nairobi_roadsvi_analysis_grid100m_buf{buffer}m.png",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m={wildcards.buffer}"


# --- 2c. SVI -> waste, per arm -----------------------------------------------
rule sviwaste:
    input:
        lambda wc: ARMS[wc.arm].svi_point_gpkg(),
        lambda wc: ARMS[wc.arm].waste_gpkg(),
    output:
        COV / "3_Nairobi_sviwaste_points_{arm}_32737.gpkg",
        COV / "3_Nairobi_sviwaste_summary_{arm}.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/3sviwaste.py --arm {wildcards.arm}"


rule sviwaste_table:
    input:
        COV / "3_Nairobi_sviwaste_summary_gsvi.csv",
    output:
        THESIS / "table_3_sviwaste.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/3sviwaste.py"


rule plot_sviwaste_maps:
    input:
        sviwaste_gpkg("gsvi"),
        BOUNDARY,
    output:
        FIG / "2coverage_analysis" / "3_Nairobi_sviwaste_positive.png",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/3plot_sviwaste_maps.R"


# --- 2d. road -> waste-positive points, per arm ------------------------------
rule roadwaste:
    input:
        ROAD_CLEANED,
        COV / "3_Nairobi_sviwaste_points_{arm}_32737.gpkg",
        COV / "2_Nairobi_roadsvi_summary_buf{buffer}m_{arm}.csv",
    output:
        COV / "4_Nairobi_roadwaste_coverage_buf{buffer}m_{arm}.gpkg",
        COV / "4_Nairobi_roadwaste_summary_buf{buffer}m_{arm}.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/4roadwaste.py --buffer-m {wildcards.buffer} --arm {wildcards.arm}"


rule roadwaste_table:
    input:
        COV / "4_Nairobi_roadwaste_coverage_buf{buffer}m_gsvi.gpkg",
    output:
        THESIS / "table_4_roadwaste_buf{buffer}m.csv",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/4roadwaste.py --buffer-m {wildcards.buffer} --table-only"


# --- 2e. GSVI -> analytical grid + headline table ---------------------------
rule gridsvi:
    input:
        lambda wc: str(active_grid_gpkg()),
        ARMS["gsvi"].svi_image_gpkg(),
        ARMS["gsvi"].svi_point_gpkg(),
        CITYROAD_GRID,
        COV / f"1_Nairobi_cityroad_summary_{ROAD_TAG}.csv",
        COV / f"2_Nairobi_roadsvi_summary_buf{SVI_BUF}m_gsvi.csv",
        COV / f"2_Nairobi_roadsvi_grid100m_buf{SVI_BUF}m_gsvi.gpkg",
    output:
        COV / "5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg",
        COV / "5_Nairobi_gridsvi_summary_gsvi.csv",
        COV / "5_Nairobi_gridsvi_road_crosstab_gsvi.csv",
        THESIS / "table_5_gridsvi.csv",
        THESIS / "table_0_coverage_headline.csv",
    params:
        road_buffer_m=ROAD_BUF,
        svi_buffer_m=SVI_BUF,
    shell:
        "python {REPO_ROOT}/2coverage_analysis/5_gridsvi.py --road-buffer-m {params.road_buffer_m} --svi-buffer-m {params.svi_buffer_m}"


rule plot_gridsvi_maps:
    input:
        COV / "5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg",
        COV / "5_Nairobi_gridsvi_summary_gsvi.csv",
        BOUNDARY,
    output:
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_observed_grid100m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_distance_grid100m.png",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/5plot_gridsvi_maps.R"


rule plot_gridsvi_analysis:
    input:
        COV / "5_Nairobi_gridsvi_grid100m_gsvi_32737.gpkg",
        COV / "5_Nairobi_gridsvi_summary_gsvi.csv",
    output:
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_correlation_spearman_grid100m.png",
        FIG / "2coverage_analysis" / "5_Nairobi_gridsvi_correlation_spearman_grid100m_scatter.png",
        COV / "5_Nairobi_gridsvi_correlation_spearman_gsvi.csv",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/5plot_gridsvi_analysis.R"


# --- schematic: n x n block of 100 m cells (GSVI arm) ------------------------
rule plot_process_zoom:
    input:
        CITYROAD_GRID,
        ROAD_CLEANED,
        BOUNDARY,
        ARMS["gsvi"].svi_point_gpkg(),
        ARMS["gsvi"].waste_gpkg(),
        sviwaste_gpkg("gsvi"),
    output:
        [FIG / "2coverage_analysis" / f"6_Nairobi_process_zoom_grid100m_{{n}}x{{n}}_svi{SVI_BUF}_{k}.png" for k in ("panels", "layers", "layers_inset")],
    params:
        svi_buffer_m=SVI_BUF,
    wildcard_constraints:
        n="|".join(str(n) for n in ZOOM_BLOCK_SIZES),
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/6plot_process_zoom_map.R --svi-buffer-m={params.svi_buffer_m} --block-cols={wildcards.n} --block-rows={wildcards.n}"

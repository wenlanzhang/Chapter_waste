COVERAGE_DATA = [
    COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
    COV / "Nairobi_sviwaste_points.gpkg",
] + [COV / f"Nairobi_roadsvi_coverage_buf{b}m.gpkg" for b in SVI_BUFFERS] + [
    COV / f"Nairobi_roadwaste_coverage_buf{b}m.gpkg" for b in SVI_BUFFERS
]

COVERAGE_FIGS = [
    FIG / "2coverage_analysis" / f"Nairobi_cityroad_density_{CITYROAD_TAG}.png",
    FIG / "2coverage_analysis" / f"Nairobi_cityroad_analysis_{CITYROAD_TAG}.png",
    FIG / "2coverage_analysis" / "Nairobi_sviwaste_positive.png",
] + [
    roadsvi_figdir(b) / f"Nairobi_roadsvi_uncovered_buf{b}m.png"
    for b in SVI_BUFFERS
] + [
    roadsvi_figdir(b)
    / f"Nairobi_process_zoom_h3_res{H3_RES}_buf{ROAD_BUF}m_svi{b}_layers.png"
    for b in SVI_BUFFERS
]


rule cityroad:
    input:
        PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
    params:
        h3_res=H3_RES,
        road_buffer_m=ROAD_BUF,
    shell:
        "python {REPO_ROOT}/2coverage_analysis/1cityroad.py --h3-res {params.h3_res} --road-buffer-m {params.road_buffer_m}"


rule plot_cityroad_maps:
    input:
        COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / f"Nairobi_cityroad_density_{CITYROAD_TAG}.png",
    params:
        h3_res=H3_RES,
        road_buffer_m=ROAD_BUF,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/1plot_cityroad_maps.R --h3-res={params.h3_res} --road-buffer-m={params.road_buffer_m}"


rule plot_cityroad_analysis:
    input:
        COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
    output:
        FIG / "2coverage_analysis" / f"Nairobi_cityroad_analysis_{CITYROAD_TAG}.png",
    params:
        h3_res=H3_RES,
        road_buffer_m=ROAD_BUF,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/1plot_cityroad_analysis.R --h3-res={params.h3_res} --road-buffer-m={params.road_buffer_m}"


rule roadsvi:
    input:
        PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
        PREP / "Nairobi_SVI_point_gsvi_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        COV / "Nairobi_roadsvi_coverage_buf{buffer}m.gpkg",
    params:
        h3_res=H3_RES,
    shell:
        "python {REPO_ROOT}/2coverage_analysis/2roadsvi.py --svi-buffer-m {wildcards.buffer} --h3-res {params.h3_res}"


rule plot_roadsvi_maps:
    input:
        COV / "Nairobi_roadsvi_coverage_buf50m.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / "Nairobi_roadsvi_uncovered_buf50m.png",
    params:
        h3_res=H3_RES,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m=50 --h3-res={params.h3_res}"


rule plot_roadsvi_maps_buffer:
    input:
        COV / "Nairobi_roadsvi_coverage_buf{buffer}m.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / "buffer" / "Nairobi_roadsvi_uncovered_buf{buffer}m.png",
    params:
        h3_res=H3_RES,
    wildcard_constraints:
        buffer="75|100",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/2plot_roadsvi_maps.R --svi-buffer-m={wildcards.buffer} --h3-res={params.h3_res}"


rule sviwaste:
    input:
        PREP / "Nairobi_SVI_point_gsvi_32737.gpkg",
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    output:
        COV / "Nairobi_sviwaste_points.gpkg",
    shell:
        "python {REPO_ROOT}/2coverage_analysis/3sviwaste.py"


rule plot_sviwaste_maps:
    input:
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / "Nairobi_sviwaste_positive.png",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/3plot_sviwaste_maps.R"


rule roadwaste:
    input:
        PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
        COV / "Nairobi_sviwaste_points.gpkg",
    output:
        COV / "Nairobi_roadwaste_coverage_buf{buffer}m.gpkg",
    params:
        h3_res=H3_RES,
    shell:
        "python {REPO_ROOT}/2coverage_analysis/4roadwaste.py --buffer-m {wildcards.buffer} --h3-res {params.h3_res}"


rule plot_process_zoom:
    input:
        COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
        COV / "Nairobi_roadsvi_coverage_buf50m.gpkg",
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / f"Nairobi_process_zoom_h3_res{H3_RES}_buf{ROAD_BUF}m_svi50_layers.png",
    params:
        h3_res=H3_RES,
        road_buffer_m=ROAD_BUF,
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/plot_process_zoom_map.R --layout=layers --h3-res={params.h3_res} --road-buffer-m={params.road_buffer_m} --svi-buffer-m=50"


rule plot_process_zoom_buffer:
    input:
        COV / f"Nairobi_cityroad_grid_{CITYROAD_TAG}.gpkg",
        COV / "Nairobi_roadsvi_coverage_buf{buffer}m.gpkg",
        COV / "Nairobi_sviwaste_points.gpkg",
        PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
    output:
        FIG / "2coverage_analysis" / "buffer" / f"Nairobi_process_zoom_h3_res{H3_RES}_buf{ROAD_BUF}m_svi{{buffer}}_layers.png",
    params:
        h3_res=H3_RES,
        road_buffer_m=ROAD_BUF,
    wildcard_constraints:
        buffer="75|100",
    shell:
        "Rscript {REPO_ROOT}/2coverage_analysis/plot_process_zoom_map.R --layout=layers --h3-res={params.h3_res} --road-buffer-m={params.road_buffer_m} --svi-buffer-m={wildcards.buffer}"

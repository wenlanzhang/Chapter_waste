PREPARE_DATA = [
    PREP / "Nairobi_boundary_polygon_32737.gpkg",
    PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
    PREP / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    PREP / "Nairobi_SVI_point_gsvi_32737.gpkg",
    PREP / "Nairobi_SVI_point_gsvi_selfcollected_32737.gpkg",
    PREP / "Nairobi_SVI_image_gsvi_32737.gpkg",
    PREP / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
    PREP / "Nairobi_slum_polygon_32737.gpkg",
    PREP / "Nairobi_grid_100m_32737.gpkg",
    PREP / "Nairobi_validation_grid_32737.gpkg",
    PREP / "Nairobi_road_01_local_raw_32737.gpkg",
    PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
    PREP / "Nairobi_road_line_32737.gpkg",
]

PREPARE_FIGS = [
    FIG / "1prepare_chapter_data" / "Nairobi_Waste_point_gsvi_32737.png",
    FIG / "1prepare_chapter_data" / "Nairobi_road_type_composition.png",
]

OSMNX_DATA = [
    PREP / "Nairobi_road_02_osmnx_raw_32737.gpkg",
    PREP / "Nairobi_road_04_osmnx_cleaned_32737.gpkg",
    PREP / "Nairobi_road_05_cleaned_comparison_32737.gpkg",
]

OSMNX_FIGS = [
    FIG / "1prepare_chapter_data" / "Nairobi_road_05_cleaned_comparison_32737.png",
    FIG / "1prepare_chapter_data" / "Nairobi_road_type_composition_OSMnx.png",
    FIG / "1prepare_chapter_data" / "Nairobi_road_comparison_summary.png",
]


rule prepare_chapter_data:
    output:
        PREPARE_DATA,
    shell:
        "python {REPO_ROOT}/1prepare_chapter_data/1_prepare_chapter_data.py"


rule plot_prepare_maps:
    input:
        PREP / "Nairobi_Waste_point_gsvi_32737.gpkg",
        PREP / "Nairobi_SVI_point_gsvi_32737.gpkg",
        PREP / "Nairobi_boundary_polygon_32737.gpkg",
        PREP / "Nairobi_slum_polygon_32737.gpkg",
    output:
        FIG / "1prepare_chapter_data" / "Nairobi_Waste_point_gsvi_32737.png",
    shell:
        "Rscript {REPO_ROOT}/1prepare_chapter_data/plot_maps.R"


rule plot_road_type_composition:
    input:
        PREP / "Nairobi_road_line_32737.gpkg",
    output:
        FIG / "1prepare_chapter_data" / "Nairobi_road_type_composition.png",
    shell:
        "Rscript {REPO_ROOT}/1prepare_chapter_data/plot_road_type_composition.R"


if INCLUDE_OSMNX:

    rule prepare_osmnx_roads:
        input:
            PREP / "Nairobi_boundary_polygon_32737.gpkg",
            PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
            PREP / "Nairobi_SVI_point_gsvi_32737.gpkg",
        output:
            OSMNX_DATA,
        shell:
            "python {REPO_ROOT}/1prepare_chapter_data/2_prepare_osmnx_roads.py"

    rule plot_road_figures:
        input:
            PREP / "Nairobi_road_01_local_raw_32737.gpkg",
            PREP / "Nairobi_road_02_osmnx_raw_32737.gpkg",
            PREP / "Nairobi_road_03_local_cleaned_32737.gpkg",
            PREP / "Nairobi_road_04_osmnx_cleaned_32737.gpkg",
            PREP / "Nairobi_road_05_cleaned_comparison_32737.gpkg",
        output:
            FIG / "1prepare_chapter_data" / "Nairobi_road_05_cleaned_comparison_32737.png",
        shell:
            "Rscript {REPO_ROOT}/1prepare_chapter_data/plot_road_figures.R"

    rule plot_road_type_composition_osmnx:
        input:
            PREP / "Nairobi_road_04_osmnx_cleaned_32737.gpkg",
        output:
            FIG / "1prepare_chapter_data" / "Nairobi_road_type_composition_OSMnx.png",
        shell:
            "Rscript {REPO_ROOT}/1prepare_chapter_data/plot_road_type_composition_osmnx.R"

    rule plot_road_network_comparison:
        input:
            PREP / "Nairobi_road_05_cleaned_comparison_32737.gpkg",
        output:
            FIG / "1prepare_chapter_data" / "Nairobi_road_comparison_summary.png",
        shell:
            "Rscript {REPO_ROOT}/1prepare_chapter_data/plot_road_network_comparison.R"

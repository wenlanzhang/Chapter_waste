"""
Sensitivity check — full IDEAMaps pipeline vs raw cell waste/SVI ratio only.

Same Nairobi grid, same Jenks break points, same GSVI vs G+Self arms.
Raw arm skips Empirical Bayes smoothing and spatial fill (no spillover from
neighbouring cells or city-wide EB retuning).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from ideamaps_grid_pipeline import (
    attach_cell_keys,
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)

from output_paths import GRID_GPKG, INPUT_DIR, MITIGATION_DIR

VALIDATION_GRID_GPKG = INPUT_DIR / "Nairobi_validation_grid_32737.gpkg"

ARMS = {
    "gsvi": {
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_32737.gpkg",
    },
    "gsvi_selfcollected": {
        "svi_gpkg": INPUT_DIR / "Nairobi_SVI_image_gsvi_selfcollected_32737.gpkg",
        "waste_gpkg": INPUT_DIR / "Nairobi_Waste_point_gsvi_selfcollected_32737.gpkg",
    },
}
SELF_SOURCES = ("Faith", "ZWL")


def metrics(df: pd.DataFrame, sev_col: str, bin_col: str) -> dict:
    n = len(df)
    sev = float((df[sev_col] == df["validation_result"]).mean()) if n else np.nan
    bin_acc = float((df[bin_col] == df["is_waste"]).mean()) if n else np.nan
    return {"n_cells": n, "severity_accuracy": round(sev, 4), "binary_accuracy": round(bin_acc, 4)}


def run_pipeline(raw: bool) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    grid = gpd.read_file(GRID_GPKG)
    breaks = load_gsvi_submission_jenks_breaks()
    kwargs = dict(jenks_breaks=breaks, raw_ratio_only=raw)
    gsvi = attach_cell_keys(
        run_ideamaps_grid_pipeline(grid, ARMS["gsvi"]["svi_gpkg"], ARMS["gsvi"]["waste_gpkg"], **kwargs)
    )
    gsc = attach_cell_keys(
        run_ideamaps_grid_pipeline(
            grid,
            ARMS["gsvi_selfcollected"]["svi_gpkg"],
            ARMS["gsvi_selfcollected"]["waste_gpkg"],
            **kwargs,
        )
    )
    return gsvi, gsc


def build_validation_df(gsvi: gpd.GeoDataFrame, gsc: gpd.GeoDataFrame, has_self: set[int]) -> pd.DataFrame:
    val = attach_cell_keys(gpd.read_file(VALIDATION_GRID_GPKG)).drop(columns="geometry")
    df = val.merge(
        gsvi[["cell_id", "lat_r", "lon_r", "result"]].rename(columns={"result": "gsvi_result"}),
        on=["cell_id", "lat_r", "lon_r"],
    ).merge(
        gsc[["cell_id", "lat_r", "lon_r", "result"]].rename(columns={"result": "gsc_result"}),
        on=["cell_id", "lat_r", "lon_r"],
    )
    df["has_self_svi"] = df["cell_id"].isin(has_self)
    df["gsvi_pred_is_waste"] = (df["gsvi_result"] > 0).astype(np.uint8)
    df["gsc_pred_is_waste"] = (df["gsc_result"] > 0).astype(np.uint8)
    df["pred_changed"] = df["gsvi_result"] != df["gsc_result"]
    return df


def comparison_rows(df: pd.DataFrame, pipeline: str) -> list[dict]:
    subsets = [
        ("All validated cells", df),
        ("Self-collected SVI overlap", df[df["has_self_svi"]]),
        ("Prediction changed (G vs G+Self)", df[df["pred_changed"]]),
    ]
    rows = []
    for subset_name, sub in subsets:
        for pred_name, sev_col, bin_col in [
            ("GSVI", "gsvi_result", "gsvi_pred_is_waste"),
            ("G+Self", "gsc_result", "gsc_pred_is_waste"),
        ]:
            m = metrics(sub, sev_col, bin_col)
            rows.append(
                {
                    "pipeline": pipeline,
                    "subset": subset_name,
                    "predictor": pred_name,
                    **m,
                }
            )
    return rows


def spillover_stats(df: pd.DataFrame) -> dict:
    gsvi_ok = df["gsvi_result"] == df["validation_result"]
    gsc_ok = df["gsc_result"] == df["validation_result"]
    improved = int((~gsvi_ok & gsc_ok).sum())
    worsened = int((gsvi_ok & ~gsc_ok).sum())
    changed = int(df["pred_changed"].sum())
    changed_no_self = int((df["pred_changed"] & ~df["has_self_svi"]).sum())
    return {
        "cells_class_changed": changed,
        "changed_without_self_svi": changed_no_self,
        "improved": improved,
        "worsened": worsened,
        "net_cells": improved - worsened,
    }


def main() -> None:
    MITIGATION_DIR.mkdir(parents=True, exist_ok=True)
    grid = gpd.read_file(GRID_GPKG)
    svi_self = gpd.read_file(ARMS["gsvi_selfcollected"]["svi_gpkg"])
    svi_self = svi_self[svi_self["source"].isin(SELF_SOURCES)]
    has_self = set(
        gpd.sjoin(svi_self, grid[["cell_id", "geometry"]], how="inner", predicate="within")[
            "cell_id"
        ].astype(int)
    )

    rows = []
    spill_rows = []
    for label, raw in [("Full IDEAMaps (EB + spatial fill)", False), ("Raw ratio only", True)]:
        gsvi, gsc = run_pipeline(raw=raw)
        df = build_validation_df(gsvi, gsc, has_self)
        rows.extend(comparison_rows(df, label))
        spill_rows.append({"pipeline": label, **spillover_stats(df)})

    comparison = pd.DataFrame(rows)
    spill = pd.DataFrame(spill_rows)

    out_cmp = MITIGATION_DIR / "Nairobi_validation_mitigation_sensitivity_comparison.csv"
    comparison.to_csv(out_cmp, index=False)

    print("Accuracy comparison:")
    print(comparison.to_string(index=False))
    print()
    print("Spillover (console only — why city-wide accuracy can move without local new data):")
    print(spill.to_string(index=False))
    print()
    print(f"Wrote {out_cmp}")


if __name__ == "__main__":
    main()

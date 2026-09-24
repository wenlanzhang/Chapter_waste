#!/usr/bin/env python3
"""Step 6.3 — the 100 m indicator rebuilt with self-collected imagery.

Step 4's finding is that most of the published surface is estimated rather than
measured: only a third of cells hold direct evidence, and two thirds of the
represented surface is interpolated. The obvious response is "collect more
imagery". This script measures how much that actually helps.

The same IDEAMaps pipeline (lib/ideamaps.py, same fixed Jenks break points, same
grid) is run twice — GSVI alone, then GSVI + self-collected — and the two
surfaces are compared cell by cell. Two effects are separated:

  coverage  cells that gain direct evidence, so provenance moves
            Interpolated support / Unsupported -> Direct observation
  value     cells that were already observed but pick up extra images and extra
            waste detections, so their ratio and possibly their class moves

The second effect propagates: changing an observed cell's ratio changes what the
spatial fill hands to its unobserved neighbours, so class changes are not
confined to cells that received imagery.

Outputs (Data/Chapter_waste/6_selfcollected/3_indicator/):
  1_Nairobi_sc_indicator_grid100m_32737.gpkg   both arms per cell + change flags
  1_sc_indicator_provenance.csv                provenance, before and after
  1_sc_indicator_class_change.csv              the 3x3 class transition table
  1_sc_indicator_changed_cells.csv             where the changed cells are
  thesis_table/table_6_3_indicator_effect.csv  the chapter table
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.ops import unary_union

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import active_grid_gpkg, prep_dir, selfcollected_dir  # noqa: E402
from lib.arms import GSVI, GSVI_SC, Arm  # noqa: E402
from lib.ideamaps import (  # noqa: E402
    METHOD_LABEL,
    load_gsvi_submission_jenks_breaks,
    run_ideamaps_grid_pipeline,
)
from lib.provenance import PROVENANCE_ORDER, assign_provenance  # noqa: E402

OUTPUT_DIR = selfcollected_dir() / "3_indicator"
TABLE_DIR = OUTPUT_DIR / "thesis_table"

GRID_OUT = OUTPUT_DIR / "1_Nairobi_sc_indicator_grid100m_32737.gpkg"
PROVENANCE_CSV = OUTPUT_DIR / "1_sc_indicator_provenance.csv"
CLASS_CHANGE_CSV = OUTPUT_DIR / "1_sc_indicator_class_change.csv"
CHANGED_CELLS_CSV = OUTPUT_DIR / "1_sc_indicator_changed_cells.csv"
EFFECT_TABLE = TABLE_DIR / "table_6_3_indicator_effect.csv"

SLUM_GPKG = prep_dir() / "Nairobi_slum_polygon_32737.gpkg"

DIRECT, INTERPOLATED, UNSUPPORTED = PROVENANCE_ORDER
CLASS_LABELS = {0: "Low", 1: "Medium", 2: "High"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=None, help="Override the 100 m grid GeoPackage")
    return parser.parse_args()


def fmt_int(x: float) -> str:
    return f"{int(round(x)):,}"


def fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


def distance_to_direct(grid: gpd.GeoDataFrame, is_direct: np.ndarray) -> pd.Series:
    centroids = np.array([(p.x, p.y) for p in grid.geometry.centroid])
    if not is_direct.any():
        return pd.Series(np.nan, index=grid.index)
    tree = cKDTree(centroids[is_direct])
    dist, _ = tree.query(centroids, k=1)
    return pd.Series(dist, index=grid.index)


def score_arm(grid: gpd.GeoDataFrame, arm: Arm, breaks: np.ndarray) -> gpd.GeoDataFrame:
    """One run of the IDEAMaps pipeline, provenance attached."""
    print(f"\n[{arm.key}] {arm.label}")
    scored = run_ideamaps_grid_pipeline(
        grid, arm.svi_image_gpkg(), arm.waste_gpkg(), jenks_breaks=breaks
    )
    scored = assign_provenance(scored)
    is_direct = (scored["indicator_provenance"] == DIRECT).to_numpy()
    scored["dist_to_direct_m"] = distance_to_direct(scored, is_direct)
    print(f"  {int(is_direct.sum()):,} direct | "
          f"{int((scored['indicator_provenance'] == INTERPOLATED).sum()):,} interpolated | "
          f"{int((scored['indicator_provenance'] == UNSUPPORTED).sum()):,} unsupported")
    return scored


def combine(grid: gpd.GeoDataFrame, a: gpd.GeoDataFrame, b: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """One row per cell carrying both arms' values side by side."""
    out = grid[["cell_id", "geometry"]].copy()
    if "grid_source" in grid.columns:
        out["grid_source"] = grid["grid_source"].to_numpy()
    for tag, scored in (("gsvi", a), ("gsc", b)):
        for col in ("total_svi_images", "waste_points", "final_waste_ratio_platform",
                    "result", "indicator_provenance", "dist_to_direct_m"):
            out[f"{col}_{tag}"] = scored[col].to_numpy()

    out["class_change"] = out["result_gsc"] - out["result_gsvi"]
    out["ratio_change"] = out["final_waste_ratio_platform_gsc"] - out["final_waste_ratio_platform_gsvi"]
    out["gained_direct"] = (
        (out["indicator_provenance_gsc"] == DIRECT) & (out["indicator_provenance_gsvi"] != DIRECT)
    ).astype(int)
    out["received_sc"] = (out["total_svi_images_gsc"] > out["total_svi_images_gsvi"]).astype(int)
    return out


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def table_provenance(cells: pd.DataFrame) -> pd.DataFrame:
    n = len(cells)
    rows = []
    for label in PROVENANCE_ORDER:
        n_a = int((cells["indicator_provenance_gsvi"] == label).sum())
        n_b = int((cells["indicator_provenance_gsc"] == label).sum())
        rows.append(
            {
                "Provenance": label,
                "GSVI": f"{fmt_int(n_a)} ({fmt_pct(100 * n_a / n)})",
                "GSVI + SC": f"{fmt_int(n_b)} ({fmt_pct(100 * n_b / n)})",
                "Change": f"{n_b - n_a:+,}",
            }
        )
    # The headline the chapter cares about: how much of the represented surface
    # is measured rather than estimated.
    direct_a = int((cells["indicator_provenance_gsvi"] == DIRECT).sum())
    direct_b = int((cells["indicator_provenance_gsc"] == DIRECT).sum())
    rep_a = direct_a + int((cells["indicator_provenance_gsvi"] == INTERPOLATED).sum())
    rep_b = direct_b + int((cells["indicator_provenance_gsc"] == INTERPOLATED).sum())
    rows.append(
        {
            "Provenance": "Direct share of represented surface",
            "GSVI": fmt_pct(100 * direct_a / rep_a),
            "GSVI + SC": fmt_pct(100 * direct_b / rep_b),
            "Change": f"{100 * direct_b / rep_b - 100 * direct_a / rep_a:+.1f} pp",
        }
    )
    out = pd.DataFrame(rows)
    print("\nIndicator provenance, before and after:")
    print(out.to_string(index=False))
    out.to_csv(PROVENANCE_CSV, index=False)
    print(f"Wrote {PROVENANCE_CSV}")
    return out


def table_class_change(cells: pd.DataFrame) -> pd.DataFrame:
    ct = pd.crosstab(
        cells["result_gsvi"].map(CLASS_LABELS).rename("GSVI"),
        cells["result_gsc"].map(CLASS_LABELS).rename("GSVI + SC"),
        margins=True,
        margins_name="Total",
    )
    order = [*CLASS_LABELS.values(), "Total"]
    ct = ct.reindex(index=[c for c in order if c in ct.index],
                    columns=[c for c in order if c in ct.columns]).fillna(0).astype(int)
    print("\nPublished class before (rows) vs after (columns):")
    print(ct.to_string())
    ct.to_csv(CLASS_CHANGE_CSV)
    print(f"Wrote {CLASS_CHANGE_CSV}")
    return ct


# A cell's continuous value has "meaningfully" changed when the shift in its
# final waste ratio exceeds this. Set at the lower Jenks break, so it is the
# smallest change that could move a cell between published classes.
MEANINGFUL_RATIO_SHIFT = 0.0222


def table_changed_cells(cells: pd.DataFrame) -> pd.DataFrame:
    """Where the cells that changed class are, and whether they got imagery."""
    changed = cells[cells["class_change"] != 0]
    n = len(cells)
    if changed.empty:
        out = pd.DataFrame([{"Measure": "Cells changing class", "Value": "0"}])
        out.to_csv(CHANGED_CELLS_CSV, index=False)
        return out

    direct_changed = changed[changed["received_sc"] == 1]
    knock_on = changed[changed["received_sc"] == 0]
    moved = cells["ratio_change"].abs()
    n_any = int((moved > 0).sum())
    n_meaningful = int((moved > MEANINGFUL_RATIO_SHIFT).sum())
    rows = [
        ("Cells whose continuous value changes at all",
         f"{fmt_int(n_any)} ({fmt_pct(100 * n_any / n)} of grid)"),
        (f"Cells whose continuous value shifts >{MEANINGFUL_RATIO_SHIFT:.4f}",
         f"{fmt_int(n_meaningful)} ({fmt_pct(100 * n_meaningful / n)} of grid)"),
        ("Median absolute shift among cells that move",
         f"{moved[moved > 0].median():.5f}" if n_any else "—"),
        ("Cells changing published class", f"{fmt_int(len(changed))} ({fmt_pct(100 * len(changed) / n)} of grid)"),
        ("  moving up (Low→Medium, Medium→High)", fmt_int(int((changed["class_change"] > 0).sum()))),
        ("  moving down", fmt_int(int((changed["class_change"] < 0).sum()))),
        ("  that received self-collected imagery", f"{fmt_int(len(direct_changed))} ({fmt_pct(100 * len(direct_changed) / len(changed))})"),
        ("  changed only through the spatial fill", f"{fmt_int(len(knock_on))} ({fmt_pct(100 * len(knock_on) / len(changed))})"),
        ("Cells inside a settlement, among those changing",
         fmt_pct(100 * changed["in_settlement"].mean())),
        ("Cells inside a settlement, whole grid", fmt_pct(100 * cells["in_settlement"].mean())),
        ("Median distance to a settlement, changed cells", f"{changed['dist_settlement_m'].median():,.0f} m"),
        ("Median distance to a settlement, whole grid", f"{cells['dist_settlement_m'].median():,.0f} m"),
    ]
    out = pd.DataFrame(rows, columns=["Measure", "Value"])
    print("\nCells whose published class changed:")
    print(out.to_string(index=False))
    out.to_csv(CHANGED_CELLS_CSV, index=False)
    print(f"Wrote {CHANGED_CELLS_CSV}")
    return out


def table_effect(cells: pd.DataFrame) -> pd.DataFrame:
    """The chapter table: what adding self-collected imagery does to the surface."""
    n = len(cells)
    direct_a = int((cells["indicator_provenance_gsvi"] == DIRECT).sum())
    direct_b = int((cells["indicator_provenance_gsc"] == DIRECT).sum())
    interp_a = int((cells["indicator_provenance_gsvi"] == INTERPOLATED).sum())
    interp_b = int((cells["indicator_provenance_gsc"] == INTERPOLATED).sum())
    rep_a, rep_b = direct_a + interp_a, direct_b + interp_b
    changed = cells[cells["class_change"] != 0]

    rows = [
        ("Direct evidence", "Cells with an observed value",
         f"{fmt_int(direct_a)} ({fmt_pct(100 * direct_a / n)})",
         f"{fmt_int(direct_b)} ({fmt_pct(100 * direct_b / n)})",
         f"{direct_b - direct_a:+,}"),
        ("Interpolation", "Cells receiving an estimated value",
         f"{fmt_int(interp_a)} ({fmt_pct(100 * interp_a / n)})",
         f"{fmt_int(interp_b)} ({fmt_pct(100 * interp_b / n)})",
         f"{interp_b - interp_a:+,}"),
        ("Final indicator", "Share of represented surface resting on direct evidence",
         fmt_pct(100 * direct_a / rep_a), fmt_pct(100 * direct_b / rep_b),
         f"{100 * direct_b / rep_b - 100 * direct_a / rep_a:+.1f} pp"),
    ]
    for cls in sorted(CLASS_LABELS):
        n_a = int((cells["result_gsvi"] == cls).sum())
        n_b = int((cells["result_gsc"] == cls).sum())
        rows.append(("Published classes", f"Cells classified {CLASS_LABELS[cls]}",
                     f"{fmt_int(n_a)} ({fmt_pct(100 * n_a / n)})",
                     f"{fmt_int(n_b)} ({fmt_pct(100 * n_b / n)})",
                     f"{n_b - n_a:+,}"))
    rows.append(("Published classes", "Cells changing class", "—",
                 f"{fmt_int(len(changed))} ({fmt_pct(100 * len(changed) / n)} of grid)", "—"))

    out = pd.DataFrame(rows, columns=["Component", "Metric", "GSVI", "GSVI + SC", "Change"])
    print("\nWhat self-collected imagery does to the published surface:")
    print(out.to_string(index=False))
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(EFFECT_TABLE, index=False)
    print(f"Wrote {EFFECT_TABLE}")
    return out


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Method: {METHOD_LABEL}")

    grid_path = args.grid or active_grid_gpkg()
    grid = gpd.read_file(grid_path)
    print(f"Grid: {grid_path.name} ({len(grid):,} cells, {grid.crs})")
    breaks = load_gsvi_submission_jenks_breaks()

    scored_gsvi = score_arm(grid, GSVI, breaks)
    scored_gsc = score_arm(grid, GSVI_SC, breaks)
    cells = combine(grid, scored_gsvi, scored_gsc)

    slum_union = unary_union(gpd.read_file(SLUM_GPKG).to_crs(cells.crs).geometry)
    centroids = gpd.GeoSeries(cells.geometry.centroid, crs=cells.crs)
    cells["dist_settlement_m"] = centroids.distance(slum_union).to_numpy(dtype=float)
    cells["in_settlement"] = (cells["dist_settlement_m"] <= 0).astype(int)

    cells.to_file(GRID_OUT, driver="GPKG")
    print(f"\nWrote {GRID_OUT}")

    flat = cells.drop(columns="geometry")
    table_provenance(flat)
    table_class_change(flat)
    table_changed_cells(flat)
    table_effect(flat)


if __name__ == "__main__":
    main()

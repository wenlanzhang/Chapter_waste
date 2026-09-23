#!/usr/bin/env python3
"""Step 4b — independent local validation of the 100 m visible-waste indicator.

Compares the GSVI-derived indicator against the IDEAMaps crowd-validation
clicks collected in Nairobi. Each click carries a human severity judgement
(0 none / 1 medium / 2 high) at a point location; clicks are joined to the
100 m grid and reduced to one row per cell by taking the maximum severity,
matching how the platform treats multiple validators of the same cell.

The comparison is then split by indicator provenance, which is the point of
the exercise: a cell whose value came from imagery collected there is a
different kind of claim from one interpolated between distant observations.

Inputs:
  4_100m/1_Nairobi_indicator_grid100m_gsvi_32737.gpkg  (1_indicator_build.py)
  Waste/IDEAMaps/260701validation/validation-dataset.csv          crowd clicks

Outputs (Data/Chapter_waste/4_100m/):
  2_Nairobi_indicator_validation_cells.csv    one row per validated cell
  thesis_table/table_4_validation.csv         agreement overall and by provenance (chapter)
  4_validation_detail.csv                     counts and numeric rates behind that table
  5_validation_confusion.csv                  3-class crowd x indicator crosstab (feeds figure 2B)
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import phd_data_root, grid100_dir  # noqa: E402
from lib.provenance import PROVENANCE_ORDER  # noqa: E402

OUTPUT_DIR = grid100_dir()
THESIS_TABLE_DIR = OUTPUT_DIR / "thesis_table"
GRID_GPKG = OUTPUT_DIR / "1_Nairobi_indicator_grid100m_gsvi_32737.gpkg"
VALIDATION_CSV = phd_data_root() / "Waste" / "IDEAMaps" / "260701validation" / "validation-dataset.csv"
CELLS_CSV = OUTPUT_DIR / "2_Nairobi_indicator_validation_cells.csv"

DIRECT, INTERPOLATED, UNSUPPORTED = PROVENANCE_ORDER
CLASS_LABELS = {0: "Low", 1: "Medium", 2: "High"}

# Distance bands for interpolated cells, to test whether agreement decays with
# range from the nearest direct observation.
DISTANCE_BANDS = [(0, 100), (100, 200), (200, 500), (500, np.inf)]


def write_thesis(df: pd.DataFrame, name: str) -> Path:
    """A table that goes in the chapter."""
    THESIS_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = THESIS_TABLE_DIR / name
    df.to_csv(path, index=False)
    print(f"Wrote {path}")
    return path


def write_support(df: pd.DataFrame, name: str) -> Path:
    """Working output: numbers behind a figure, not a chapter table."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    df.to_csv(path, index=False)
    print(f"Wrote {path}")
    return path


def load_validation_cells() -> pd.DataFrame:
    """Crowd clicks joined to the indicator grid, one row per validated cell."""
    grid = gpd.read_file(GRID_GPKG)
    clicks = pd.read_csv(VALIDATION_CSV)
    pts = gpd.GeoDataFrame(
        clicks,
        geometry=gpd.points_from_xy(clicks["Longitude"], clicks["Latitude"]),
        crs="EPSG:4326",
    ).to_crs(grid.crs)

    joined = gpd.sjoin(
        pts,
        grid[
            [
                "cell_id",
                "indicator_provenance",
                "dist_to_direct_m",
                "total_svi_images",
                "waste_points",
                "final_waste_ratio_platform",
                "result",
                "geometry",
            ]
        ],
        how="inner",
        predicate="within",
    )
    print(
        f"Crowd clicks: {len(clicks):,} total, {len(joined):,} inside the grid, "
        f"covering {joined['cell_id'].nunique():,} cells"
    )

    cells = (
        joined.groupby("cell_id")
        .agg(
            crowd_severity=("Validation Result", "max"),
            published_result=("Model Result", "max"),
            n_clicks=("Validation Result", "size"),
            indicator_severity=("result", "first"),
            indicator_ratio=("final_waste_ratio_platform", "first"),
            provenance=("indicator_provenance", "first"),
            dist_to_direct_m=("dist_to_direct_m", "first"),
            total_svi_images=("total_svi_images", "first"),
            waste_points=("waste_points", "first"),
        )
        .reset_index()
        .dropna(subset=["crowd_severity"])
    )
    cells["crowd_severity"] = cells["crowd_severity"].astype(int)
    cells["crowd_waste"] = (cells["crowd_severity"] > 0).astype(int)
    cells["indicator_waste"] = (cells["indicator_severity"] > 0).astype(int)
    return cells


def binary_rates(truth: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    tp = int(np.sum((truth == 1) & (pred == 1)))
    fp = int(np.sum((truth == 0) & (pred == 1)))
    tn = int(np.sum((truth == 0) & (pred == 0)))
    fn = int(np.sum((truth == 1) & (pred == 0)))
    n = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else np.nan
    recall = tp / (tp + fn) if (tp + fn) else np.nan
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and (precision + recall) > 0
        else np.nan
    )
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": (tp + tn) / n if n else np.nan,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "crowd_positive_rate": (tp + fn) / n if n else np.nan,
        "indicator_positive_rate": (tp + fp) / n if n else np.nan,
    }


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    """Unweighted kappa on the 3-class severity scale."""
    labels = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return np.nan
    observed = np.mean(a == b)
    expected = sum(
        (np.mean(a == lab) * np.mean(b == lab)) for lab in labels
    )
    return (observed - expected) / (1 - expected) if expected < 1 else np.nan


def group_rows(cells: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Overall, then each provenance class, then distance bands within interpolated."""
    groups: list[tuple[str, pd.DataFrame]] = [("All validated cells", cells)]
    for label in PROVENANCE_ORDER:
        sub = cells[cells["provenance"] == label]
        if len(sub):
            groups.append((label, sub))
    interp = cells[cells["provenance"] == INTERPOLATED]
    for lo, hi in DISTANCE_BANDS:
        sub = interp[(interp["dist_to_direct_m"] > lo) & (interp["dist_to_direct_m"] <= hi)]
        if len(sub):
            name = f"  interpolated, {lo}-{hi:.0f} m from evidence" if np.isfinite(hi) else f"  interpolated, >{lo} m from evidence"
            groups.append((name, sub))
    return groups


def build_tables(cells: pd.DataFrame) -> None:
    display_rows, detail_rows = [], []
    for name, sub in group_rows(cells):
        m = binary_rates(sub["crowd_waste"].to_numpy(), sub["indicator_waste"].to_numpy())
        kappa = cohen_kappa(
            sub["crowd_severity"].to_numpy(), sub["indicator_severity"].to_numpy()
        )
        exact = float(np.mean(sub["crowd_severity"] == sub["indicator_severity"]))
        display_rows.append(
            {
                "Validated subset": name,
                "Cells, n": f"{m['n']:,}",
                "Binary agreement": f"{100 * m['accuracy']:.1f}%",
                "Crowd says waste": f"{100 * m['crowd_positive_rate']:.1f}%",
                "Indicator says waste": f"{100 * m['indicator_positive_rate']:.1f}%",
                "Recall": f"{100 * m['recall']:.1f}%" if np.isfinite(m["recall"]) else "—",
                "Precision": f"{100 * m['precision']:.1f}%" if np.isfinite(m["precision"]) else "—",
                "3-class exact": f"{100 * exact:.1f}%",
                "Kappa": f"{kappa:.3f}" if np.isfinite(kappa) else "—",
            }
        )
        detail_rows.append(
            {
                "subset": name.strip(),
                **{k: v for k, v in m.items()},
                "three_class_exact": exact,
                "cohen_kappa": kappa,
            }
        )

    display = pd.DataFrame(display_rows)
    print("\nAgreement with the local crowd validation:")
    print(display.to_string(index=False))
    write_thesis(display, "table_4_validation.csv")
    write_support(pd.DataFrame(detail_rows), "4_validation_detail.csv")

    crosstab = pd.crosstab(
        cells["crowd_severity"].map(CLASS_LABELS).rename("Crowd judgement"),
        cells["indicator_severity"].map(CLASS_LABELS).rename("Indicator class"),
    ).reindex(index=list(CLASS_LABELS.values()), columns=list(CLASS_LABELS.values()), fill_value=0)
    print("\n3-class crosstab (rows = crowd, columns = indicator):")
    print(crosstab.to_string())
    write_support(crosstab.reset_index(), "5_validation_confusion.csv")


def main() -> None:
    if not GRID_GPKG.exists():
        raise SystemExit(f"Missing {GRID_GPKG} — run 1_indicator_build.py first")
    if not VALIDATION_CSV.exists():
        raise SystemExit(f"Missing crowd validation file: {VALIDATION_CSV}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cells = load_validation_cells()
    cells.to_csv(CELLS_CSV, index=False)
    print(f"Wrote {CELLS_CSV}")
    build_tables(cells)


if __name__ == "__main__":
    main()

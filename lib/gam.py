"""Shared GAM constants and year-FE treatment for signed-distance models."""

from __future__ import annotations

import pandas as pd

MIN_YEAR_N = 200
SPLINE_DF = 8
SPLINE_DEGREE = 3
PRED_GRID_N = 200
CI_ALPHA = 0.05
BOOT_B = 80
BOOT_SEED = 42


def assign_year_fe(
    df: pd.DataFrame,
    *,
    year_col: str = "year",
    outcome_col: str = "waste_positive",
    min_year_n: int = MIN_YEAR_N,
    verbose: bool = True,
) -> pd.DataFrame:
    """Year fixed-effect levels: each sparse year joins its own nearest usable year.

    A year cannot carry its own fixed effect if it has fewer than `min_year_n`
    panoramas or no waste-positive panorama (the level would be estimated from
    almost nothing, or separate completely). Each such year is merged, on its
    own, into the nearest year that has neither problem; a tie goes to the
    earlier year. In the GSVI frame that sends 2015 (5 panoramas) to 2017 and
    2019 (73) to 2018.

    This replaces an earlier rule that first pooled all sparse years into one
    "other" level and then moved that level as a block, which placed 2015 in
    2018 only because it had been pooled with 2019.
    """
    out = df.copy()
    by_year = out.groupby(year_col)[outcome_col].agg(["size", "sum"])
    usable = by_year.index[(by_year["size"] >= min_year_n) & (by_year["sum"] > 0)]
    target = {y: y for y in by_year.index}
    if len(usable):
        for y in by_year.index.difference(usable):
            target[y] = min(usable, key=lambda u: (abs(u - y), u))
            if verbose:
                print(
                    f"  Year {y} ({int(by_year.loc[y, 'size']):,} panoids, "
                    f"{int(by_year.loc[y, 'sum'])} waste+) → year FE '{target[y]}' "
                    "(nearest year with enough panoramas and positives)"
                )
    out["year_fe"] = out[year_col].map(target).astype(str)
    return out

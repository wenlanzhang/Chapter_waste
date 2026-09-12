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
    """Pool rare years, then reassign zero-positive FE levels to the nearest year with positives."""
    out = df.copy()
    year_counts = out[year_col].value_counts()
    rare = set(year_counts[year_counts < min_year_n].index.tolist())
    out["year_fe"] = out[year_col].astype(str)
    if rare:
        out.loc[out[year_col].isin(rare), "year_fe"] = "other"
        if verbose:
            print(f"  Pooling rare years (n<{min_year_n}) as 'other': {sorted(rare)}")

    pos_by_fe = out.groupby("year_fe")[outcome_col].sum()
    zero_pos = [lv for lv, n in pos_by_fe.items() if int(n) == 0]
    if zero_pos:
        rep_year = out.groupby("year_fe")[year_col].median().astype(float).to_dict()
        positive_levels = [lv for lv, n in pos_by_fe.items() if int(n) > 0]
        pos_reps = {lv: rep_year[lv] for lv in positive_levels}
        for lv in zero_pos:
            y0 = rep_year[lv]
            nearest = min(pos_reps.items(), key=lambda kv: abs(kv[1] - y0))[0]
            n_move = int((out["year_fe"] == lv).sum())
            if verbose:
                print(
                    f"  Reassigning year_fe='{lv}' ({n_move:,} panoids, 0 waste+) "
                    f"→ '{nearest}' (nearest year FE with positives)"
                )
            out.loc[out["year_fe"] == lv, "year_fe"] = nearest
    return out

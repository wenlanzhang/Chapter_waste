"""Capture-era splits used by period-stratified GAM and HDBSCAN robustness."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

PERIODS: dict[str, dict[str, object]] = {
    "2015_2019": {
        "label": "2015–2019",
        "years": {2015, 2016, 2017, 2018, 2019},
    },
    "2021_2022": {
        "label": "2021–2022",
        "years": {2021, 2022},
    },
}


def period_key_for_year(year: int, periods: Mapping[str, dict] | None = None) -> str | None:
    table = periods if periods is not None else PERIODS
    for key, meta in table.items():
        if year in meta["years"]:
            return key
    return None


def assign_period(
    years: pd.Series,
    periods: Mapping[str, dict] | None = None,
) -> pd.Series:
    """Map calendar years to period keys; years outside the splits become NA."""
    table = periods if periods is not None else PERIODS
    numeric = pd.to_numeric(years, errors="coerce")
    return numeric.map(lambda y: period_key_for_year(int(y), table) if pd.notna(y) else None)

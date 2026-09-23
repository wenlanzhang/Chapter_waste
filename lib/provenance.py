"""Indicator provenance labels for the 100 m IDEAMaps grid."""

from __future__ import annotations

import geopandas as gpd
import numpy as np

PROVENANCE_ORDER = [
    "Direct observation",
    "Interpolated support",
    "Unsupported, platform-coded low",
]

DEFINITIONS = {
    "Direct observation": "At least one street-level image in the cell (arm-specific)",
    "Interpolated support": "No local imagery; value estimated through interpolation",
    "Unsupported, platform-coded low": (
        "Missing after interpolation; encoded as zero for IDEAMaps"
    ),
}


def assign_provenance(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Classify provenance from pipeline columns.

    Requires ``total_svi_images`` and ``final_waste_ratio`` *before* fillna(0).
    """
    out = grid.copy()
    has_svi = out["total_svi_images"].fillna(0).astype(int) > 0
    filled = out["final_waste_ratio"].notna()

    provenance = np.full(len(out), PROVENANCE_ORDER[2], dtype=object)
    provenance[has_svi.to_numpy()] = PROVENANCE_ORDER[0]
    provenance[(~has_svi & filled).to_numpy()] = PROVENANCE_ORDER[1]
    out["indicator_provenance"] = provenance
    out["final_waste_ratio_platform"] = out["final_waste_ratio"].fillna(0)
    return out

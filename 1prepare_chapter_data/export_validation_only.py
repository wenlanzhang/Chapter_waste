"""Export validation layers only (uses existing Step 1 grid)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "prep",
    Path(__file__).resolve().parent / "1_prepare_chapter_data.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

import geopandas as gpd

boundary = gpd.read_file(mod.BOUNDARY_SHP)
grid = gpd.read_file(mod.OUTPUT_DIR / mod.OUTPUT_FILES["grid_100m"])
validation_raw = mod.load_validation_points()
validation_clipped = gpd.clip(validation_raw, boundary)
validation_with_cells = mod.assign_validation_cell_ids(validation_clipped, grid)
validation_point_out = validation_with_cells.to_crs(mod.PROJECTED_CRS)
validation_grid_out = mod.aggregate_validation_by_cell(validation_with_cells, grid)

mod.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
for key, gdf in [
    ("validation_point", validation_point_out),
    ("validation_grid", validation_grid_out),
]:
    path = mod.OUTPUT_DIR / mod.OUTPUT_FILES[key]
    gdf.to_file(path, driver="GPKG")
    print(f"Wrote {path.name}: {len(gdf):,} features")

print(
    f"Points in grid: {validation_point_out['cell_id'].notna().sum():,}/"
    f"{len(validation_point_out):,}"
)
print(f"Validated cells: {len(validation_grid_out):,}")
print(f"Multi-click cells: {(validation_grid_out['n_validations'] > 1).sum():,}")

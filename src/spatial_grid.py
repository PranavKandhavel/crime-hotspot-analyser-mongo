"""
FR-3: Spatial Grid Generation

Divides the study area into rectangular grid cells using plain degree-based
binning, anchored at the (0, 0) origin so cell indices are reproducible
across runs (not dependent on this dataset's min/max bounds).

compute_cell() is unchanged from the Spark version and still pure Python,
so the existing unit tests (tests/test_spatial_grid.py) still apply
unmodified.

NEW in the Mongo port: each occupied grid cell is also built as a real
GeoJSON Polygon. This is what turns "hotspot ranking" from a plain group-by
into something MongoDB's actual geospatial query operators ($geoWithin,
$geoIntersects, etc.) can operate on, and gives the overlay queries
(union/intersects/symmetric difference/identity) real polygons to work
with instead of requiring a separate boundaries dataset.

Limitation (unchanged from the Spark version): degrees of latitude and
longitude are not uniform distances, so cells aren't perfectly square on
the ground outside the equator. Accepted simplification for a city-scale
MVP -- see README Limitations.
"""

import math

import numpy as np
import pandas as pd


def compute_cell(lat: float, lon: float, cell_size: float) -> tuple[int, int, float, float]:
    """Return (cell_x, cell_y, cell_center_lat, cell_center_lon) for one point."""
    cell_x = math.floor(lon / cell_size)
    cell_y = math.floor(lat / cell_size)
    center_lat = (cell_y + 0.5) * cell_size
    center_lon = (cell_x + 0.5) * cell_size
    return cell_x, cell_y, center_lat, center_lon


def cell_polygon_coordinates(cell_x: int, cell_y: int, cell_size: float) -> list:
    """GeoJSON Polygon coordinate ring for one grid cell, counter-clockwise
    (right-hand rule, as required by GeoJSON/MongoDB for well-formed polygons)."""
    min_lon, max_lon = cell_x * cell_size, (cell_x + 1) * cell_size
    min_lat, max_lat = cell_y * cell_size, (cell_y + 1) * cell_size
    return [[
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],  # closed ring
    ]]


def assign_grid_cells(df: pd.DataFrame, cell_size: float) -> pd.DataFrame:
    """Add cell_x, cell_y, cell_center_lat, cell_center_lon, and a GeoJSON
    'location' Point to every row. Vectorized with numpy (no per-row Python
    loop) so this stays fast even at tens of thousands of rows."""
    out = df.copy()
    out["cell_x"] = np.floor(out["longitude"] / cell_size).astype(int)
    out["cell_y"] = np.floor(out["latitude"] / cell_size).astype(int)
    out["cell_center_lat"] = (out["cell_y"] + 0.5) * cell_size
    out["cell_center_lon"] = (out["cell_x"] + 0.5) * cell_size

    num_occupied_cells = out[["cell_x", "cell_y"]].drop_duplicates().shape[0]
    print("=" * 60)
    print("FR-3: SPATIAL GRID GENERATION")
    print("=" * 60)
    print(f"Grid cell size:              {cell_size} degrees (~{cell_size * 111:.2f} km at the equator)")
    print(f"Occupied grid cells:         {num_occupied_cells}")
    print("Method: degree-based binning, origin (0,0). Not a metric-equal-area grid.")
    print()

    return out


def build_grid_cell_documents(df: pd.DataFrame, cell_size: float) -> list:
    """One GeoJSON Polygon document per unique occupied cell, ready to
    insert into the grid_cells collection. incident_count is filled in
    later by hotspot_analysis.aggregate_by_grid (kept separate so this
    function only depends on grid geometry, not on aggregation results)."""
    unique_cells = df[["cell_x", "cell_y", "cell_center_lat", "cell_center_lon"]].drop_duplicates()
    docs = []
    for row in unique_cells.itertuples(index=False):
        docs.append({
            "cell_x": int(row.cell_x),
            "cell_y": int(row.cell_y),
            "bounds": {
                "type": "Polygon",
                "coordinates": cell_polygon_coordinates(int(row.cell_x), int(row.cell_y), cell_size),
            },
            "center": {
                "type": "Point",
                "coordinates": [row.cell_center_lon, row.cell_center_lat],
            },
            "incident_count": 0,  # overwritten after aggregation
        })
    return docs

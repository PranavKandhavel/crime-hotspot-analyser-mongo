"""
Tests for the pieces of src/spatial_queries.py that don't require a live
Atlas connection: pure-Python distance math and the Shapely-based overlay
functions (overlay_union, overlay_symmetric_difference, overlay_identity).

Run with: pytest tests/test_spatial_queries_offline.py -v

Everything else in spatial_queries.py (KNN, containment, proximity,
adjacency, spatial joins, $geoIntersects-based intersects) needs a real
Atlas cluster and is exercised by actually running `python main.py`
against your own cluster -- see README "Testing against a live cluster".
"""

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.spatial_queries import (
    distance_euclidean,
    distance_geodetic_haversine,
    overlay_union,
    overlay_symmetric_difference,
    overlay_identity,
)
from src.spatial_grid import cell_polygon_coordinates


def _cell_poly(cx, cy, size=0.01):
    return {"type": "Polygon", "coordinates": cell_polygon_coordinates(cx, cy, size)}


def test_distance_euclidean_zero_for_identical_points():
    assert distance_euclidean([-87.63, 41.88], [-87.63, 41.88]) == 0.0


def test_distance_euclidean_matches_pythagoras():
    d = distance_euclidean([0, 0], [3, 4])
    assert math.isclose(d, 5.0)


def test_distance_geodetic_known_cities():
    # Chicago to New York, approx great-circle distance ~1145 km
    chicago = [-87.6298, 41.8781]
    new_york = [-74.0060, 40.7128]
    d_m = distance_geodetic_haversine(chicago, new_york)
    assert 1_100_000 < d_m < 1_200_000


def test_distance_geodetic_zero_for_identical_points():
    p = [-87.63, 41.88]
    assert distance_geodetic_haversine(p, p) == 0.0


def test_overlay_union_of_adjacent_cells_has_more_area_than_one():
    a = _cell_poly(0, 0)
    b = _cell_poly(1, 0)  # adjacent to the east
    from shapely.geometry import shape
    merged = overlay_union([a, b])
    merged_area = shape(merged).area
    single_area = shape(a).area
    assert merged_area > single_area
    assert math.isclose(merged_area, single_area * 2, rel_tol=1e-6)


def test_overlay_symmetric_difference_of_identical_polygons_is_empty():
    a = _cell_poly(5, 5)
    result = overlay_symmetric_difference(a, a)
    from shapely.geometry import shape
    assert shape(result).is_empty


def test_overlay_identity_non_overlapping_cells():
    a = _cell_poly(0, 0)
    b = _cell_poly(10, 10)  # far away, no overlap
    result = overlay_identity(a, b)
    assert result["overlap_with_b"] is None  # no intersection
    assert result["a_only"] is not None       # all of A remains

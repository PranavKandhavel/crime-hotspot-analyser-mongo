"""
Run with: pytest tests/test_spatial_grid.py -v
No Mongo connection required -- compute_cell() is pure Python.
"""

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.spatial_grid import compute_cell, cell_polygon_coordinates

CELL_SIZE = 0.01


def test_origin_cell():
    cell_x, cell_y, center_lat, center_lon = compute_cell(0.005, 0.005, CELL_SIZE)
    assert cell_x == 0
    assert cell_y == 0
    assert math.isclose(center_lat, 0.005)
    assert math.isclose(center_lon, 0.005)


def test_known_chicago_point():
    lat, lon = 41.8781, -87.6298
    cell_x, cell_y, center_lat, center_lon = compute_cell(lat, lon, CELL_SIZE)
    assert cell_x == math.floor(lon / CELL_SIZE) == -8763
    assert cell_y == math.floor(lat / CELL_SIZE) == 4187
    assert abs(center_lat - lat) <= CELL_SIZE
    assert abs(center_lon - lon) <= CELL_SIZE


def test_negative_coordinates_do_not_crash():
    cell_x, cell_y, _, _ = compute_cell(-33.87, 151.21, CELL_SIZE)
    assert isinstance(cell_x, int)
    assert isinstance(cell_y, int)


def test_cell_boundary_rounds_down_not_toward_zero():
    cell_x, _, _, _ = compute_cell(0.0, -0.001, CELL_SIZE)
    assert cell_x == -1  # NOT 0


def test_adjacent_points_can_share_a_cell():
    a = compute_cell(41.8781, -87.6298, CELL_SIZE)
    b = compute_cell(41.8782, -87.6299, CELL_SIZE)
    assert (a[0], a[1]) == (b[0], b[1])


def test_cell_polygon_is_closed_and_ccw():
    coords = cell_polygon_coordinates(-8763, 4187, CELL_SIZE)[0]
    assert coords[0] == coords[-1]  # closed ring
    assert len(coords) == 5  # 4 corners + closing point
    # counter-clockwise: x increases then y increases then x decreases then y decreases
    assert coords[1][0] > coords[0][0]  # east
    assert coords[2][1] > coords[1][1]  # north
    assert coords[3][0] < coords[2][0]  # west

"""
The full spatial query catalog, mapped one-to-one onto the requirements
list. Each function is self-contained and documented with which MongoDB
operator (or, where Mongo has no native equivalent, which client-side
library) implements it.

IMPORTANT, read before using this module in a report: MongoDB's geo
operators ($geoWithin, $geoIntersects, $near, $geoNear) can all TEST
spatial relationships (is this point inside that polygon? how far apart
are these?) but none of them COMPUTE a new geometry. True overlay algebra
-- Union, Symmetric Difference, Identity -- needs actual polygon-clipping
math, which MongoDB does not implement (this is the same reason tools like
PostGIS or Apache Sedona exist). Those three operations below use Shapely
on data already pulled out of Mongo; everything else is a real, native
MongoDB query.

Two different coordinate representations are stored on every crime
document specifically so both notions of "distance" are queryable:
  - `location`        : GeoJSON Point, 2dsphere index -> geodetic (great-
                         circle / curved-earth) distance, used by $near,
                         $geoNear, $geoWithin/$geoIntersects with $geometry.
  - `location_legacy`  : plain [lon, lat] pair, 2d index -> planar
                         (Euclidean) distance, used by $near/$geoWithin
                         with legacy coordinate syntax (e.g. $box).
"""

from shapely.geometry import shape, mapping
from shapely.ops import unary_union

import config

EARTH_RADIUS_M = 6_371_000


# ---------------------------------------------------------------------------
# 1. Distance measurement
# ---------------------------------------------------------------------------

def distance_euclidean(point_a: list, point_b: list) -> float:
    """Straight-line (planar) distance between two [lon, lat] points, in
    degrees. This treats the coordinate plane as flat -- fine for a tight
    local comparison, misleading over city-sized spans or near the poles.
    Pure Python; matches what a 2d-index $near query ranks by."""
    return ((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2) ** 0.5


def distance_geodetic_haversine(point_a: list, point_b: list) -> float:
    """Great-circle distance between two [lon, lat] points, in meters,
    via the haversine formula -- accounts for the Earth's curvature,
    unlike distance_euclidean(). This is what a 2dsphere-indexed $near /
    $geoNear query computes internally."""
    import math
    lon1, lat1, lon2, lat2 = map(math.radians, [point_a[0], point_a[1], point_b[0], point_b[1]])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1, math.sqrt(a)))


def query_nearest_with_geodetic_distance(db, point: list, k: int) -> list:
    """$geoNear: k nearest crimes to `point`, with each result's true
    geodesic distance (meters) attached as `distance_m`. Requires the
    2dsphere index on `location`."""
    pipeline = [
        {"$geoNear": {
            "near": {"type": "Point", "coordinates": point},
            "distanceField": "distance_m",
            "spherical": True,
            "limit": k,
        }},
        {"$project": {"_id": 0, "crime_id": 1, "category": 1, "location": 1, "distance_m": 1}},
    ]
    return list(db[config.COLLECTION_CRIMES].aggregate(pipeline))


# ---------------------------------------------------------------------------
# 2. KNN search and KNN join
# ---------------------------------------------------------------------------

def query_knn(db, point: list, k: int) -> list:
    """$near on the 2dsphere index: k nearest crimes to an arbitrary point,
    sorted nearest-first (native to the index, no extra sort stage needed)."""
    cursor = db[config.COLLECTION_CRIMES].find(
        {"location": {"$near": {"$geometry": {"type": "Point", "coordinates": point}}}}
    ).limit(k)
    return list(cursor)


def query_knn_join(db, k: int, sample_size: int) -> list:
    """For each of `sample_size` source crimes, find its k nearest OTHER
    crimes. This is a point-to-point KNN join: Mongo has no single
    operator for "join every row in A to its k nearest in B", so it's
    done as one $near query per source point. Fine at small sample sizes
    (this project's scale); at real scale you'd batch/parallelize this or
    use a different engine built for joins (e.g. a spatial-partitioned
    batch job)."""
    crimes = db[config.COLLECTION_CRIMES]
    sources = list(crimes.find({}, {"crime_id": 1, "location": 1}).limit(sample_size))

    results = []
    for src in sources:
        neighbors = list(crimes.find(
            {
                "crime_id": {"$ne": src["crime_id"]},
                "location": {"$near": {"$geometry": src["location"]}},
            },
            {"crime_id": 1, "location": 1, "category": 1},
        ).limit(k))
        results.append({"source_id": src["crime_id"], "neighbors": neighbors})
    return results


# ---------------------------------------------------------------------------
# 3. Containment and spatial range search
# ---------------------------------------------------------------------------

def query_containment(db, polygon_geojson: dict, limit: int = 0) -> list:
    """$geoWithin: every crime point contained inside an arbitrary
    GeoJSON polygon (e.g. a hotspot cell boundary, or the union of
    several). Geodetic -- needs the 2dsphere index."""
    cursor = db[config.COLLECTION_CRIMES].find(
        {"location": {"$geoWithin": {"$geometry": polygon_geojson}}}
    )
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def query_spatial_range_box_euclidean(db, lower_left: list, upper_right: list) -> list:
    """$geoWithin + $box on the LEGACY 2d index (location_legacy): a
    rectangular range search using planar/Euclidean distance semantics,
    as distinct from the geodetic polygon search above."""
    cursor = db[config.COLLECTION_CRIMES].find(
        {"location_legacy": {"$geoWithin": {"$box": [lower_left, upper_right]}}}
    )
    return list(cursor)


# ---------------------------------------------------------------------------
# 4. Proximity (buffer) and adjacency
# ---------------------------------------------------------------------------

def query_proximity_buffer(db, center_point: list, inner_radius_m: float, outer_radius_m: float) -> dict:
    """Builds the two surfaces a buffer query needs: points within
    inner_radius_m (the 'core'), and points between inner_radius_m and
    outer_radius_m (the 'buffer ring' / donut). Both via $geoWithin +
    $centerSphere, which takes a radius in RADIANS -- divide meters by
    Earth's radius to convert."""
    crimes = db[config.COLLECTION_CRIMES]
    inner_radius_rad = inner_radius_m / EARTH_RADIUS_M
    outer_radius_rad = outer_radius_m / EARTH_RADIUS_M

    inner_docs = list(crimes.find(
        {"location": {"$geoWithin": {"$centerSphere": [center_point, inner_radius_rad]}}}
    ))
    outer_docs = list(crimes.find(
        {"location": {"$geoWithin": {"$centerSphere": [center_point, outer_radius_rad]}}}
    ))
    inner_ids = {d["crime_id"] for d in inner_docs}
    buffer_ring_docs = [d for d in outer_docs if d["crime_id"] not in inner_ids]

    return {"within_inner": inner_docs, "buffer_ring": buffer_ring_docs}


def query_adjacency(db, cell_x: int, cell_y: int) -> list:
    """Adjacency as zero-distance proximity: grid cells whose polygon
    boundary touches or overlaps the target cell's boundary, found via
    $geoIntersects (a feature at distance 0 from another necessarily
    intersects it). The target cell itself is excluded from the result."""
    target = db[config.COLLECTION_GRID_CELLS].find_one({"cell_x": cell_x, "cell_y": cell_y})
    if target is None:
        return []
    neighbors = list(db[config.COLLECTION_GRID_CELLS].find({
        "bounds": {"$geoIntersects": {"$geometry": target["bounds"]}},
        "$nor": [{"cell_x": cell_x, "cell_y": cell_y}],
    }))
    return neighbors


# ---------------------------------------------------------------------------
# 5. Spatial aggregation and spatial join
# ---------------------------------------------------------------------------

def query_spatial_aggregation(db, polygon_geojson: dict) -> list:
    """Crime counts by category within an arbitrary polygon region (not
    limited to a single pre-built grid cell) -- $match on $geoWithin,
    then the same $group aggregation used elsewhere in the project."""
    pipeline = [
        {"$match": {"location": {"$geoWithin": {"$geometry": polygon_geojson}}}},
        {"$group": {"_id": "$category", "incident_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "category": "$_id", "incident_count": 1}},
        {"$sort": {"incident_count": -1}},
    ]
    return list(db[config.COLLECTION_CRIMES].aggregate(pipeline))


def spatial_join_points_to_polygons(db, polygon_docs: list) -> list:
    """A genuine spatial join: for each polygon document, find every crime
    point that geometrically falls inside it ($geoWithin), rather than
    relying on a pre-computed attribute key like cell_x/cell_y (that's
    what hotspot_analysis.aggregate_by_grid does, and is an attribute
    join, not a spatial one). Run only over the polygons you pass in
    (e.g. the top-N hotspot cells) -- one query per polygon, so keep the
    input list small."""
    crimes = db[config.COLLECTION_CRIMES]
    joined = []
    for poly_doc in polygon_docs:
        matches = list(crimes.find(
            {"location": {"$geoWithin": {"$geometry": poly_doc["bounds"]}}},
            {"crime_id": 1, "category": 1},
        ))
        joined.append({
            "cell_x": poly_doc["cell_x"], "cell_y": poly_doc["cell_y"],
            "matched_count": len(matches), "crime_ids": [m["crime_id"] for m in matches],
        })
    return joined


# ---------------------------------------------------------------------------
# 6. Overlay: Intersects (native), Union / Symmetric Difference / Identity
#    (client-side via Shapely -- see module docstring for why)
# ---------------------------------------------------------------------------

def overlay_intersects(db, polygon_geojson: dict) -> list:
    """$geoIntersects: every grid cell whose polygon intersects the given
    polygon. In a regular, non-overlapping grid this returns the touching
    neighbors plus any cell the query polygon overlaps -- the native-Mongo
    half of 'overlay'."""
    return list(db[config.COLLECTION_GRID_CELLS].find(
        {"bounds": {"$geoIntersects": {"$geometry": polygon_geojson}}}
    ))


def overlay_union(polygon_geojsons: list) -> dict:
    """Union: merge several polygons into one combined geometry. No native
    Mongo operator computes this -- done with Shapely after pulling the
    geometries out. Typical use here: merge the top-N hotspot cells into
    one combined 'hotspot region' polygon."""
    shapes = [shape(g) for g in polygon_geojsons]
    merged = unary_union(shapes)
    return mapping(merged)


def overlay_symmetric_difference(polygon_a_geojson: dict, polygon_b_geojson: dict) -> dict:
    """Symmetric difference: the area covered by exactly one of the two
    polygons, not both and not neither. Shapely-only, same reason as
    Union above."""
    a, b = shape(polygon_a_geojson), shape(polygon_b_geojson)
    return mapping(a.symmetric_difference(b))


def overlay_identity(polygon_a_geojson: dict, polygon_b_geojson: dict) -> dict:
    """Identity overlay (GIS sense, e.g. ArcGIS's Identity tool): output
    covers the full extent of polygon A, split into the part that overlaps
    polygon B and the part that doesn't, each taggable with which input(s)
    contributed it. Returns both pieces; a real GIS tool would also carry
    forward B's attributes onto the overlap piece -- do that in the
    caller, since this function only has geometry, not attribute data."""
    a, b = shape(polygon_a_geojson), shape(polygon_b_geojson)
    overlap = a.intersection(b)
    a_only = a.difference(b)
    return {
        "overlap_with_b": mapping(overlap) if not overlap.is_empty else None,
        "a_only": mapping(a_only) if not a_only.is_empty else None,
    }

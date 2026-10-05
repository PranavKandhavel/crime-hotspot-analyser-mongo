"""
Flask REST API for the Crime Hotspot Analyser React frontend.

Start with:
    python api/app.py

Requires MONGO_URI in .env (same as main.py).
Endpoints serve live data from MongoDB Atlas.
"""

import sys
import os

# Allow imports from the project root (config, src.*)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request
from flask_cors import CORS

import config
from src import db as dbmod
from src.hotspot_analysis import aggregate_by_grid, rank_hotspots
from src.temporal_analysis import category_summary, monthly_counts, hourly_counts, day_night_comparison
from src.spatial_grid import cell_polygon_coordinates
import src.spatial_queries as sq

app = Flask(__name__)
CORS(app)   # allow React dev server (localhost:5173) to call this

# ── helpers ──────────────────────────────────────────────────────────────────

def _db():
    return dbmod.get_db()


def _serialize(doc):
    """Strip MongoDB _id and convert datetime objects to ISO strings."""
    import datetime
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime.datetime):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_serialize(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, dict):
            out[k] = _serialize(v)
        else:
            out[k] = v
    return out


# ── aggregate / analysis endpoints ───────────────────────────────────────────

@app.route("/api/hotspots")
def api_hotspots():
    """Top-N hotspot grid cells, sorted by incident_count desc."""
    top_n = int(request.args.get("n", config.TOP_N_HOTSPOTS))
    db = _db()
    grid_counts = aggregate_by_grid(db)
    hotspots = rank_hotspots(grid_counts, top_n)

    results = []
    for rank, h in enumerate(hotspots, 1):
        coords = cell_polygon_coordinates(h["cell_x"], h["cell_y"], config.GRID_CELL_SIZE_DEGREES)
        # coords[0] is the ring [[lon,lat], ...]  -> convert to [[lat,lon], ...] for Leaflet
        polygon_latlon = [[pt[1], pt[0]] for pt in coords[0]]
        entry = _serialize(h)
        entry["rank"] = rank
        entry["polygon_latlon"] = polygon_latlon
        entry["center_lat"] = (h["cell_y"] + 0.5) * config.GRID_CELL_SIZE_DEGREES
        entry["center_lon"] = (h["cell_x"] + 0.5) * config.GRID_CELL_SIZE_DEGREES
        results.append(entry)
    return jsonify(results)


@app.route("/api/categories")
def api_categories():
    """Crime counts by category, most frequent first."""
    db = _db()
    data = category_summary(db)
    return jsonify([_serialize(d) for d in data])


@app.route("/api/temporal/monthly")
def api_monthly():
    db = _db()
    data = monthly_counts(db)
    return jsonify([_serialize(d) for d in data])


@app.route("/api/temporal/hourly")
def api_hourly():
    db = _db()
    data = hourly_counts(db)
    return jsonify([_serialize(d) for d in data])


@app.route("/api/temporal/day_night")
def api_day_night():
    db = _db()
    data = day_night_comparison(db)
    return jsonify([_serialize(d) for d in data])


@app.route("/api/stats")
def api_stats():
    """Summary statistics for the banner."""
    db = _db()
    total = db[config.COLLECTION_CRIMES].count_documents({})
    with_date = db[config.COLLECTION_CRIMES].count_documents({"has_valid_date": True})
    # Date range from an aggregation (faster than sorting the entire collection)
    pipeline = [
        {"$match": {"has_valid_date": True}},
        {"$group": {
            "_id": None,
            "earliest": {"$min": "$event_ts"},
            "latest": {"$max": "$event_ts"},
        }},
    ]
    agg = list(db[config.COLLECTION_CRIMES].aggregate(pipeline))
    earliest = agg[0]["earliest"].isoformat() if agg else None
    latest   = agg[0]["latest"].isoformat()   if agg else None
    grid_cells = db[config.COLLECTION_GRID_CELLS].count_documents({})
    return jsonify({
        "total_crimes": total,
        "crimes_with_date": with_date,
        "grid_cells": grid_cells,
        "earliest": earliest,
        "latest": latest,
    })


# ── spatial query endpoints ───────────────────────────────────────────────────

@app.route("/api/queries/knn")
def api_knn():
    """KNN search: k nearest crimes to a point.
    Query params: lat, lon, k (default 10)
    """
    lat = float(request.args.get("lat", 0))
    lon = float(request.args.get("lon", 0))
    k   = int(request.args.get("k", config.KNN_DEFAULT_K))
    db = _db()
    results = sq.query_knn(db, [lon, lat], k)
    return jsonify([_serialize(r) for r in results])


@app.route("/api/queries/containment")
def api_containment():
    """Crimes inside a specific grid cell polygon.
    Query params: cell_x, cell_y, limit (default 200)
    """
    cell_x = int(request.args.get("cell_x", 0))
    cell_y = int(request.args.get("cell_y", 0))
    limit  = int(request.args.get("limit", 200))
    polygon = {
        "type": "Polygon",
        "coordinates": cell_polygon_coordinates(cell_x, cell_y, config.GRID_CELL_SIZE_DEGREES),
    }
    db = _db()
    results = sq.query_containment(db, polygon, limit=limit)
    return jsonify([_serialize(r) for r in results])


@app.route("/api/queries/range")
def api_range():
    """Euclidean bounding-box search.
    Query params: lat1, lon1 (lower-left), lat2, lon2 (upper-right)
    """
    lat1 = float(request.args.get("lat1", 0))
    lon1 = float(request.args.get("lon1", 0))
    lat2 = float(request.args.get("lat2", 0))
    lon2 = float(request.args.get("lon2", 0))
    db = _db()
    results = sq.query_spatial_range_box_euclidean(db, [lon1, lat1], [lon2, lat2])
    return jsonify([_serialize(r) for r in results])


@app.route("/api/queries/buffer")
def api_buffer():
    """Proximity buffer (inner + outer ring).
    Query params: lat, lon, inner_m (default 500), outer_m (default 1500)
    """
    lat     = float(request.args.get("lat", 0))
    lon     = float(request.args.get("lon", 0))
    inner_m = float(request.args.get("inner_m", config.PROXIMITY_INNER_RADIUS_M))
    outer_m = float(request.args.get("outer_m", config.PROXIMITY_OUTER_RADIUS_M))
    db = _db()
    result = sq.query_proximity_buffer(db, [lon, lat], inner_m, outer_m)
    return jsonify({
        "within_inner": [_serialize(r) for r in result["within_inner"]],
        "buffer_ring":  [_serialize(r) for r in result["buffer_ring"]],
        "inner_count":  len(result["within_inner"]),
        "ring_count":   len(result["buffer_ring"]),
    })


@app.route("/api/queries/adjacency")
def api_adjacency():
    """Adjacent grid cells to a target cell.
    Query params: cell_x, cell_y
    """
    cell_x = int(request.args.get("cell_x", 0))
    cell_y = int(request.args.get("cell_y", 0))
    db = _db()
    results = sq.query_adjacency(db, cell_x, cell_y)
    # Attach Leaflet-friendly polygon coords
    out = []
    for r in results:
        entry = _serialize(r)
        coords = cell_polygon_coordinates(r["cell_x"], r["cell_y"], config.GRID_CELL_SIZE_DEGREES)
        entry["polygon_latlon"] = [[pt[1], pt[0]] for pt in coords[0]]
        out.append(entry)
    return jsonify(out)


@app.route("/api/queries/aggregation")
def api_aggregation():
    """Category breakdown inside a grid cell polygon.
    Query params: cell_x, cell_y
    """
    cell_x = int(request.args.get("cell_x", 0))
    cell_y = int(request.args.get("cell_y", 0))
    polygon = {
        "type": "Polygon",
        "coordinates": cell_polygon_coordinates(cell_x, cell_y, config.GRID_CELL_SIZE_DEGREES),
    }
    db = _db()
    results = sq.query_spatial_aggregation(db, polygon)
    return jsonify([_serialize(r) for r in results])


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Crime Hotspot API on http://localhost:5000")
    print("Ensure MONGO_URI is set in .env and main.py has been run to populate the DB.")
    app.run(debug=True, port=5000)

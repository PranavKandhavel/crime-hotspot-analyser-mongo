"""
FR-4: Crime Aggregation
FR-5: Hotspot Identification

Spark's groupBy().agg() becomes a MongoDB aggregation pipeline $group
stage. Results are written back onto the grid_cells documents so later
spatial queries (containment, overlay, union of top hotspots) have the
incident_count available directly on each polygon.

These are "high-count cells", never "statistically significant hotspots"
-- that label needs a real spatial-statistics test (e.g. Getis-Ord Gi*),
which is out of scope here. See README Limitations.
"""

from pymongo import UpdateOne
from pymongo.database import Database

import config


def aggregate_by_grid(db: Database) -> list:
    """FR-4: group crimes by grid cell; returns cells sorted by count desc."""
    crimes = db[config.COLLECTION_CRIMES]

    pipeline = [
        {"$group": {
            "_id": {"cell_x": "$cell_x", "cell_y": "$cell_y"},
            "incident_count": {"$sum": 1},
            "categories": {"$addToSet": "$category"},
            "earliest_incident": {"$min": "$event_ts"},
            "latest_incident": {"$max": "$event_ts"},
        }},
        {"$project": {
            "_id": 0,
            "cell_x": "$_id.cell_x",
            "cell_y": "$_id.cell_y",
            "incident_count": 1,
            "distinct_categories": {"$size": "$categories"},
            "earliest_incident": 1,
            "latest_incident": 1,
        }},
        {"$sort": {"incident_count": -1}},
    ]

    print("=" * 60)
    print("FR-4: CRIME AGGREGATION")
    print("=" * 60)

    # Technical note (mirrors the Spark version's .explain() call): surface
    # the winning query plan for this aggregation so the index usage behind
    # the $group stage is visible and explainable in the report.
    try:
        explain_result = db.command(
            "aggregate", config.COLLECTION_CRIMES, pipeline=pipeline, explain=True
        )
        winning_plan = explain_result.get("queryPlanner", {}).get("winningPlan", explain_result)
        print(f"Winning query plan (stage): {winning_plan.get('stage', 'see full explain output')}")
    except Exception as e:  # explain support varies slightly by Atlas tier; never block the real run on it
        print(f"(explain unavailable: {e})")

    results = list(crimes.aggregate(pipeline))
    print(f"Occupied grid cells aggregated: {len(results)}")
    print()
    return results


def write_counts_to_grid_cells(db: Database, grid_counts: list) -> None:
    """Push each cell's incident_count/category-count/date-range back onto
    its grid_cells document, so later queries can read it straight off the
    polygon without re-joining to crimes every time."""
    grid_cells = db[config.COLLECTION_GRID_CELLS]
    ops = [
        UpdateOne(
            {"cell_x": c["cell_x"], "cell_y": c["cell_y"]},
            {"$set": {
                "incident_count": c["incident_count"],
                "distinct_categories": c["distinct_categories"],
                "earliest_incident": c["earliest_incident"],
                "latest_incident": c["latest_incident"],
            }},
        )
        for c in grid_counts
    ]
    if ops:
        grid_cells.bulk_write(ops, ordered=False)


def rank_hotspots(grid_counts: list, top_n: int) -> list:
    """FR-5: top N cells by incident_count (grid_counts is already sorted)."""
    hotspots = grid_counts[:top_n]

    print("=" * 60)
    print(f"FR-5: HOTSPOT IDENTIFICATION (top {top_n} high-count cells)")
    print("=" * 60)
    print("Note: ranked by raw incident count only. These are 'high-count")
    print("cells', not statistically significant clusters -- no significance")
    print("test (e.g. Getis-Ord Gi*) has been applied. See README Limitations.")
    print()

    return hotspots

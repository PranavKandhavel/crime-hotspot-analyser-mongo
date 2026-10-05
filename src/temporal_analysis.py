"""
FR-6: Crime Category Analysis
FR-7: Temporal Analysis

All temporal summaries filter on has_valid_date: true, per FR-2/FR-7:
records with valid coordinates but missing/unparseable dates are retained
in `crimes` for spatial analysis but excluded here.

event_ts is stored as a native BSON Date (see src/ingest.py), which is
what makes Mongo's $month/$hour/$dateToString aggregation operators usable
directly -- storing it as a string would require re-parsing it in every
pipeline.
"""

from pymongo.database import Database

import config


def category_summary(db: Database) -> list:
    """FR-6: total incidents per category, most frequent first."""
    pipeline = [
        {"$group": {"_id": "$category", "incident_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "category": "$_id", "incident_count": 1}},
        {"$sort": {"incident_count": -1}},
    ]
    result = list(db[config.COLLECTION_CRIMES].aggregate(pipeline))
    print("=" * 60)
    print("FR-6: CRIME CATEGORY ANALYSIS")
    print("=" * 60)
    for row in result[:10]:
        print(f"  {row['category']:<20} {row['incident_count']}")
    print()
    return result


def hotspot_category_breakdown(db: Database, hotspot_cells: list) -> list:
    """FR-6: category counts restricted to the identified high-count cells."""
    cell_pairs = [{"cell_x": c["cell_x"], "cell_y": c["cell_y"]} for c in hotspot_cells]
    if not cell_pairs:
        return []
    pipeline = [
        {"$match": {"$or": cell_pairs}},
        {"$group": {
            "_id": {"cell_x": "$cell_x", "cell_y": "$cell_y", "category": "$category"},
            "incident_count": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0, "cell_x": "$_id.cell_x", "cell_y": "$_id.cell_y",
            "category": "$_id.category", "incident_count": 1,
        }},
        {"$sort": {"cell_x": 1, "cell_y": 1, "incident_count": -1}},
    ]
    return list(db[config.COLLECTION_CRIMES].aggregate(pipeline))


def monthly_counts(db: Database) -> list:
    """FR-7: incidents per calendar month (year-month)."""
    pipeline = [
        {"$match": {"has_valid_date": True}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$event_ts"}},
            "incident_count": {"$sum": 1},
        }},
        {"$project": {"_id": 0, "year_month": "$_id", "incident_count": 1}},
        {"$sort": {"year_month": 1}},
    ]
    result = list(db[config.COLLECTION_CRIMES].aggregate(pipeline))
    total = db[config.COLLECTION_CRIMES].count_documents({})
    excluded = total - db[config.COLLECTION_CRIMES].count_documents({"has_valid_date": True})
    print("=" * 60)
    print(f"FR-7: TEMPORAL ANALYSIS -- monthly counts (excluded {excluded} records with missing/invalid dates)")
    print("=" * 60)
    return result


def hourly_counts(db: Database) -> list:
    """FR-7: incidents per hour of day."""
    pipeline = [
        {"$match": {"has_valid_date": True}},
        {"$group": {"_id": {"$hour": "$event_ts"}, "incident_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "hour": "$_id", "incident_count": 1}},
        {"$sort": {"hour": 1}},
    ]
    return list(db[config.COLLECTION_CRIMES].aggregate(pipeline))


def day_night_comparison(db: Database) -> list:
    """FR-7: day vs night counts using config.DAY_START_HOUR / NIGHT_START_HOUR.
    Hours in [DAY_START, NIGHT_START) = 'day'."""
    pipeline = [
        {"$match": {"has_valid_date": True}},
        {"$addFields": {"hour": {"$hour": "$event_ts"}}},
        {"$addFields": {
            "period": {
                "$cond": [
                    {"$and": [
                        {"$gte": ["$hour", config.DAY_START_HOUR]},
                        {"$lt": ["$hour", config.NIGHT_START_HOUR]},
                    ]},
                    "day", "night",
                ]
            }
        }},
        {"$group": {"_id": "$period", "incident_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "period": "$_id", "incident_count": 1}},
    ]
    result = list(db[config.COLLECTION_CRIMES].aggregate(pipeline))
    print(f"Day/night split: day = [{config.DAY_START_HOUR}:00, {config.NIGHT_START_HOUR}:00), else night")
    return result

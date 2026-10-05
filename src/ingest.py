"""
Loads cleaned, grid-assigned records into Atlas.

Replaces Spark's distributed write with pymongo bulk inserts. This is the
one place where pandas NaT/NaN needs explicit handling -- MongoDB has no
native NaN/NaT, so they're converted to None before insertion.
"""

import math

import pandas as pd
from pymongo import ASCENDING, GEO2D, GEOSPHERE
from pymongo.database import Database

import config


def _clean_value(v):
    """pandas NaN/NaT -> None, so pymongo doesn't choke on non-JSON-safe floats."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def build_crime_documents(df: pd.DataFrame) -> list:
    docs = []
    for row in df.itertuples(index=False):
        event_ts = _clean_value(row.event_ts)
        docs.append({
            "crime_id": row.crime_id,
            "category": row.category,
            "raw_date": _clean_value(row.raw_date),
            "event_ts": event_ts.to_pydatetime() if isinstance(event_ts, pd.Timestamp) else None,
            "has_valid_date": bool(row.has_valid_date),
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
            "location": {"type": "Point", "coordinates": [float(row.longitude), float(row.latitude)]},  # GeoJSON: [lon, lat] -> 2dsphere, geodetic queries
            "location_legacy": [float(row.longitude), float(row.latitude)],  # plain pair -> 2d index, Euclidean/planar queries
            "cell_x": int(row.cell_x),
            "cell_y": int(row.cell_y),
        })
    return docs


def ensure_indexes(db: Database) -> None:
    crimes = db[config.COLLECTION_CRIMES]
    grid_cells = db[config.COLLECTION_GRID_CELLS]

    crimes.create_index([("location", GEOSPHERE)])
    crimes.create_index([("location_legacy", GEO2D)])
    crimes.create_index([("cell_x", ASCENDING), ("cell_y", ASCENDING)])
    crimes.create_index([("category", ASCENDING)])
    crimes.create_index([("event_ts", ASCENDING)])

    grid_cells.create_index([("bounds", GEOSPHERE)])
    grid_cells.create_index([("center", GEOSPHERE)])
    grid_cells.create_index([("cell_x", ASCENDING), ("cell_y", ASCENDING)], unique=True)

    print("Indexes ensured: crimes.location (2dsphere), crimes.location_legacy (2d), "
          "crimes.(cell_x,cell_y), crimes.category, crimes.event_ts, "
          "grid_cells.bounds (2dsphere), grid_cells.center (2dsphere), "
          "grid_cells.(cell_x,cell_y) unique")


def load_crimes(db: Database, df: pd.DataFrame, batch_size: int) -> int:
    collection = db[config.COLLECTION_CRIMES]
    collection.delete_many({})  # idempotent re-runs: start clean each time

    docs = build_crime_documents(df)
    inserted = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)

    print(f"Inserted {inserted} documents into '{config.COLLECTION_CRIMES}'")
    return inserted


def load_grid_cells(db: Database, grid_cell_docs: list) -> int:
    collection = db[config.COLLECTION_GRID_CELLS]
    collection.delete_many({})

    if grid_cell_docs:
        collection.insert_many(grid_cell_docs, ordered=False)

    print(f"Inserted {len(grid_cell_docs)} documents into '{config.COLLECTION_GRID_CELLS}'")
    return len(grid_cell_docs)

"""
Central configuration. Edit this file (and your .env) to point at a
different dataset or Atlas cluster -- nothing else should need changes.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root, if present

# ---------------------------------------------------------------------------
# MongoDB Atlas connection
# ---------------------------------------------------------------------------
# NEVER hardcode your real connection string here. Set it in a .env file
# (see .env.example) or as a real environment variable.
MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("MONGO_DB_NAME", "crime_hotspot_db")

COLLECTION_CRIMES = "crimes"
COLLECTION_GRID_CELLS = "grid_cells"

# ---------------------------------------------------------------------------
# Input / output paths
# ---------------------------------------------------------------------------
INPUT_CSV_PATH = "data/crime_data.csv"
OUTPUT_DIR = "outputs"
CHARTS_DIR = "outputs/charts"

# ---------------------------------------------------------------------------
# Column mapping -- defaults match the City of Chicago "Crimes - 2001 to
# present" dataset (https://data.cityofchicago.org/.../ijzp-q8t2).
# Change these if you use a different source.
# ---------------------------------------------------------------------------
COLUMNS = {
    "id": "ID",
    "category": "Primary Type",
    "date": "Date",
    "latitude": "Latitude",
    "longitude": "Longitude",
}

# Python strptime format matching the dataset's date column.
# Chicago's format looks like: 01/23/2023 11:40:00 PM
DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"

# ---------------------------------------------------------------------------
# Spatial grid (same semantics as the Spark version)
# ---------------------------------------------------------------------------
GRID_CELL_SIZE_DEGREES = 0.01  # ~1.1 km at the equator
TOP_N_HOTSPOTS = 10

# ---------------------------------------------------------------------------
# Day / night split (24h clock)
# ---------------------------------------------------------------------------
DAY_START_HOUR = 6
NIGHT_START_HOUR = 18

# ---------------------------------------------------------------------------
# Coordinate validity bounds
# ---------------------------------------------------------------------------
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

# ---------------------------------------------------------------------------
# Spatial query defaults (used by src/spatial_queries.py demos in main.py)
# ---------------------------------------------------------------------------
PROXIMITY_INNER_RADIUS_M = 500     # buffer inner boundary, meters
PROXIMITY_OUTER_RADIUS_M = 1500    # buffer outer boundary, meters
KNN_DEFAULT_K = 10
KNN_JOIN_K = 3                     # neighbors per point for the KNN-join demo
KNN_JOIN_SAMPLE_SIZE = 25          # how many source points to run the join demo over (keeps the O(n) Mongo-call-per-point demo fast)

# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
INSERT_BATCH_SIZE = 2000

"""
FR-2: Data Cleaning

Standardizes column names, validates coordinates, parses dates, removes
duplicates, and reports how many records were removed and why.

Output schema (fixed internal names, regardless of the source dataset's
own column names):
    crime_id, category, raw_date, event_ts, latitude, longitude, has_valid_date
"""

import pandas as pd


def _require_columns(df: pd.DataFrame, columns: dict) -> None:
    missing = [
        col for key, col in columns.items()
        if key in ("category", "date", "latitude", "longitude") and col not in df.columns
    ]
    if missing:
        raise ValueError(
            f"Configured column(s) not found in dataset: {missing}. "
            f"Available columns: {list(df.columns)}. Update COLUMNS in config.py."
        )


def clean_data(df: pd.DataFrame, columns: dict, date_format: str,
               lat_min: float, lat_max: float,
               lon_min: float, lon_max: float) -> tuple[pd.DataFrame, dict]:
    _require_columns(df, columns)
    input_count = len(df)
    has_id = "id" in columns and columns["id"] in df.columns

    # --- Standardize column names -------------------------------------------
    std = pd.DataFrame({
        "crime_id": df[columns["id"]].astype(str) if has_id else df.index.astype(str),
        "category": df[columns["category"]],
        "raw_date": df[columns["date"]],
        "latitude": pd.to_numeric(df[columns["latitude"]], errors="coerce"),
        "longitude": pd.to_numeric(df[columns["longitude"]], errors="coerce"),
    })

    # --- Coordinate validation ------------------------------------------------
    before_coord_filter = len(std)
    coord_valid = (
        std["latitude"].notna() & std["longitude"].notna()
        & (std["latitude"] != 0.0) & (std["longitude"] != 0.0)  # drops common (0,0) null-island errors
        & std["latitude"].between(lat_min, lat_max)
        & std["longitude"].between(lon_min, lon_max)
    )
    with_valid_coords = std[coord_valid].copy()
    invalid_coord_count = before_coord_filter - len(with_valid_coords)

    # --- Parse dates (kept nullable; invalid/missing dates do not drop the row) --
    with_valid_coords["event_ts"] = pd.to_datetime(
        with_valid_coords["raw_date"], format=date_format, errors="coerce"
    )
    with_valid_coords["has_valid_date"] = with_valid_coords["event_ts"].notna()

    # --- Missing category -> explicit placeholder, not a dropped row ----------
    cat = with_valid_coords["category"].astype(str).str.strip().str.upper()
    cat = cat.where(cat.ne("") & cat.ne("NAN"), "UNKNOWN")
    with_valid_coords["category"] = cat

    # --- Deduplication ----------------------------------------------------------
    dedup_keys = ["crime_id"] if has_id else ["category", "raw_date", "latitude", "longitude"]
    before_dedup = len(with_valid_coords)
    cleaned = with_valid_coords.drop_duplicates(subset=dedup_keys).reset_index(drop=True)
    duplicate_count = before_dedup - len(cleaned)

    cleaned_count = len(cleaned)
    missing_date_count = int((~cleaned["has_valid_date"]).sum())

    stats = {
        "input_count": input_count,
        "invalid_coord_removed": invalid_coord_count,
        "duplicate_removed": duplicate_count,
        "cleaned_count": cleaned_count,
        "total_removed": input_count - cleaned_count,
        "missing_date_count": missing_date_count,
        "dedup_strategy": f"drop_duplicates on {dedup_keys}" + (" (source ID)" if has_id else " (no source ID; composite key used)"),
        "geo_coverage": (cleaned["latitude"].min(), cleaned["latitude"].max(),
                          cleaned["longitude"].min(), cleaned["longitude"].max()),
        "date_coverage": (cleaned["event_ts"].min(), cleaned["event_ts"].max()),
    }

    print("=" * 60)
    print("FR-2: DATA CLEANING")
    print("=" * 60)
    print(f"Input records:              {stats['input_count']}")
    print(f"Removed (invalid coords):   {stats['invalid_coord_removed']}")
    print(f"Removed (duplicates):       {stats['duplicate_removed']}  [{stats['dedup_strategy']}]")
    print(f"Cleaned records:            {stats['cleaned_count']}")
    print(f"  of which missing date:    {stats['missing_date_count']} (kept for spatial analysis, excluded from temporal)")
    print(f"Geo coverage (lat,lon):     {stats['geo_coverage']}")
    print(f"Date coverage:              {stats['date_coverage']}")
    print()

    return cleaned, stats

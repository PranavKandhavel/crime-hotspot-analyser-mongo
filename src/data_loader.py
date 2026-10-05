"""
FR-1: Data Loading

Loads the raw crime CSV with pandas (replacing the Spark DataFrame reader
from the earlier version -- there's no cluster to distribute this read
across, and pandas handles a tens-of-thousands-of-rows CSV comfortably in
memory on a laptop).
"""

import os
import pandas as pd


def load_crime_data(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at '{csv_path}'.\n"
            "Download a crime dataset with latitude/longitude columns "
            "(see README.md) and place it at this path, or update "
            "INPUT_CSV_PATH in config.py."
        )

    df = pd.read_csv(csv_path, low_memory=False)

    print("=" * 60)
    print("FR-1: DATA LOADING")
    print("=" * 60)
    print(f"Input file:        {csv_path}")
    print(f"Total input rows:  {len(df)}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print()

    return df

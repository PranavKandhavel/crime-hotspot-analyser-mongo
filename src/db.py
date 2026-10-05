"""
MongoDB Atlas connection handling.

All other modules get their database handle through get_db() -- nothing
else should call MongoClient() directly, so there's exactly one place
connection logic lives.
"""

from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

import config

_client = None


def get_client() -> MongoClient:
    global _client
    if _client is not None:
        return _client

    if not config.MONGO_URI:
        raise RuntimeError(
            "MONGO_URI is not set. Copy .env.example to .env and fill in "
            "your Atlas connection string (Atlas UI -> Connect -> Drivers -> Python)."
        )

    try:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=8000)
        _client.admin.command("ping")  # fail fast with a clear error, not a lazy timeout later
    except ConfigurationError as e:
        raise RuntimeError(
            f"Invalid MONGO_URI format: {e}\n"
            "Check for typos, and make sure any special characters in your "
            "password are URL-encoded (e.g. '@' -> '%40')."
        ) from e
    except ServerSelectionTimeoutError as e:
        raise RuntimeError(
            f"Could not reach your Atlas cluster: {e}\n"
            "Check: (1) your IP is allowed under Network Access in Atlas, "
            "(2) your cluster is running, (3) your username/password are correct."
        ) from e

    return _client


def get_db():
    return get_client()[config.DB_NAME]


def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None

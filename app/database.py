"""MongoDB connection lifecycle and index management.

The application creates one process-wide client and reuses it. Connection
pool sizes and timeouts intentionally stay at PyMongo defaults until the
deployment's measured concurrency is known; Atlas SRV/TLS settings belong in
MONGODB_URI. This module owns startup validation, indexes, and shutdown.
"""

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from app.config import settings

_client: MongoClient | None = None

ROLE_PROFILE_TTL_SECONDS = 7 * 24 * 60 * 60
JOB_SOURCE_CACHE_TTL_SECONDS = 6 * 60 * 60

# Every index maps to a real access path in the service layer. TTL indexes
# mirror the freshness checks in roleprofile/cache.py and discovery.py, so an
# expired document disappears even if the process is not running at expiry.
INDEXES: dict[str, list[tuple[str, dict]]] = {
    "users": [
        ("user_id", {"unique": True, "name": "users_user_id_unique"}),
        ("email", {"unique": True, "name": "users_email_unique"}),
    ],
    "analyses": [
        (
            "user_id",
            {
                "name": "analyses_user_created",
                "sort": {"user_id": ASCENDING, "created_at": DESCENDING},
            },
        ),
        ("resume_file_key", {"name": "analyses_resume_file_key"}),
    ],
    "role_profiles": [
        (
            "_expires_at",
            {
                "name": "role_profiles_expiry",
                "expireAfterSeconds": ROLE_PROFILE_TTL_SECONDS,
            },
        ),
    ],
    "job_source_cache": [
        (
            "_expires_at",
            {
                "name": "job_source_cache_expiry",
                "expireAfterSeconds": JOB_SOURCE_CACHE_TTL_SECONDS,
            },
        ),
    ],
    "discovery_runs": [
        (
            "user_id",
            {
                "name": "discovery_runs_user_created",
                "sort": {"user_id": ASCENDING, "created_at": DESCENDING},
            },
        ),
        ("analysis_id", {"name": "discovery_runs_analysis_id"}),
        (
            "target.role",
            {
                "name": "discovery_runs_cached_lookup",
                "sort": {
                    "target.role": ASCENDING,
                    "target.location": ASCENDING,
                    "created_at": DESCENDING,
                },
            },
        ),
    ],
    "api_quota": [
        (
            "source_period",
            {"unique": True, "name": "api_quota_source_period_unique"},
        ),
    ],
}


def get_database() -> Database:
    """Return the configured database, creating the shared client lazily."""
    global _client
    if settings.storage_backend != "mongodb":
        raise RuntimeError("MongoDB was requested while STORAGE_BACKEND is not 'mongodb'")

    if _client is None:
        if not settings.mongodb_uri.strip():
            raise RuntimeError(
                "MONGODB_URI is required when STORAGE_BACKEND=mongodb. "
                "Set the Atlas connection string in .env."
            )
        # No arbitrary pool/timeouts: the Atlas deployment's measured traffic
        # profile is not known yet, and URI/Atlas defaults are the safe base.
        _client = MongoClient(settings.mongodb_uri, tz_aware=True)
    return _client[settings.mongodb_database]


def ensure_indexes(database: Database | None = None) -> None:
    """Create the query and TTL indexes used by the application."""
    db = database or get_database()
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        for fields, options in indexes:
            collection.create_index(fields, **options)


def initialize_database() -> None:
    """Verify connectivity and ensure indexes during application startup."""
    database = get_database()
    database.command("ping")
    ensure_indexes(database)


def close_database() -> None:
    """Close the shared client during application shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None

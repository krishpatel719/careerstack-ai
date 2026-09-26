"""Persistent, MongoDB-backed job map fed by approved sources.

The map is a precomputed snapshot, not a provider proxy: scheduled ingestion
writes normalized postings, while HTTP map requests only read MongoDB. External
URLs are retained for users to open, but this module never scrapies rendered
LinkedIn, Naukri, or Indeed pages.
"""

import hashlib
import json
import logging
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pymongo import DESCENDING, GEOSPHERE, ReturnDocument, UpdateOne

from app.config import settings
from app.database import ensure_indexes, get_database
from app.models.resume import ParsedResume
from app.services import discovery
from app.services.discovery import generate_queries
from app.services.jobs.base import normalize_external_url, source_rank
from app.services.roleprofile.miner import posting_matches_role

logger = logging.getLogger(__name__)

JOBS_COLLECTION = "job_map_jobs"
SOURCES_COLLECTION = "job_map_job_sources"
RUNS_COLLECTION = "job_map_runs"
LOCKS_COLLECTION = "job_map_ingestion_locks"
LOCK_ID = "job-map-ingestion"
JOB_RETENTION_DAYS = 90
DEFAULT_INGEST_LIMIT = 2000
MAX_MAP_LIMIT = 500
DEFAULT_MAP_LIMIT = 250

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LOCATIONS_PAYLOAD = json.loads(
    (_DATA_DIR / "job_map_locations.json").read_text(encoding="utf-8")
)
_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")

_LOCATION_ALIASES: dict[str, dict] = {}
for _location in _LOCATIONS_PAYLOAD["locations"]:
    for _alias in _location["aliases"]:
        _LOCATION_ALIASES[_alias] = _location
# Longest aliases first: "new delhi" must win before a shorter overlap.
_SORTED_LOCATION_ALIASES = sorted(_LOCATION_ALIASES, key=len, reverse=True)


class JobMapUnavailableError(RuntimeError):
    """MongoDB is not configured or the map snapshot cannot be read."""


def _normalise_phrase(value: object) -> str:
    text = _PUNCTUATION_RE.sub(" ", str(value or "").lower())
    return _WHITESPACE_RE.sub(" ", text).strip()


def resolve_location(value: object) -> dict | None:
    """Resolve a provider location to one curated city, never by guesswork."""
    normalised = _normalise_phrase(value)
    if not normalised:
        return None
    for alias in _SORTED_LOCATION_ALIASES:
        if alias in normalised:
            location = _LOCATION_ALIASES[alias]
            longitude, latitude = location["coordinates"]
            return {
                "location_key": location["key"],
                "city": location["city"],
                "state": location["state"],
                "country": location["country"],
                "geo": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "location_quality": "curated",
            }
    return None


def canonical_job_id(
    title: str, company: str, location_key: str, raw_location: str
) -> str:
    """Stable location-aware identity used to merge provider copies."""
    company_key = _normalise_phrase(company)
    for suffix in (
        " private limited",
        " technologies",
        " technology",
        " solutions",
        " services",
        " systems",
        " software",
        " pvt ltd",
        " ltd",
        " llc",
        " inc",
    ):
        if company_key.endswith(suffix):
            company_key = company_key[: -len(suffix)].strip()
    canonical_location = location_key or _normalise_phrase(raw_location) or "unknown"
    raw = "|".join(
        (_normalise_phrase(title), company_key, canonical_location)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_key(posting: dict) -> str:
    external_id = posting.get("id")
    source = str(posting.get("source") or "external")
    if external_id:
        return f"{source}|{external_id}"
    fallback = "|".join(
        (
            _normalise_phrase(posting.get("title")),
            _normalise_phrase(posting.get("company")),
            str(posting.get("url") or ""),
        )
    )
    return f"{source}|fallback|{hashlib.sha256(fallback.encode('utf-8')).hexdigest()}"


def normalize_map_posting(
    posting: dict,
    *,
    target_role: str,
    now: datetime | None = None,
) -> dict | None:
    """One provider posting -> one public map document, or None if unusable."""
    if not posting_matches_role(posting, target_role):
        return None
    title = str(posting.get("title") or "").strip()
    company = str(posting.get("company") or "").strip()
    raw_location = str(posting.get("location") or "").strip()
    if not title or not company:
        return None

    safe_url = normalize_external_url(posting.get("url"))
    resolved = resolve_location(raw_location)
    location_key = resolved["location_key"] if resolved else ""
    seen_at = now or datetime.now(timezone.utc)
    job_id = canonical_job_id(title, company, location_key, raw_location)
    source = str(posting.get("source") or "external")
    document = {
        "_id": job_id,
        "job_id": job_id,
        "source_key": _source_key(posting),
        "external_id": str(posting["id"]) if posting.get("id") is not None else None,
        "title": title,
        "company": company,
        "company_key": _normalise_phrase(company),
        "location": raw_location or "Location not listed",
        "location_key": location_key or None,
        "city": resolved["city"] if resolved else None,
        "state": resolved["state"] if resolved else None,
        "country": resolved["country"] if resolved else "India",
        "location_quality": resolved["location_quality"] if resolved else "unmapped",
        "target_role": target_role.strip(),
        "source": source,
        "source_label": str(
            posting.get("source_label") or f"via {source.title()}"
        ),
        "url": safe_url,
        "description": str(posting.get("description") or ""),
        "description_truncated": bool(posting.get("description_truncated")),
        "is_remote": posting.get("is_remote"),
        "employment_type": posting.get("employment_type"),
        "salary_min": posting.get("salary_min"),
        "salary_max": posting.get("salary_max"),
        "salary_currency": posting.get("salary_currency"),
        "posted_at": posting.get("created"),
        "last_seen_at": seen_at.isoformat(),
        "active": True,
        "schema_version": 1,
        # TTL needs a BSON date. The public API continues to expose ISO time.
        "_expires_at": seen_at + timedelta(days=JOB_RETENTION_DAYS),
    }
    if resolved:
        document["geo"] = resolved["geo"]
    return document


def dedupe_map_postings(documents: list[dict]) -> list[dict]:
    """Prefer full first-party sources, then the fuller same-source copy."""
    by_id: dict[str, dict] = {}
    for document in documents:
        job_id = document["job_id"]
        current = by_id.get(job_id)
        if current is None:
            by_id[job_id] = document
            continue
        current_rank = source_rank(current.get("source"))
        candidate_rank = source_rank(document.get("source"))
        if candidate_rank < current_rank or (
            candidate_rank == current_rank
            and len(document.get("description") or "")
            > len(current.get("description") or "")
        ):
            by_id[job_id] = document
    return list(by_id.values())


def _require_mongodb() -> None:
    if settings.storage_backend != "mongodb":
        raise JobMapUnavailableError(
            "The job map requires MongoDB. Set STORAGE_BACKEND=mongodb and "
            "MONGODB_URI, then run the ingestion command."
        )


def acquire_ingestion_lock(owner: str, lease_minutes: int = 30) -> bool:
    _require_mongodb()
    now = datetime.now(timezone.utc)
    lease_until = now + timedelta(minutes=lease_minutes)
    database = get_database()
    ensure_indexes(database)
    lock = database[LOCKS_COLLECTION].find_one_and_update(
        {
            "_id": LOCK_ID,
            "$or": [
                {"lease_until": {"$lte": now}},
                {"owner": owner},
                {"lease_until": {"$exists": False}},
            ],
        },
        {
            "$set": {
                "owner": owner,
                "acquired_at": now,
                "lease_until": lease_until,
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return bool(lock and lock.get("owner") == owner)


def release_ingestion_lock(owner: str) -> None:
    if settings.storage_backend != "mongodb":
        return
    get_database()[LOCKS_COLLECTION].delete_one({"_id": LOCK_ID, "owner": owner})


def _bulk_upsert(
    collection,
    key_field: str,
    documents: list[dict],
    set_fields: dict,
    insert_fields: dict,
) -> None:
    """Use PyMongo bulk writes, with a compatible per-record fallback.

    Mongomock 4.3 does not yet implement every PyMongo 4.18 bulk-operation
    argument. Keeping the fallback here lets the exact repository contract be
    tested without weakening the production batch path.
    """
    if not documents:
        return
    updates = [
        UpdateOne(
            {key_field: document[key_field]},
            {"$set": set_fields(document), "$setOnInsert": insert_fields},
            upsert=True,
        )
        for document in documents
    ]
    try:
        collection.bulk_write(updates, ordered=False)
    except TypeError as exc:
        if "bulk" not in str(exc).lower() and "sort" not in str(exc).lower():
            raise
        for document in documents:
            collection.update_one(
                {key_field: document[key_field]},
                {"$set": set_fields(document), "$setOnInsert": insert_fields},
                upsert=True,
            )


async def ingest_targets(
    targets: list[dict], max_postings: int = DEFAULT_INGEST_LIMIT
) -> dict:
    """Fetch approved sources for configured targets and upsert a map snapshot."""
    _require_mongodb()
    enabled_targets = [
        target
        for target in targets
        if target.get("enabled", True)
        and str(target.get("role") or "").strip()
        and str(target.get("location") or "").strip()
    ]
    if not enabled_targets:
        return {"status": "complete", "upserted_jobs": 0, "targets": 0}

    owner = f"{socket.gethostname()}:{uuid.uuid4().hex}"
    if not acquire_ingestion_lock(owner):
        return {"status": "skipped", "reason": "another ingestion is running"}

    run_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc)
    database = get_database()
    runs = database[RUNS_COLLECTION]
    runs.insert_one(
        {
            "_id": run_id,
            "status": "running",
            "started_at": started_at.isoformat(),
            "targets": enabled_targets,
        }
    )

    all_documents: list[dict] = []
    source_counts: dict[str, int] = {}
    fetched = 0
    unmapped = 0
    try:
        for target in enabled_targets:
            role = str(target["role"]).strip()
            location = str(target["location"]).strip()
            queries = generate_queries(role, ParsedResume())
            # _gather_sources returns (postings, per-source counts) -- two
            # values, not three. The raw fetched count is just how many
            # postings came back before dedupe, so derive it here rather
            # than widening a signature that discovery.py also depends on.
            raw_postings, counts = await discovery._gather_sources(
                role, queries, location
            )
            fetched += len(raw_postings)
            for source, count in counts.items():
                source_counts[source] = source_counts.get(source, 0) + count

            documents = [
                normalize_map_posting(posting, target_role=role)
                for posting in raw_postings[:max_postings]
            ]
            valid = [document for document in documents if document is not None]
            unmapped += sum(
                1 for document in valid if document.get("location_quality") == "unmapped"
            )
            all_documents.extend(valid)

        deduplicated = dedupe_map_postings(all_documents)
        now = datetime.now(timezone.utc)
        first_seen = {"first_seen_at": now.isoformat()}
        _bulk_upsert(
            database[JOBS_COLLECTION],
            "_id",
            deduplicated,
            lambda document: {
                key: value for key, value in document.items() if key != "_id"
            },
            first_seen,
        )
        _bulk_upsert(
            database[SOURCES_COLLECTION],
            "source_key",
            deduplicated,
            lambda document: {
                "job_id": document["job_id"],
                "source": document["source"],
                "external_id": document.get("external_id"),
                "url": document.get("url"),
                "last_seen_at": now.isoformat(),
            },
            first_seen,
        )

        completed_at = datetime.now(timezone.utc)
        result = {
            "status": "complete",
            "run_id": run_id,
            "targets": len(enabled_targets),
            "fetched": fetched,
            "normalized": len(all_documents),
            "upserted_jobs": len(deduplicated),
            "unmapped_locations": unmapped,
            "by_source": source_counts,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }
        runs.update_one({"_id": run_id}, {"$set": result})
        return result
    except Exception as exc:
        logger.exception("Job-map ingestion failed")
        runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "Job-map ingestion failed. Check the server log.",
                }
            },
        )
        raise exc
    finally:
        release_ingestion_lock(owner)


def _public_job(document: dict | None) -> dict | None:
    if document is None:
        return None
    result = dict(document)
    for internal in (
        "_id",
        "external_id",
        "schema_version",
        "_expires_at",
        "source_key",
        "location_key",
        "active",
    ):
        result.pop(internal, None)
    geo = result.pop("geo", None)
    if isinstance(geo, dict):
        coordinates = geo.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2:
            result["longitude"], result["latitude"] = coordinates
    return result


def search_map(
    *,
    role: str | None = None,
    location: str | None = None,
    company: str | None = None,
    source: str | None = None,
    remote: bool | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
    limit: int = DEFAULT_MAP_LIMIT,
) -> dict:
    """Read the precomputed MongoDB snapshot. Never calls a job provider."""
    _require_mongodb()
    limit = max(1, min(int(limit), MAX_MAP_LIMIT))
    query: dict[str, Any] = {"active": True}
    and_conditions: list[dict] = []
    if role:
        pattern = re.compile(re.escape(role.strip()), re.IGNORECASE)
        and_conditions.append({"$or": [{"title": pattern}, {"target_role": pattern}]})
    if location:
        pattern = re.compile(re.escape(location.strip()), re.IGNORECASE)
        and_conditions.append({"$or": [{"location": pattern}, {"city": pattern}]})
    if and_conditions:
        query["$and"] = and_conditions
    if company:
        query["company"] = re.compile(re.escape(company.strip()), re.IGNORECASE)
    if source:
        query["source"] = source.strip().lower()
    if remote is not None:
        query["is_remote"] = remote
    if latitude is not None and longitude is not None:
        max_distance = max(1.0, min(float(radius_km or 100), 1000.0))
        query["geo"] = {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "$maxDistance": max_distance * 1000,
            }
        }

    database = get_database()
    documents = list(
        database[JOBS_COLLECTION]
        .find(query)
        .sort("last_seen_at", DESCENDING)
        .limit(limit)
    )
    jobs = [_public_job(document) for document in documents]
    last_run = database[RUNS_COLLECTION].find_one(
        {"status": "complete"}, sort=[("completed_at", DESCENDING)]
    )
    return {
        "jobs": jobs,
        "meta": {
            "count": len(jobs),
            "limit": limit,
            "mapped": sum(1 for job in jobs if job.get("latitude") is not None),
            "last_ingested_at": (last_run or {}).get("completed_at"),
        },
        "notice": (
            "Jobs come from configured APIs and official company ATS boards. "
            "CareerStack does not scrape LinkedIn, Naukri, or Indeed pages."
        ),
    }


def get_map_job(job_id: str) -> dict | None:
    _require_mongodb()
    if not re.fullmatch(r"[a-f0-9]{64}", job_id):
        return None
    return _public_job(get_database()[JOBS_COLLECTION].find_one({"_id": job_id}))

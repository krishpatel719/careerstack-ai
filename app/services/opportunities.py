"""Broad, resume-free job opportunity search.

This is the search/map layer that sits above the existing job-source
adapters. It searches the configured provider APIs and official ATS boards,
then returns normalized, deduplicated opportunities with source attribution.
It deliberately does not scrape arbitrary search-engine result pages.
"""

from datetime import datetime, timezone

from app.models.job import Job
from app.models.resume import ParsedResume
from app.services import discovery
from app.services.discovery import WIDEN_MIN_UNIQUE, WIDEN_TARGET, dedupe, generate_queries, rank_jobs


DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _clamp_limit(value: int) -> int:
    return max(1, min(int(value), MAX_LIMIT))


async def search_opportunities(role: str, location: str, limit: int = DEFAULT_LIMIT) -> dict:
    """Search configured job sources and return a client-safe opportunity feed.

    Ranking here is *opportunity ranking*, not resume matching: recency and
    location are useful before a user chooses an analysis, while keyword
    matching is deliberately left to discovery.py's resume-aware pipeline.
    """
    role = role.strip()
    location = location.strip()
    if not role:
        raise ValueError("A role is required.")
    if not location:
        location = WIDEN_TARGET

    limit = _clamp_limit(limit)
    queries = generate_queries(role, ParsedResume())
    jobs, source_counts, fetched = await discovery._fetch_queries(
        queries, location, role=role
    )
    unique_jobs, duplicates = dedupe(jobs)
    search_location = location
    widened = None

    if len(unique_jobs) < WIDEN_MIN_UNIQUE and location.lower() != WIDEN_TARGET.lower():
        reason = discovery._widen_reason(len(unique_jobs), location)
        wider_jobs, wider_counts, wider_fetched = await discovery._fetch_queries(
            queries, WIDEN_TARGET, role=role
        )
        fetched += wider_fetched
        for source_name, count in wider_counts.items():
            source_counts[source_name] = source_counts.get(source_name, 0) + count
        unique_jobs, duplicates = dedupe(jobs + wider_jobs)
        search_location = WIDEN_TARGET
        widened = {"from": location, "to": WIDEN_TARGET, "reason": reason}

    ranked = rank_jobs(unique_jobs, "", set(), search_location)
    total_seen = len(unique_jobs) + duplicates

    return {
        "target": {"role": role, "location": search_location},
        "requested_location": location,
        "queries": queries,
        "jobs": [job.model_dump() for job in ranked[:limit]],
        "stats": {
            "requested": len(queries),
            "fetched": fetched,
            "unique": len(unique_jobs),
            "returned": min(limit, len(ranked)),
            "duplicate_rate": round(duplicates / total_seen, 4) if total_seen else 0.0,
            "by_source": {**source_counts, "after_dedupe": len(unique_jobs)},
        },
        "widened": widened,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notice": (
            "Opportunities are collected from configured job APIs and official "
            "company ATS sources. External application links are provided for "
            "users to open; this service does not scrape search-engine pages."
        ),
    }

"""Lever public postings API adapter.

Lever exposes a public JSON board endpoint at /v0/postings/{company}. This
adapter only calls that official endpoint for tokens explicitly enabled in
app/data/lever_companies.json. It does not scrape the company's rendered
career page.
"""

import asyncio
import logging
from pathlib import Path
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.jobs.base import raw_posting
from app.services.jobs.public_ats import (
    REQUEST_HEADERS,
    clean_description,
    epoch_milliseconds_to_iso,
    is_retryable,
    load_company_tokens as load_tokens,
    matches_location,
    posting_list,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "lever"
BASE_URL = "https://api.lever.co/v0/postings/{token}"
REQUEST_TIMEOUT_SECONDS = 20.0
CONCURRENCY = 6

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_COMPANIES_FILE = _DATA_DIR / "lever_companies.json"


def load_company_tokens() -> list[str]:
    return load_tokens(_COMPANIES_FILE)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=is_retryable,
    reraise=True,
)
async def _get_board(client: httpx.AsyncClient, token: str) -> list[dict]:
    response = await client.get(
        BASE_URL.format(token=quote(token, safe="")),
        params={"mode": "json"},
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        response.raise_for_status()
    payload = response.json()
    return posting_list(payload)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _description(job: dict) -> str:
    # Lever's JSON mode provides descriptionPlain. Fall back to the HTML
    # field used by older/alternate responses and clean both to plain text.
    for value in (job.get("descriptionPlain"), job.get("description")):
        cleaned = clean_description(value)
        if cleaned:
            return cleaned
    return ""


def _normalise(job: dict, company_fallback: str) -> dict:
    raw_categories = job.get("categories")
    categories = raw_categories if isinstance(raw_categories, dict) else {}
    raw_id = job.get("id")
    external_id = str(raw_id) if isinstance(raw_id, (str, int, float)) and not isinstance(raw_id, bool) else None
    return raw_posting(
        source=SOURCE_NAME,
        external_id=external_id,
        title=_text(job.get("text")),
        company=_text(categories.get("team")) or company_fallback,
        location=_text(categories.get("location")),
        description=_description(job),
        category=_text(categories.get("department")),
        employment_type=_text(categories.get("commitment")),
        url=_text(job.get("hostedUrl")),
        created=epoch_milliseconds_to_iso(job.get("createdAt")),
    )


async def _fetch_one(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, token: str, location: str
) -> list[dict]:
    async with semaphore:
        try:
            jobs = await _get_board(client, token)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Lever board %r unavailable: %s", token, exc)
            return []

    return [
        _normalise(job, token)
        for job in posting_list(jobs)
        if matches_location(
            (job.get("categories") or {}).get("location")
            if isinstance(job.get("categories"), dict)
            else None,
            location,
        )
    ]


async def fetch(role: str, location: str, limit: int = 200) -> list[dict]:
    """Fetch enabled Lever boards matching the requested location.

    `role` is intentionally unused. Lever boards are small enough to fetch
    whole, and discovery ranks the resulting descriptions against the role.
    """
    tokens = load_company_tokens()
    if not tokens:
        return []

    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_one(client, semaphore, token, location) for token in tokens],
            return_exceptions=True,
        )

    collected: list[dict] = []
    for token, result in zip(tokens, results):
        if isinstance(result, BaseException):
            logger.warning("Lever board %r raised unexpectedly: %s", token, result)
            continue
        collected.extend(result)

    return collected[:limit]

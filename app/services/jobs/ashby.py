"""Ashby public job-board API adapter.

Ashby exposes a public JSON job-board endpoint for enabled board tokens. This
uses that official endpoint only; it does not scrape rendered career pages or
follow application URLs.
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
    is_retryable,
    load_company_tokens as load_tokens,
    matches_location,
    posting_list,
)

logger = logging.getLogger(__name__)

SOURCE_NAME = "ashby"
BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"
REQUEST_TIMEOUT_SECONDS = 20.0
CONCURRENCY = 6

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_COMPANIES_FILE = _DATA_DIR / "ashby_companies.json"


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
        params={"includeCompensation": "true"},
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return posting_list(payload.get("jobs"))
    return posting_list(payload)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _description(job: dict) -> str:
    for value in (job.get("descriptionHtml"), job.get("description")):
        cleaned = clean_description(value)
        if cleaned:
            return cleaned
    return ""


def _normalise(job: dict, company_fallback: str) -> dict:
    stated_remote = job.get("isRemote")
    is_remote = stated_remote if isinstance(stated_remote, bool) else None
    raw_id = job.get("id")
    external_id = str(raw_id) if isinstance(raw_id, (str, int, float)) and not isinstance(raw_id, bool) else None
    return raw_posting(
        source=SOURCE_NAME,
        external_id=external_id,
        title=_text(job.get("title")),
        company=(
            _text(job.get("companyName"))
            or _text(job.get("jobBoardName"))
            or company_fallback
        ),
        location=_text(job.get("location")),
        description=_description(job),
        category=_text(job.get("department")),
        employment_type=_text(job.get("employmentType")),
        is_remote=is_remote,
        url=_text(job.get("jobUrl")) or _text(job.get("applyUrl")),
        created=_text(job.get("publishedAt")),
    )


async def _fetch_one(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, token: str, location: str
) -> list[dict]:
    async with semaphore:
        try:
            jobs = await _get_board(client, token)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Ashby board %r unavailable: %s", token, exc)
            return []

    return [
        _normalise(job, token)
        for job in posting_list(jobs)
        if matches_location(job.get("location"), location)
    ]


async def fetch(role: str, location: str, limit: int = 200) -> list[dict]:
    """Fetch enabled Ashby boards matching the requested location.

    `role` is intentionally unused; discovery applies the resume-aware role
    ranking after all source adapters have normalised their postings.
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
            logger.warning("Ashby board %r raised unexpectedly: %s", token, result)
            continue
        collected.extend(result)

    return collected[:limit]

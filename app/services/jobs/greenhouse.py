"""Greenhouse job board adapter.

No API key, no quota, and it's the companies' own ATS -- so for the boards
in app/data/greenhouse_companies.json this is authoritative data rather
than an aggregator's copy. It only covers those companies, which is why it
sits below JSearch but above Adzuna in dedupe priority.

Descriptions come back as HTML-escaped markup (`&lt;div&gt;...`), not
plain text, and need unescaping and tag-stripping before the skill
extractor sees them -- otherwise every posting reads as a wall of markup.
Measured on a real board: 5913 characters of raw markup reduce to 4103
characters of usable text, still an order of magnitude more than Adzuna's
~500 character snippet.

Each board is one HTTP call, fanned out concurrently under a semaphore. A
company that 404s or times out contributes [] and the run continues.
"""

import asyncio
import html
import json
import logging
import re
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.jobs.base import id_or_none, raw_posting, text_or_none

logger = logging.getLogger(__name__)

SOURCE_NAME = "greenhouse"

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
REQUEST_TIMEOUT_SECONDS = 20.0
CONCURRENCY = 8

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_COMPANIES_FILE = _DATA_DIR / "greenhouse_companies.json"

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# City spellings that differ between what a user types and what boards
# publish. Greenhouse locations are free text written by each employer, so
# "Bangalore" (what people search) and "Bengaluru" (what boards say) never
# match on substring alone. Only genuine aliases for the same place --
# this is not a general synonym list.
_CITY_ALIASES = {
    "bangalore": ["bangalore", "bengaluru"],
    "bengaluru": ["bangalore", "bengaluru"],
    "bombay": ["bombay", "mumbai"],
    "mumbai": ["bombay", "mumbai"],
    "delhi": ["delhi", "new delhi", "ncr"],
    "new delhi": ["delhi", "new delhi", "ncr"],
    "gurgaon": ["gurgaon", "gurugram"],
    "gurugram": ["gurgaon", "gurugram"],
    "calcutta": ["calcutta", "kolkata"],
    "kolkata": ["calcutta", "kolkata"],
    "madras": ["madras", "chennai"],
    "chennai": ["madras", "chennai"],
    "poona": ["poona", "pune"],
    "pune": ["poona", "pune"],
    "trivandrum": ["trivandrum", "thiruvananthapuram"],
    "noida": ["noida", "greater noida"],
}

# Treated as "anywhere in the country", so a country-wide search keeps
# every India-located posting instead of matching the literal word.
_COUNTRY_WIDE = {"india", "in", "anywhere", ""}


def load_company_tokens() -> list[str]:
    """Board tokens from the curated file.

    Every token there was verified to return HTTP 200 -- see that file's
    _comment for why the originally-specified list could not be used as
    given (14 of its 15 entries 404'd).
    """
    try:
        payload = json.loads(_COMPANIES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Could not read %s: %s", _COMPANIES_FILE.name, exc)
        return []
    if not isinstance(payload, dict):
        return []
    entries = payload.get("companies")
    if not isinstance(entries, list):
        return []
    tokens: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        token = text_or_none(entry.get("token"))
        if token:
            tokens.append(token)
    return tokens


def clean_description(content: object) -> str:
    """HTML-escaped Greenhouse markup -> plain text.

    Unescape first, then strip tags: doing it the other way round leaves
    `&lt;div&gt;` untouched, since it isn't a tag until it's unescaped.
    """
    if not isinstance(content, str) or not content:
        return ""
    unescaped = html.unescape(content)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _location_terms(location: str) -> list[str]:
    normalised = (location or "").strip().lower()
    return _CITY_ALIASES.get(normalised, [normalised])


def matches_location(job_location: object, wanted: str) -> bool:
    """Case-insensitive city match against a board's free-text location.

    A country-wide search ("India") matches everything these boards
    return that is India-located; a city search matches that city or any
    known alias of it.
    """
    wanted_normalised = (wanted or "").strip().lower()
    haystack = job_location.lower() if isinstance(job_location, str) else ""

    if wanted_normalised in _COUNTRY_WIDE:
        return "india" in haystack

    return any(term and term in haystack for term in _location_terms(wanted_normalised))


def _is_retryable(exc: BaseException) -> bool:
    """Retry only transient board failures.

    A renamed board commonly returns 404 and a revoked/forbidden endpoint
    returns 401/403. Repeating those requests wastes time and can look like
    aggressive scraping. Timeouts, connection failures, rate limits, and
    5xx responses remain retryable.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in {408, 425, 429} or status >= 500
    return isinstance(exc, httpx.HTTPError)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=_is_retryable,
    reraise=True,
)
async def _get_board(client: httpx.AsyncClient, token: str) -> list[dict]:
    response = await client.get(
        BASE_URL.format(token=token), params={"content": "true"}, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def _normalise(job: dict, company_fallback: str) -> dict:
    raw_location = job.get("location")
    location = raw_location.get("name") if isinstance(raw_location, dict) else None
    raw_departments = job.get("departments")
    departments = raw_departments if isinstance(raw_departments, list) else []
    department_names = [
        name
        for department in departments
        if isinstance(department, dict)
        and (name := text_or_none(department.get("name")))
    ]
    return raw_posting(
        source=SOURCE_NAME,
        external_id=id_or_none(job.get("id")),
        title=job.get("title"),
        company=text_or_none(job.get("company_name")) or company_fallback,
        location=location,
        description=clean_description(job.get("content")),
        category=", ".join(department_names) or None,
        # Links back to the board itself, as the terms require.
        url=job.get("absolute_url"),
        created=text_or_none(job.get("first_published")) or text_or_none(
            job.get("updated_at")
        ),
    )


async def _fetch_one(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, token: str, location: str
) -> list[dict]:
    async with semaphore:
        try:
            jobs = await _get_board(client, token)
        except (httpx.HTTPError, ValueError) as exc:
            # A renamed or removed board 404s here. Log and contribute
            # nothing rather than failing the whole fan-out.
            logger.warning("Greenhouse board %r unavailable: %s", token, exc)
            return []

    normalised: list[dict] = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict):
            continue
        raw_location = job.get("location")
        job_location = raw_location.get("name") if isinstance(raw_location, dict) else None
        if not matches_location(job_location, location):
            continue
        try:
            normalised.append(_normalise(job, token))
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning("Skipping malformed Greenhouse posting on board %r: %s", token, exc)
    return normalised


async def fetch(role: str, location: str, limit: int = 200) -> list[dict]:
    """Every posting across the curated boards that matches `location`.

    `role` is deliberately unused for filtering: these boards are small
    enough to take whole, and discovery ranks by fit anyway -- pre-filtering
    on a title string here would drop a "Software Engineer II" posting from
    a "backend developer" search for no good reason.
    """
    tokens = load_company_tokens()
    if not isinstance(tokens, list) or not tokens:
        logger.warning("No Greenhouse company tokens configured -- source disabled")
        return []
    tokens = [token for token in tokens if isinstance(token, str) and token]

    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_fetch_one(client, semaphore, token, location) for token in tokens],
            return_exceptions=True,
        )

    collected: list[dict] = []
    for token, result in zip(tokens, results):
        if isinstance(result, BaseException):
            # _fetch_one already swallows the expected failures; this is
            # the belt-and-braces case for anything unforeseen.
            logger.warning("Greenhouse board %r raised unexpectedly: %s", token, result)
            continue
        if isinstance(result, list):
            collected.extend(posting for posting in result if isinstance(posting, dict))
        else:
            logger.warning("Greenhouse board %r returned a malformed result", token)

    return collected[:limit]

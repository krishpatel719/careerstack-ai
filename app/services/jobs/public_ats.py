"""Shared helpers for official public ATS job-board APIs.

These adapters call documented provider endpoints only. They do not fetch
arbitrary career-page HTML and never follow a job's application URL server
side; the URL is retained solely as a user-clickable source link.
"""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "CareerStackAI/0.1 (+https://github.com/krishpatel719/careerstack-ai)",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

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
_COUNTRY_WIDE = {"india", "in", "anywhere", ""}

# Indian places used to recognise a posting as India-located when the
# provider omits the country. Greenhouse and Ashby write "Bengaluru,
# India" or plain "India", so a substring check for "india" is enough for
# them -- but Lever writes "Noida, Uttar Pradesh" and "Mumbai,
# Maharashtra" with no country at all. Matching only the literal word
# therefore discarded every genuine Indian Lever posting: Paytm returned
# 174 jobs and contributed 0.
#
# States are included because a city list alone still misses smaller
# locations ("Vizag, Andhra Pradesh"). Matched on whole words so "pune"
# cannot fire inside an unrelated longer word.
_INDIA_PLACES = frozenset({
    # Metros and major tech hubs
    "bangalore", "bengaluru", "mumbai", "bombay", "delhi", "new delhi", "ncr",
    "gurgaon", "gurugram", "noida", "greater noida", "hyderabad", "chennai",
    "madras", "pune", "poona", "kolkata", "calcutta", "ahmedabad", "surat",
    "jaipur", "lucknow", "kanpur", "nagpur", "indore", "bhopal", "patna",
    "vadodara", "coimbatore", "kochi", "cochin", "trivandrum",
    "thiruvananthapuram", "chandigarh", "mysore", "mysuru", "visakhapatnam",
    "vizag", "bhubaneswar", "guwahati", "rajkot", "nashik", "ludhiana",
    # States and union territories
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim",
    "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
    "west bengal", "puducherry", "pondicherry",
})


def _is_india_located(haystack: str) -> bool:
    """Whether a free-text ATS location denotes somewhere in India.

    Checks the country word first, then falls back to recognising an
    Indian city or state for providers that omit the country entirely.
    """
    if "india" in haystack:
        return True
    return any(
        re.search(rf"(?<![a-z]){re.escape(place)}(?![a-z])", haystack)
        for place in _INDIA_PLACES
    )


def load_company_tokens(data_file: Path) -> list[str]:
    """Load enabled ATS board tokens from a curated local JSON file.

    A token is deliberately opt-in. The shipped files start empty; an
    operator adds only company boards whose provider terms and endpoint use
    have been reviewed. Invalid entries are ignored rather than allowed to
    break discovery.
    """
    try:
        payload = json.loads(data_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    entries = payload.get("companies", []) if isinstance(payload, dict) else []
    tokens: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("enabled") is False:
            continue
        raw_token = entry.get("token")
        if not isinstance(raw_token, str):
            continue
        token = raw_token.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def posting_list(value: object) -> list[dict]:
    """Return only posting objects from a provider's jobs collection.

    Public APIs and the cache are external input. A provider contract change
    that turns the collection into an object, or inserts a scalar entry, must
    invalidate that shape rather than raise while one source is being read.
    """
    if not isinstance(value, list):
        return []
    return [posting for posting in value if isinstance(posting, dict)]


def text_or_none(value: object) -> str | None:
    """Return a trimmed string, or None for malformed provider values."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def is_retryable(exc: BaseException) -> bool:
    """Retry transient provider failures, never permanent access errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in {408, 425, 429} or status >= 500
    return isinstance(exc, httpx.HTTPError)


def clean_description(content: object) -> str:
    """Turn ATS HTML or HTML-escaped markup into readable plain text.

    Non-string values are malformed provider data, not a reason to fail the
    whole board, so they contribute no description.
    """
    if not isinstance(content, str) or not content:
        return ""
    unescaped = html.unescape(content)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def matches_location(job_location: object, wanted: str) -> bool:
    """Match a public ATS's free-text location without broad title parsing."""
    wanted_normalised = (wanted or "").strip().lower()
    haystack = job_location.lower() if isinstance(job_location, str) else ""
    if wanted_normalised in _COUNTRY_WIDE:
        return _is_india_located(haystack)
    terms = _CITY_ALIASES.get(wanted_normalised, [wanted_normalised])
    return any(term and term in haystack for term in terms)


def epoch_milliseconds_to_iso(value: object) -> str | None:
    """Convert common ATS epoch-millisecond timestamps to ISO UTC."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None

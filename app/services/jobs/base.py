"""The adapter interface every job source implements.

A source takes a role, a location and a result budget, and returns raw
posting dicts in one common shape. Normalising *here* rather than in
discovery.py is the point of the interface: discovery stays unaware of
which provider a posting came from, so adding a fourth source later
touches this package and nothing else.

Two rules hold for every adapter, and the pipeline depends on both:

1. Never raise. A dead or rate-limited source returns [] and logs. One
   source failing must not cost the user their other results -- the same
   rule CLAUDE.md already states for job sources.
2. Always stamp `source` with the adapter's own SOURCE_NAME, since dedupe
   priority in discovery.py is decided by that field.
"""

import logging
import math
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# Dedupe priority when the same posting arrives from several sources,
# best first. Full-description providers come before snippet-only Adzuna.
# Official company ATS sources stay ahead of the broad aggregator because
# their URLs and descriptions are first-party data.
SOURCE_PRIORITY = ["jsearch", "greenhouse", "lever", "ashby", "adzuna"]


def source_rank(source: str | None) -> int:
    """Lower is better. An unknown source sorts last rather than raising,
    so a future adapter that forgets to register here degrades instead of
    breaking dedupe.
    """
    try:
        return SOURCE_PRIORITY.index(source or "")
    except ValueError:
        return len(SOURCE_PRIORITY)


def text_or_none(value: object) -> str | None:
    """Return a trimmed provider string, or ``None`` for malformed data.

    Provider JSON is untrusted input.  In particular, a list or object in a
    field that the common posting schema describes as text must not escape
    into Pydantic validation (or, worse, be rendered as a link/value).
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def number_or_none(value: object) -> float | int | None:
    """Return a finite numeric provider value, or ``None`` if malformed."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def id_or_none(value: object) -> str | None:
    """Return a provider identifier as text without accepting containers."""
    if isinstance(value, str):
        return text_or_none(value)
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        return str(value)
    return None


def normalize_external_url(value: object) -> str | None:
    """Return a trimmed absolute HTTP(S) URL, or ``None`` if unsafe/invalid.

    Provider payloads and cached runs are external input. Rendering a value
    such as ``javascript:`` directly would turn a "View posting" link into
    code execution, while a relative value could be silently re-pointed at
    this application. Keep the allow-list identical at the adapter and
    discovery boundaries.
    """
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if (
        not candidate
        or "\\" in candidate
        or any(ord(char) < 32 or ord(char) == 127 for char in candidate)
    ):
        return None

    try:
        parsed = urlsplit(candidate)
        # Accessing port also validates it (e.g. rejects a bad numeric port).
        _ = parsed.port
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return None

    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


class JobSource(Protocol):
    """Structural interface -- adapters are plain modules, not classes, so
    this documents and type-checks the shape without forcing inheritance.
    """

    SOURCE_NAME: str

    async def fetch(self, role: str, location: str, limit: int) -> list[dict]:
        ...


# Display credit per source. Each provider's terms require attribution, so
# the label travels with the posting rather than being inferred in the UI.
SOURCE_LABELS = {
    "jsearch": "via JSearch",
    "greenhouse": "via Greenhouse",
    "lever": "via Lever",
    "ashby": "via Ashby",
    "adzuna": "via Adzuna",
}


def default_source_label(source: str | None) -> str:
    return SOURCE_LABELS.get(source or "", f"via {source}" if source else "via an external board")


def raw_posting(
    *,
    source: str,
    external_id: str | None,
    title: str | None,
    company: str | None,
    location: str | None,
    description: str | None,
    url: str | None,
    created: str | None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    salary_currency: str | None = None,
    category: str | None = None,
    source_label: str | None = None,
    is_remote: bool | None = None,
    employment_type: str | None = None,
) -> dict:
    """The common raw-posting shape, built in one place.

    Keyword-only on purpose: these are mostly-optional string fields, and
    positional calls across adapters would be a silent field-swap
    waiting to happen.

    Field names match what discovery.normalise_posting() already reads
    from Adzuna payloads, so existing callers need no changes.

    is_remote is a tri-state: True/False when the provider states it
    (JSearch does, via job_is_remote), None when it doesn't. None means
    "unknown", and discovery falls back to sniffing the text for it --
    passing False there would assert something the provider never said.
    """
    source_name = text_or_none(source) or "external"
    source_text = text_or_none(source_label) or default_source_label(source_name)
    return {
        "id": id_or_none(external_id),
        "source": source_name,
        "source_label": source_text,
        "title": text_or_none(title),
        "company": text_or_none(company),
        "location": text_or_none(location),
        "description": description if isinstance(description, str) else "",
        # This is a property of the provider's response contract, not the
        # description's length: only Adzuna's free tier returns a snippet.
        "description_truncated": source_name == "adzuna",
        "category": text_or_none(category),
        "employment_type": text_or_none(employment_type),
        "is_remote": is_remote if isinstance(is_remote, bool) else None,
        "url": normalize_external_url(url),
        "created": text_or_none(created),
        "salary_min": number_or_none(salary_min),
        "salary_max": number_or_none(salary_max),
        "salary_currency": text_or_none(salary_currency),
    }

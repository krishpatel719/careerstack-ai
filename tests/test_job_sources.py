"""Tests for the job source adapters and the multi-source fan-out.

No network: each adapter's HTTP layer is stubbed with a payload in the
real provider's shape (captured from live responses while building these
adapters), and the point is the normalisation, the fan-out resilience and
the dedupe priority -- not the providers themselves.
"""

import httpx
import pytest

from app.services import discovery
from app.services.jobs import adzuna_source, ashby, greenhouse, jsearch, lever
from app.services.jobs.base import SOURCE_PRIORITY, raw_posting, source_rank

# --------------------------------------------------------------------------
# Common shape
# --------------------------------------------------------------------------

COMMON_FIELDS = {
    "id", "source", "source_label", "title", "company", "location", "description",
    "description_truncated", "category", "employment_type", "is_remote", "url", "created",
    "salary_min", "salary_max", "salary_currency",
}


def test_raw_posting_has_the_common_field_set():
    posting = raw_posting(
        source="adzuna",
        external_id="1",
        title="Backend Developer",
        company="Acme",
        location="Pune",
        description="text",
        url="https://example.test",
        created="2026-09-01T00:00:00Z",
    )
    assert set(posting.keys()) == COMMON_FIELDS


def test_source_priority_prefers_full_description_official_sources():
    assert SOURCE_PRIORITY == ["jsearch", "greenhouse", "lever", "ashby", "adzuna"]
    assert source_rank("jsearch") < source_rank("greenhouse")
    assert source_rank("greenhouse") < source_rank("lever")
    assert source_rank("lever") < source_rank("ashby") < source_rank("adzuna")


def test_unknown_source_sorts_last_rather_than_raising():
    assert source_rank("some-future-source") > source_rank("adzuna")
    assert source_rank(None) > source_rank("adzuna")


@pytest.mark.parametrize(
    "url",
    ["https://example.test/jobs/1", "http://example.test/jobs/1", "  https://example.test/job  "],
)
def test_raw_posting_keeps_only_absolute_http_urls(url):
    posting = raw_posting(
        source="jsearch", external_id="1", title="Dev", company="Acme",
        location="Pune", description="text", url=url, created=None,
    )
    assert posting["url"] == url.strip()


@pytest.mark.parametrize(
    "url",
    [None, "", "/jobs/1", "//evil.test/jobs/1", "javascript:alert(1)", "data:text/html,bad", "mailto:jobs@example.test"],
)
def test_raw_posting_discards_unsafe_or_relative_urls(url):
    posting = raw_posting(
        source="jsearch", external_id="1", title="Dev", company="Acme",
        location="Pune", description="text", url=url, created=None,
    )
    assert posting["url"] is None


def test_raw_posting_marks_truncation_from_the_source_contract():
    common = dict(
        external_id="1", title="Dev", company="Acme", location="Pune",
        description="text", url="https://example.test/job", created=None,
    )
    assert raw_posting(source="adzuna", **common)["description_truncated"] is True
    assert raw_posting(source="jsearch", **common)["description_truncated"] is False
    assert raw_posting(source="greenhouse", **common)["description_truncated"] is False
    assert raw_posting(source="lever", **common)["description_truncated"] is False
    assert raw_posting(source="ashby", **common)["description_truncated"] is False


def test_stored_job_validation_repairs_unsafe_cached_links_and_source_metadata():
    job = discovery.normalise_stored_job(
        {
            "fingerprint": "cached-1",
            "source": "jsearch",
            "url": "javascript:alert(1)",
            "meta": {"description_truncated": True},
        }
    )

    assert job.url is None
    assert job.meta.description_truncated is False


# --------------------------------------------------------------------------
# Adzuna adapter
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_adzuna_adapter_normalises_to_the_common_schema(monkeypatch):
    async def fake_search(query, location, limit, country="in", page=1):
        if page > 1:
            return []
        return [
            {
                "id": 123,
                "title": "Backend Developer",
                "company": "Acme Pvt Ltd",
                "location": "Ahmedabad, Gujarat",
                "description": "Python and Django required.",
                "category": "IT Jobs",
                "url": "https://adzuna.test/job/123",
                "created": "2026-09-20T10:00:00Z",
                "salary_min": 600000.0,
                "salary_max": 900000.0,
            }
        ]

    monkeypatch.setattr(adzuna_source, "adzuna_search", fake_search)
    postings = await adzuna_source.fetch("backend developer", "Ahmedabad")

    assert len(postings) == 1
    posting = postings[0]
    assert set(posting.keys()) == COMMON_FIELDS
    assert posting["source"] == "adzuna"
    assert posting["id"] == "123"
    assert posting["title"] == "Backend Developer"
    assert posting["description_truncated"] is True
    assert posting["salary_currency"] == "INR"


@pytest.mark.anyio
async def test_adzuna_adapter_reports_no_currency_when_there_is_no_salary(monkeypatch):
    async def fake_search(query, location, limit, country="in", page=1):
        if page > 1:
            return []
        return [{"id": 1, "title": "Dev", "company": "Acme", "location": "Pune",
                 "description": "x", "url": "u", "created": "c",
                 "salary_min": None, "salary_max": None}]

    monkeypatch.setattr(adzuna_source, "adzuna_search", fake_search)
    postings = await adzuna_source.fetch("dev", "Pune")
    assert postings[0]["salary_currency"] is None


# --------------------------------------------------------------------------
# JSearch adapter
# --------------------------------------------------------------------------


# One entry from a real JSearch `data` array, trimmed to the fields read.
JSEARCH_PAYLOAD = {
    "data": [
        {
            "job_id": "abc123",
            "job_title": "Senior Backend Engineer",
            "employer_name": "Globex",
            "job_city": "Bengaluru",
            "job_state": "Karnataka",
            "job_country": "IN",
            "job_description": "Full description text, not a truncated snippet. " * 20,
            "job_apply_link": "https://jsearch.test/job/abc123",
            "job_posted_at_datetime_utc": "2026-09-18T08:00:00.000Z",
            "job_min_salary": 1800000,
            "job_max_salary": 2600000,
            "job_salary_currency": "INR",
            "job_employment_type": "FULLTIME",
            "job_is_remote": False,
        }
    ]
}


@pytest.mark.anyio
async def test_jsearch_adapter_normalises_to_the_common_schema(monkeypatch):
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")

    async def fake_get(params, headers):
        assert headers["X-RapidAPI-Host"] == "jsearch.p.rapidapi.com"
        assert headers["X-RapidAPI-Key"] == "test-key"
        assert params["query"] == "backend developer in Bengaluru"
        assert params["date_posted"] == "month"
        return httpx.Response(200, json=JSEARCH_PAYLOAD)

    monkeypatch.setattr(jsearch, "_get", fake_get)
    postings = await jsearch.fetch("backend developer", "Bengaluru")

    assert len(postings) == 1
    posting = postings[0]
    assert set(posting.keys()) == COMMON_FIELDS
    assert posting["source"] == "jsearch"
    assert posting["company"] == "Globex"
    assert posting["location"] == "Bengaluru, Karnataka"
    assert posting["salary_currency"] == "INR"
    assert posting["employment_type"] == "FULLTIME"
    assert posting["is_remote"] is False
    # Terms attribution travels with the posting.
    assert posting["source_label"] == "via JSearch"
    # The reason this source outranks the others.
    assert len(posting["description"]) > 500
    assert posting["description_truncated"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [None, [], "not-an-object", 42])
async def test_jsearch_rejects_malformed_top_level_payloads(payload, monkeypatch):
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda *a, **k: 1)

    async def fake_get(params, headers):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(jsearch, "_get", fake_get)
    assert await jsearch.fetch("backend developer", "India") == []


@pytest.mark.anyio
async def test_jsearch_skips_malformed_items_and_keeps_valid_ones(monkeypatch):
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda *a, **k: 1)

    malformed = {
        "job_id": [],
        "job_title": {},
        "employer_name": [],
        "job_city": {},
        "job_state": [],
        "job_country": 42,
        "job_description": {},
        "job_apply_link": [],
        "job_posted_at_datetime_utc": {},
        "job_min_salary": {},
        "job_max_salary": [],
        "job_salary_currency": {},
        "job_employment_type": [{}, 3],
        "job_is_remote": "false",
    }
    payload = {"data": [malformed, None, "not-an-object", JSEARCH_PAYLOAD["data"][0]]}

    async def fake_get(params, headers):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(jsearch, "_get", fake_get)
    postings = await jsearch.fetch("backend developer", "Bengaluru")

    assert len(postings) == 1
    assert postings[0]["source"] == "jsearch"
    assert postings[0]["source_label"] == "via JSearch"
    assert postings[0]["title"] == "Senior Backend Engineer"
    assert postings[0]["description_truncated"] is False


def test_jsearch_preserves_a_missing_remote_flag_as_unknown():
    posting = dict(JSEARCH_PAYLOAD["data"][0])
    posting.pop("job_is_remote")

    normalised = jsearch._normalise(posting)

    assert normalised["is_remote"] is None


@pytest.mark.anyio
async def test_jsearch_without_an_api_key_returns_empty_and_does_not_raise(monkeypatch):
    """The configured state in this repo: RAPIDAPI_KEY is empty, so this
    path runs on every discovery call and must be silent and harmless.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "")

    async def exploding_get(params, headers):
        raise AssertionError("must not make a request without a key")

    monkeypatch.setattr(jsearch, "_get", exploding_get)

    assert await jsearch.fetch("backend developer", "India") == []
    assert jsearch.is_configured() is False


@pytest.mark.anyio
async def test_jsearch_rate_limit_returns_empty_rather_than_raising(monkeypatch):
    """429 is expected on a ~200 call/month tier and must not fail a run."""
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")

    async def rate_limited(params, headers):
        raise httpx.HTTPStatusError(
            "429", request=httpx.Request("GET", "https://x"), response=httpx.Response(429)
        )

    monkeypatch.setattr(jsearch, "_get", rate_limited)
    assert await jsearch.fetch("backend developer", "India") == []


# --------------------------------------------------------------------------
# Greenhouse adapter
# --------------------------------------------------------------------------


def test_greenhouse_retries_only_transient_http_failures():
    def status_error(status):
        return httpx.HTTPStatusError(
            str(status),
            request=httpx.Request("GET", "https://boards-api.greenhouse.io/"),
            response=httpx.Response(status),
        )

    assert greenhouse._is_retryable(status_error(404)) is False
    assert greenhouse._is_retryable(status_error(401)) is False
    assert greenhouse._is_retryable(status_error(403)) is False
    assert greenhouse._is_retryable(status_error(429)) is True
    assert greenhouse._is_retryable(status_error(503)) is True
    assert greenhouse._is_retryable(httpx.ReadTimeout("timed out")) is True


def test_greenhouse_unescapes_and_strips_html_from_descriptions():
    """Boards return HTML-escaped markup. Unescaping must happen before
    tag-stripping, or `&lt;div&gt;` survives as literal text.
    """
    raw = "&lt;div&gt;&lt;strong&gt;About:&lt;/strong&gt;&lt;/div&gt;\n&lt;p&gt;We use Python.&lt;/p&gt;"
    cleaned = greenhouse.clean_description(raw)

    assert "<" not in cleaned and "&lt;" not in cleaned
    assert "About:" in cleaned
    assert "We use Python." in cleaned


def test_greenhouse_clean_description_handles_empty_input():
    assert greenhouse.clean_description(None) == ""
    assert greenhouse.clean_description("") == ""


@pytest.mark.parametrize(
    "job_location, wanted",
    [
        ("Bengaluru, India", "bangalore"),
        ("Bengaluru, India", "BANGALORE"),
        ("Bengaluru, India", "Bengaluru"),
        ("BENGALURU, INDIA", "bangalore"),
        ("Mumbai, India", "mumbai"),
        ("Mumbai, India", "Bombay"),
        ("Gurugram, India", "gurgaon"),
        ("Pune, India", "PUNE"),
    ],
)
def test_greenhouse_city_filter_is_case_insensitive(job_location, wanted):
    assert greenhouse.matches_location(job_location, wanted) is True


def test_greenhouse_city_filter_rejects_a_different_city():
    assert greenhouse.matches_location("Bengaluru, India", "Ahmedabad") is False
    assert greenhouse.matches_location("New York, USA", "Mumbai") is False


def test_greenhouse_country_wide_search_matches_any_india_location():
    assert greenhouse.matches_location("Bengaluru, India", "India") is True
    assert greenhouse.matches_location("Mumbai, India", "india") is True
    # A non-India posting on the same board is excluded.
    assert greenhouse.matches_location("San Francisco, USA", "India") is False


GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "id": 4970739101,
            "title": "Backend Engineer",
            "location": {"name": "Bengaluru, India"},
            "content": "&lt;div&gt;We use Python and Django.&lt;/div&gt;",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/4970739101",
            "first_published": "2026-09-14T03:49:28-04:00",
            "updated_at": "2026-09-14T03:52:53-04:00",
            "company_name": "Acme",
            "departments": [{"name": "Engineering"}],
        },
        {
            "id": 2,
            "title": "Sales Lead",
            "location": {"name": "San Francisco, USA"},
            "content": "&lt;p&gt;Not in India.&lt;/p&gt;",
            "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/2",
            "first_published": "2026-09-10T00:00:00-04:00",
            "company_name": "Acme",
            "departments": [],
        },
    ]
}


@pytest.mark.anyio
async def test_greenhouse_adapter_normalises_and_filters_by_location(monkeypatch):
    monkeypatch.setattr(greenhouse, "load_company_tokens", lambda: ["acme"])

    async def fake_get_board(client, token):
        return GREENHOUSE_PAYLOAD["jobs"]

    monkeypatch.setattr(greenhouse, "_get_board", fake_get_board)
    postings = await greenhouse.fetch("backend developer", "Bangalore")

    assert len(postings) == 1  # the SF posting is filtered out
    posting = postings[0]
    assert set(posting.keys()) == COMMON_FIELDS
    assert posting["source"] == "greenhouse"
    assert posting["title"] == "Backend Engineer"
    assert "We use Python and Django." in posting["description"]
    assert posting["description_truncated"] is False
    # Terms compliance: links back to the board.
    assert posting["url"].startswith("https://job-boards.greenhouse.io/")


@pytest.mark.anyio
async def test_greenhouse_one_failing_board_does_not_kill_the_fan_out(monkeypatch):
    monkeypatch.setattr(greenhouse, "load_company_tokens", lambda: ["dead", "alive"])

    async def fake_get_board(client, token):
        if token == "dead":
            raise httpx.HTTPStatusError(
                "404", request=httpx.Request("GET", "https://x"), response=httpx.Response(404)
            )
        return GREENHOUSE_PAYLOAD["jobs"]

    monkeypatch.setattr(greenhouse, "_get_board", fake_get_board)
    postings = await greenhouse.fetch("backend developer", "India")

    # The live board still contributed despite the dead one.
    assert len(postings) == 1
    assert postings[0]["company"] == "Acme"


@pytest.mark.anyio
async def test_greenhouse_with_no_configured_tokens_returns_empty(monkeypatch):
    monkeypatch.setattr(greenhouse, "load_company_tokens", lambda: [])
    assert await greenhouse.fetch("backend developer", "India") == []


def test_every_shipped_greenhouse_token_is_a_nonempty_string():
    tokens = greenhouse.load_company_tokens()
    assert tokens, "the curated company list should not be empty"
    assert all(isinstance(token, str) and token for token in tokens)
    assert len(tokens) == len(set(tokens)), "duplicate board tokens"


# --------------------------------------------------------------------------
# Public ATS adapters
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_lever_adapter_normalises_official_public_board_payload(monkeypatch):
    monkeypatch.setattr(lever, "load_company_tokens", lambda: ["acme"])

    async def fake_get_board(client, token):
        assert token == "acme"
        return [
            {
                "id": "lever-123",
                "text": "Backend Engineer",
                "hostedUrl": "https://jobs.lever.co/acme/lever-123",
                "createdAt": 1760000000000,
                "categories": {
                    "team": "Acme",
                    "location": "Bengaluru, India",
                    "department": "Engineering",
                    "commitment": "Full-time",
                },
                "description": "<p>Build Python APIs.</p>",
            }
        ]

    monkeypatch.setattr(lever, "_get_board", fake_get_board)
    postings = await lever.fetch("backend developer", "Bangalore")

    assert len(postings) == 1
    posting = postings[0]
    assert set(posting.keys()) == COMMON_FIELDS
    assert posting["source"] == "lever"
    assert posting["source_label"] == "via Lever"
    assert posting["description"] == "Build Python APIs."
    assert posting["description_truncated"] is False
    assert posting["created"].endswith("+00:00")


@pytest.mark.anyio
async def test_ashby_adapter_normalises_official_public_board_payload(monkeypatch):
    monkeypatch.setattr(ashby, "load_company_tokens", lambda: ["acme"])

    async def fake_get_board(client, token):
        assert token == "acme"
        return [
            {
                "id": "ashby-123",
                "title": "Python Developer",
                "companyName": "Acme",
                "location": "Pune, India",
                "descriptionHtml": "<div>Use FastAPI.</div>",
                "jobUrl": "https://jobs.ashbyhq.com/acme/ashby-123",
                "publishedAt": "2026-09-20T10:00:00Z",
                "employmentType": "Full-time",
                "isRemote": False,
            }
        ]

    monkeypatch.setattr(ashby, "_get_board", fake_get_board)
    postings = await ashby.fetch("python developer", "Pune")

    assert len(postings) == 1
    posting = postings[0]
    assert set(posting.keys()) == COMMON_FIELDS
    assert posting["source"] == "ashby"
    assert posting["source_label"] == "via Ashby"
    assert posting["description"] == "Use FastAPI."
    assert posting["description_truncated"] is False
    assert posting["is_remote"] is False


def test_public_ats_company_files_load_only_unique_enabled_tokens():
    for tokens in (lever.load_company_tokens(), ashby.load_company_tokens()):
        assert all(isinstance(token, str) and token for token in tokens)
        assert len(tokens) == len(set(tokens))


@pytest.mark.anyio
@pytest.mark.parametrize("module", [lever, ashby])
async def test_empty_public_ats_config_disables_source_without_network(module, monkeypatch):
    async def exploding_get_board(client, token):
        raise AssertionError("an empty curated config must make no provider call")

    monkeypatch.setattr(module, "_get_board", exploding_get_board)

    assert await module.fetch("backend developer", "India") == []


class _ShapeResponseClient:
    def __init__(self, payload):
        self.payload = payload

    async def get(self, *args, **kwargs):
        request = httpx.Request("GET", "https://provider.test/board")
        if self.payload is None:
            return httpx.Response(200, content=b"null", request=request)
        return httpx.Response(200, json=self.payload, request=request)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("module", "payload"),
    [
        (lever, {"unexpected": "not-a-list"}),
        (lever, [None, "not-an-object"]),
        (ashby, {"jobs": "not-a-list"}),
        (ashby, {"jobs": [None, "not-an-object"]}),
    ],
)
async def test_public_ats_get_board_rejects_malformed_payload_shapes(module, payload):
    assert await module._get_board(_ShapeResponseClient(payload), "acme") == []


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [None, [], "not-an-object", 42])
async def test_greenhouse_rejects_malformed_top_level_payloads(payload):
    assert await greenhouse._get_board(_ShapeResponseClient(payload), "acme") == []


@pytest.mark.anyio
async def test_greenhouse_skips_malformed_items_and_nested_fields(monkeypatch):
    monkeypatch.setattr(greenhouse, "load_company_tokens", lambda: ["acme"])
    malformed_but_located = {
        "id": {},
        "title": [],
        "location": {"name": "Pune, India"},
        "content": {"unexpected": "shape"},
        "absolute_url": [],
        "company_name": {},
        "departments": [{"name": []}, None, {"name": "Engineering"}],
        "first_published": {},
    }
    valid = dict(GREENHOUSE_PAYLOAD["jobs"][0])
    valid["id"] = "greenhouse-valid"
    valid["location"] = {"name": "Pune, India"}

    async def fake_get_board(client, token):
        return [malformed_but_located, None, "not-an-object", valid]

    monkeypatch.setattr(greenhouse, "_get_board", fake_get_board)
    postings = await greenhouse.fetch("backend developer", "Pune")

    assert len(postings) == 2
    malformed_result, valid_result = postings
    assert malformed_result["source"] == "greenhouse"
    assert malformed_result["id"] is None
    assert malformed_result["title"] is None
    assert malformed_result["description"] == ""
    assert malformed_result["company"] == "acme"
    assert malformed_result["description_truncated"] is False
    assert valid_result["id"] == "greenhouse-valid"
    assert valid_result["title"] == "Backend Engineer"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("module", "job"),
    [
        (
            lever,
            {
                "id": {},
                "text": [],
                "categories": {
                    "location": "Pune, India",
                    "team": [],
                    "department": {},
                    "commitment": 123,
                },
                "description": {"unexpected": "shape"},
                "hostedUrl": 123,
                "createdAt": "not-an-epoch",
            },
        ),
        (
            ashby,
            {
                "id": {},
                "title": [],
                "companyName": {},
                "location": "Pune, India",
                "descriptionHtml": 123,
                "jobUrl": [],
                "publishedAt": {},
                "isRemote": "false",
            },
        ),
    ],
)
async def test_public_ats_adapter_never_raises_on_malformed_posting_fields(
    module, job, monkeypatch
):
    monkeypatch.setattr(module, "load_company_tokens", lambda: ["acme"])

    async def fake_get_board(client, token):
        return [job]

    monkeypatch.setattr(module, "_get_board", fake_get_board)
    postings = await module.fetch("backend developer", "Pune")

    # A posting that still has a usable location is retained with optional
    # malformed fields coerced to their unknown values; it never escapes as
    # a list/dict where the common schema promises text or None.
    assert len(postings) == 1
    assert set(postings[0]) == COMMON_FIELDS
    posting = postings[0]
    assert posting["description"] == ""
    assert all(
        posting[key] is None
        for key in {"id", "title", "category", "employment_type", "created"}
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("module", "job"),
    [
        (
            lever,
            {
                "id": "lever-live",
                "text": "Backend Engineer",
                "categories": {"location": "Pune, India"},
                "description": "Full Lever description.",
            },
        ),
        (
            ashby,
            {
                "id": "ashby-live",
                "title": "Backend Engineer",
                "location": "Pune, India",
                "descriptionHtml": "Full Ashby description.",
            },
        ),
    ],
)
async def test_one_failing_public_ats_board_does_not_kill_healthy_board(
    module, job, monkeypatch
):
    monkeypatch.setattr(module, "load_company_tokens", lambda: ["dead", "alive"])

    async def fake_get_board(client, token):
        if token == "dead":
            raise httpx.ReadTimeout("timed out")
        return [job]

    monkeypatch.setattr(module, "_get_board", fake_get_board)

    postings = await module.fetch("backend developer", "Pune")

    assert len(postings) == 1
    assert postings[0]["source"] == module.SOURCE_NAME


def _stub_sources(
    monkeypatch,
    adzuna=None,
    jsearch_result=None,
    greenhouse_result=None,
    lever_result=None,
    ashby_result=None,
    adzuna_raises=False,
    greenhouse_raises=False,
    lever_raises=False,
    ashby_raises=False,
):
    async def fake_adzuna(role, location, limit=None):
        if adzuna_raises:
            raise RuntimeError("adzuna exploded")
        return adzuna or []

    async def fake_jsearch(role, location, limit=50):
        return jsearch_result or []

    async def fake_greenhouse(role, location, limit=200):
        if greenhouse_raises:
            raise RuntimeError("greenhouse exploded")
        return greenhouse_result or []

    async def fake_lever(role, location, limit=200):
        if lever_raises:
            raise RuntimeError("lever exploded")
        return lever_result or []

    async def fake_ashby(role, location, limit=200):
        if ashby_raises:
            raise RuntimeError("ashby exploded")
        return ashby_result or []

    monkeypatch.setattr(discovery.adzuna_source, "fetch", fake_adzuna)
    monkeypatch.setattr(discovery.jsearch, "fetch", fake_jsearch)
    monkeypatch.setattr(discovery.greenhouse, "fetch", fake_greenhouse)
    monkeypatch.setattr(discovery.lever, "fetch", fake_lever)
    monkeypatch.setattr(discovery.ashby, "fetch", fake_ashby)
    # Bypass the on-disk source cache so these exercise the fan-out itself.
    monkeypatch.setattr(discovery, "_cached_source_postings", lambda *a, **k: None)
    monkeypatch.setattr(discovery, "_store_source_postings", lambda *a, **k: None)


def _src_posting(source, title="Backend Developer", company="Acme", description="Python.", **kw):
    return raw_posting(
        source=source,
        external_id=kw.get("external_id", f"{source}-1"),
        title=title,
        company=company,
        location=kw.get("location", "Bengaluru, India"),
        description=description,
        url=f"https://{source}.test/job",
        created=kw.get("created", "2026-09-20T00:00:00Z"),
    )


@pytest.mark.anyio
async def test_fan_out_gathers_all_five_sources_and_counts_each(monkeypatch):
    _stub_sources(
        monkeypatch,
        adzuna=[_src_posting("adzuna", company="A1"), _src_posting("adzuna", company="A2")],
        jsearch_result=[_src_posting("jsearch", company="J1")],
        greenhouse_result=[_src_posting("greenhouse", company="G1")],
        lever_result=[_src_posting("lever", company="L1")],
        ashby_result=[_src_posting("ashby", company="A1")],
    )

    postings, counts = await discovery._gather_sources(
        "backend developer", ["backend developer"], "Bengaluru"
    )

    assert counts == {"adzuna": 2, "jsearch": 1, "greenhouse": 1, "lever": 1, "ashby": 1}
    assert len(postings) == 6


@pytest.mark.anyio
async def test_lever_and_ashby_use_independent_source_cache_entries(monkeypatch):
    cached_by_source = {
        "lever": [_src_posting("lever", company="Lever Co")],
        "ashby": [_src_posting("ashby", company="Ashby Co")],
    }
    requested_sources = []

    def fake_cached_source_postings(source, role, location):
        requested_sources.append(source)
        return cached_by_source[source]

    async def must_not_fetch():
        raise AssertionError("a fresh per-source cache hit must not call its provider")

    monkeypatch.setattr(
        discovery, "_cached_source_postings", fake_cached_source_postings
    )

    lever_postings = await discovery._cached_fetch(
        "lever", "backend developer", "India", must_not_fetch
    )
    ashby_postings = await discovery._cached_fetch(
        "ashby", "backend developer", "India", must_not_fetch
    )

    assert requested_sources == ["lever", "ashby"]
    assert lever_postings[0]["source"] == "lever"
    assert ashby_postings[0]["source"] == "ashby"
    assert discovery._source_cache_key(
        "lever", "backend developer", "India"
    ) != discovery._source_cache_key("ashby", "backend developer", "India")


@pytest.mark.anyio
async def test_fan_out_completes_when_one_source_errors(monkeypatch):
    """The central resilience guarantee: a source raising outright must
    cost only its own results.
    """
    _stub_sources(
        monkeypatch,
        adzuna_raises=True,
        jsearch_result=[_src_posting("jsearch", company="J1")],
        greenhouse_result=[_src_posting("greenhouse", company="G1")],
    )

    postings, counts = await discovery._gather_sources(
        "backend developer", ["backend developer"], "India"
    )

    assert counts["adzuna"] == 0
    assert counts["jsearch"] == 1
    assert counts["greenhouse"] == 1
    assert len(postings) == 2


@pytest.mark.anyio
async def test_fan_out_completes_when_every_source_errors(monkeypatch):
    _stub_sources(
        monkeypatch,
        adzuna_raises=True,
        greenhouse_raises=True,
        lever_raises=True,
        ashby_raises=True,
    )

    postings, counts = await discovery._gather_sources("role", ["role"], "India")

    assert postings == []
    assert counts == {"adzuna": 0, "jsearch": 0, "greenhouse": 0, "lever": 0, "ashby": 0}


@pytest.mark.anyio
async def test_missing_rapidapi_key_does_not_break_the_run(monkeypatch):
    """End-to-end version of the JSearch no-key path, through the fan-out:
    the other two sources still produce a full result set.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "")
    monkeypatch.setattr(discovery, "_cached_source_postings", lambda *a, **k: None)
    monkeypatch.setattr(discovery, "_store_source_postings", lambda *a, **k: None)

    async def fake_adzuna(role, location, limit=None):
        return [_src_posting("adzuna", company="A1")]

    async def fake_greenhouse(role, location, limit=200):
        return [_src_posting("greenhouse", company="G1")]

    monkeypatch.setattr(discovery.adzuna_source, "fetch", fake_adzuna)
    monkeypatch.setattr(discovery.greenhouse, "fetch", fake_greenhouse)

    postings, counts = await discovery._gather_sources("role", ["role"], "India")

    assert counts["jsearch"] == 0
    assert counts["adzuna"] == 1 and counts["greenhouse"] == 1
    assert len(postings) == 2


def test_jsearch_wins_over_adzuna_for_an_identical_fingerprint():
    """Same job, same fingerprint, two sources. JSearch must survive dedupe
    because its description is the full posting rather than a snippet.
    """
    adzuna_job = discovery.normalise_posting(
        _src_posting("adzuna", description="Truncated snippet...")
    )
    jsearch_job = discovery.normalise_posting(
        _src_posting("jsearch", description="The full posting text, at length. " * 10)
    )
    assert adzuna_job.fingerprint == jsearch_job.fingerprint

    # Adzuna arrives first, so first-seen-wins would keep the wrong one.
    unique, duplicates = discovery.dedupe([adzuna_job, jsearch_job])

    assert len(unique) == 1
    assert duplicates == 1
    assert unique[0].source == "jsearch"


def test_greenhouse_wins_over_adzuna_but_loses_to_jsearch():
    adzuna_job = discovery.normalise_posting(_src_posting("adzuna"))
    greenhouse_job = discovery.normalise_posting(_src_posting("greenhouse"))
    jsearch_job = discovery.normalise_posting(_src_posting("jsearch"))

    unique, _ = discovery.dedupe([adzuna_job, greenhouse_job])
    assert unique[0].source == "greenhouse"

    unique, _ = discovery.dedupe([greenhouse_job, jsearch_job])
    assert unique[0].source == "jsearch"

    unique, _ = discovery.dedupe([jsearch_job, greenhouse_job, adzuna_job])
    assert len(unique) == 1
    assert unique[0].source == "jsearch"


def test_all_official_ats_sources_outrank_adzuna_in_priority_order():
    jobs = {
        source: discovery.normalise_posting(_src_posting(source))
        for source in ("adzuna", "jsearch", "greenhouse", "lever", "ashby")
    }

    unique, duplicates = discovery.dedupe(
        [jobs["adzuna"], jobs["jsearch"], jobs["ashby"], jobs["lever"], jobs["greenhouse"]]
    )

    assert duplicates == 4
    assert len(unique) == 1
    assert unique[0].source == "jsearch"


def test_source_priority_beats_description_length():
    """Priority is the primary key: a short JSearch description still wins
    over a long Adzuna one, because the source is the better authority.
    """
    long_adzuna = discovery.normalise_posting(
        _src_posting("adzuna", description="x" * 5000)
    )
    short_jsearch = discovery.normalise_posting(
        _src_posting("jsearch", description="short")
    )

    unique, _ = discovery.dedupe([long_adzuna, short_jsearch])
    assert unique[0].source == "jsearch"


def test_normalise_posting_keeps_the_adapter_source():
    for source in ("adzuna", "jsearch", "greenhouse", "lever", "ashby"):
        job = discovery.normalise_posting(_src_posting(source))
        assert job.source == source


def test_normalise_posting_defaults_to_adzuna_for_a_sourceless_dict():
    """Hand-built dicts in the older tests carry no `source` key; they must
    still validate rather than failing the model.
    """
    job = discovery.normalise_posting({"title": "Dev", "company": "Acme", "location": "Pune"})
    assert job.source == "adzuna"


# --------------------------------------------------------------------------
# JSearch request parameters and quota budget
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_jsearch_sends_every_required_parameter(monkeypatch):
    """The exact param set matters: country scopes to India, num_pages=2
    buys ~20 results for one quota call, and work_from_home must NOT be
    sent -- remote is a client-side filter on the discovery page, so
    narrowing it here would hide postings the user can still choose.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda *a, **k: 1)

    captured = {}

    async def fake_get(params, headers):
        captured.update(params)
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(jsearch, "_get", fake_get)
    await jsearch.fetch("web developer", "Ahmedabad")

    assert captured["query"] == "web developer in Ahmedabad"
    assert captured["country"] == "in"
    assert captured["page"] == "1"
    assert captured["num_pages"] == "2"
    assert captured["date_posted"] == "month"
    assert captured["language"] == "en"
    assert "work_from_home" not in captured


@pytest.mark.anyio
async def test_jsearch_counts_every_call_against_the_monthly_budget(monkeypatch):
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    recorded = []
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda source, **k: recorded.append(source) or 1)

    async def fake_get(params, headers):
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(jsearch, "_get", fake_get)
    await jsearch.fetch("dev", "India")

    assert recorded == ["jsearch"]


@pytest.mark.anyio
async def test_jsearch_skips_the_call_once_the_budget_is_spent(monkeypatch):
    """At MONTHLY_CALL_BUDGET the source stops itself, preserving the
    reserve for a demo -- and makes no HTTP request at all.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: False)

    async def exploding_get(params, headers):
        raise AssertionError("must not call the API with no budget left")

    monkeypatch.setattr(jsearch, "_get", exploding_get)
    assert await jsearch.fetch("dev", "India") == []


@pytest.mark.anyio
async def test_jsearch_counts_a_failed_call_too(monkeypatch):
    """A request that fails still consumed quota upstream, so it must be
    counted -- counting only successes drifts optimistic and overruns.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    recorded = []
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda source, **k: recorded.append(source) or 1)

    async def failing_get(params, headers):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(jsearch, "_get", failing_get)
    assert await jsearch.fetch("dev", "India") == []
    assert recorded == ["jsearch"]


def test_jsearch_budget_reserves_calls_below_the_real_tier_limit():
    assert jsearch.MONTHLY_CALL_BUDGET < jsearch.MONTHLY_CALL_LIMIT
    assert jsearch.MONTHLY_CALL_LIMIT - jsearch.MONTHLY_CALL_BUDGET == jsearch.MONTHLY_CALL_RESERVE


# --------------------------------------------------------------------------
# Quota counter
# --------------------------------------------------------------------------


def test_quota_counts_and_resets_per_calendar_month():
    from datetime import datetime, timezone

    from app.services.jobs import quota

    september = datetime(2026, 9, 15, tzinfo=timezone.utc)
    october = datetime(2026, 10, 1, tzinfo=timezone.utc)
    source = "quota-test-source"

    assert quota.usage(source, now=september) == 0
    assert quota.record_call(source, now=september) == 1
    assert quota.record_call(source, now=september) == 2
    assert quota.usage(source, now=september) == 2

    # New month, new key -- the reset needs no scheduled job.
    assert quota.usage(source, now=october) == 0
    assert quota.record_call(source, now=october) == 1
    # September's record is preserved, not overwritten.
    assert quota.usage(source, now=september) == 2


def test_quota_has_budget_respects_the_limit():
    from datetime import datetime, timezone

    from app.services.jobs import quota

    now = datetime(2026, 11, 5, tzinfo=timezone.utc)
    source = "budget-test-source"

    assert quota.has_budget(source, limit=2, now=now) is True
    quota.record_call(source, now=now)
    assert quota.has_budget(source, limit=2, now=now) is True
    quota.record_call(source, now=now)
    assert quota.has_budget(source, limit=2, now=now) is False


# --------------------------------------------------------------------------
# Remote flag: provider-stated beats inferred
# --------------------------------------------------------------------------


def test_a_provider_stated_remote_flag_beats_text_sniffing():
    """JSearch reports job_is_remote -- the employer's own answer. It must
    win over our regex, which only exists for sources that say nothing.
    """
    # Says remote, but the text never mentions it: trust the provider.
    stated_remote = discovery.normalise_posting(
        raw_posting(
            source="jsearch", external_id="1", title="Engineer", company="Acme",
            location="Bengaluru", description="Build things.", url="u",
            created=None, is_remote=True,
        )
    )
    assert stated_remote.is_remote is True

    # Says NOT remote, though the text mentions the word: still trust it.
    stated_onsite = discovery.normalise_posting(
        raw_posting(
            source="jsearch", external_id="2", title="Engineer", company="Acme",
            location="Bengaluru", description="This is not a remote role.", url="u",
            created=None, is_remote=False,
        )
    )
    assert stated_onsite.is_remote is False


def test_remote_is_inferred_when_the_provider_says_nothing():
    inferred = discovery.normalise_posting(
        raw_posting(
            source="adzuna", external_id="3", title="Engineer", company="Acme",
            location="Remote", description="Fully remote position.", url="u",
            created=None, is_remote=None,
        )
    )
    assert inferred.is_remote is True


# --------------------------------------------------------------------------
# Attribution
# --------------------------------------------------------------------------


def test_every_source_carries_its_own_attribution_label():
    labels = {
        source: discovery.normalise_posting(
            raw_posting(
                source=source, external_id="1", title="Dev", company="Acme",
                location="Pune", description="x", url="u", created=None,
            )
        ).source_label
        for source in ("jsearch", "greenhouse", "lever", "ashby", "adzuna")
    }
    assert labels == {
        "jsearch": "via JSearch",
        "greenhouse": "via Greenhouse",
        "lever": "via Lever",
        "ashby": "via Ashby",
        "adzuna": "via Adzuna",
    }


@pytest.mark.anyio
async def test_jsearch_does_not_retry_a_permanent_failure(monkeypatch):
    """403 is RapidAPI's "not subscribed to this API" -- an account fact,
    not a blip. Retrying it three times burned three calls against a
    200/month tier for nothing. Verified against the live API before this
    guard existed.
    """
    monkeypatch.setattr(jsearch.settings, "rapidapi_key", "test-key")
    monkeypatch.setattr(jsearch.quota, "has_budget", lambda *a, **k: True)
    monkeypatch.setattr(jsearch.quota, "record_call", lambda *a, **k: 1)

    attempts = []

    # Patch the transport, not the client: that leaves the module's own
    # @retry decorator in place, so the retry policy is what's under test.
    def forbidden_transport(request):
        attempts.append(1)
        return httpx.Response(403, json={"message": "You are not subscribed to this API."})

    real_init = httpx.AsyncClient.__init__

    def init_with_mock_transport(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(forbidden_transport)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", init_with_mock_transport)

    assert await jsearch.fetch("dev", "India") == []
    assert len(attempts) == 1, "a permanent 403 must not be retried"


@pytest.mark.anyio
async def test_jsearch_still_retries_a_transient_failure(monkeypatch):
    """A 500 or a timeout is worth another attempt -- only the permanent
    statuses are exempt.
    """
    assert jsearch._is_retryable(
        httpx.HTTPStatusError("500", request=httpx.Request("GET", "https://x"),
                              response=httpx.Response(500))
    ) is True
    assert jsearch._is_retryable(
        httpx.HTTPStatusError("429", request=httpx.Request("GET", "https://x"),
                              response=httpx.Response(429))
    ) is True
    assert jsearch._is_retryable(httpx.ConnectError("boom")) is True
    for status in (400, 401, 403, 404):
        assert jsearch._is_retryable(
            httpx.HTTPStatusError(str(status), request=httpx.Request("GET", "https://x"),
                                  response=httpx.Response(status))
        ) is False

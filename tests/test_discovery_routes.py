"""Tests for the /api/discovery routes: auth, ownership, and the
per-posting detail view.

Network-free -- discovery.execute_run is either stubbed or driven against
a stubbed adzuna.search, the same way the other route tests stub
get_or_parse/get_or_mine. Each test registers its own throwaway user, so
runs don't collide with leftover ./data/ state.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.services.discovery as discovery_module
from app.main import app
from app.models.resume import ContactInfo, ParsedResume
from app.store import load_json, save_json

client = TestClient(app)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _unique_email() -> str:
    return f"discovery-{uuid.uuid4().hex}@example.com"


def _register() -> tuple[str, str]:
    """Returns (auth header value, user_id) for a fresh throwaway user."""
    email = _unique_email()
    response = client.post(
        "/api/auth/register",
        json={"name": "Discovery Tester", "email": email, "password": "testpass123"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return f"Bearer {body['access_token']}", body["user"]["user_id"]


def _stub_resume() -> ParsedResume:
    return ParsedResume(
        contact=ContactInfo(name="Someone"),
        skills=["Python", "Django"],
        sections_found=["skills"],
        total_experience_months=12,
    )


def _save_analysis(user_id: str, resume_file_key: str | None = "stub-resume-key") -> str:
    """An analysis record owned by user_id, without running the real
    pipeline. Only the fields discovery reads are populated.
    """
    analysis_id = uuid.uuid4().hex
    record = {
        "analysis_id": analysis_id,
        "user_id": user_id,
        "filename": "resume.pdf",
        "role": "backend developer",
        "location": "Ahmedabad",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if resume_file_key is not None:
        record["resume_file_key"] = resume_file_key
    save_json("analyses", analysis_id, record)
    return analysis_id


def _save_parse(
    key: str = "stub-resume-key", skills: list[str] | None = None
) -> None:
    resume = _stub_resume()
    if skills is not None:
        resume.skills = skills
    save_json("parsed_resumes", key, resume.model_dump())


def _save_run(user_id: str, analysis_id: str, jobs: list[dict] | None = None) -> str:
    run_id = uuid.uuid4().hex
    save_json(
        "discovery_runs",
        run_id,
        {
            "run_id": run_id,
            "user_id": user_id,
            "analysis_id": analysis_id,
            "status": "complete",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "target": {"role": "backend developer", "location": "Ahmedabad"},
            "stats": {"requested": 3, "fetched": 40, "unique": 30, "ranked": 30, "duplicate_rate": 0.25},
            "widened": None,
            "queries": ["backend developer"],
            "jobs": jobs or [],
            "error": None,
        },
    )
    return run_id


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


def test_discovery_routes_require_authentication():
    assert client.post("/api/discovery/run", json={"analysis_id": "x"}).status_code == 401
    assert client.get("/api/discovery/some-run").status_code == 401
    assert client.get("/api/discovery/some-run/jobs/some-fingerprint").status_code == 401


def test_another_user_cannot_fetch_someone_elses_run():
    """404, not 403. A 403 would confirm the run id is real -- same rule
    the analyses routes already follow.
    """
    owner_auth, owner_id = _register()
    other_auth, _ = _register()

    _save_parse()
    analysis_id = _save_analysis(owner_id)
    run_id = _save_run(owner_id, analysis_id)

    owner_response = client.get(f"/api/discovery/{run_id}", headers={"Authorization": owner_auth})
    assert owner_response.status_code == 200

    other_response = client.get(f"/api/discovery/{run_id}", headers={"Authorization": other_auth})
    assert other_response.status_code == 404
    assert "403" not in other_response.text


def test_another_user_cannot_fetch_a_job_from_someone_elses_run():
    owner_auth, owner_id = _register()
    other_auth, _ = _register()

    _save_parse()
    analysis_id = _save_analysis(owner_id)
    job = {"fingerprint": "abc123", "title": "Backend Developer", "company": "Acme"}
    run_id = _save_run(owner_id, analysis_id, jobs=[job])

    assert (
        client.get(f"/api/discovery/{run_id}/jobs/abc123", headers={"Authorization": owner_auth}).status_code
        == 200
    )
    assert (
        client.get(f"/api/discovery/{run_id}/jobs/abc123", headers={"Authorization": other_auth}).status_code
        == 404
    )


def test_public_run_and_detail_sanitize_legacy_job_data():
    auth, user_id = _register()
    missing_analysis_id = uuid.uuid4().hex
    legacy_job = {
        "fingerprint": "legacy-job",
        "source": "greenhouse",
        "source_label": "via Greenhouse",
        "title": "Backend Engineer",
        "company": "Example Co",
        "location": "India",
        "is_remote": False,
        "description": "Build Python services with PostgreSQL.",
        "url": "javascript:alert(1)",
        "match_score": 72.0,
        "matched_skills": ["python"],
        "missing_skills": [],
        "score_breakdown": {},
        "meta": {
            "description_truncated": True,
            "description_chars": 38,
            "skills_detected_in_posting": 2,
            "low_confidence": True,
            "skills_unscored": False,
        },
    }
    run_id = _save_run(
        user_id, missing_analysis_id, jobs=[legacy_job]
    )

    run_response = client.get(
        f"/api/discovery/{run_id}", headers={"Authorization": auth}
    )
    assert run_response.status_code == 200
    public_job = run_response.json()["jobs"][0]
    assert public_job["url"] is None
    assert public_job["meta"]["description_truncated"] is False

    detail_response = client.get(
        f"/api/discovery/{run_id}/jobs/legacy-job",
        headers={"Authorization": auth},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["url"] is None
    assert detail_response.json()["meta"]["description_truncated"] is False


def test_discovery_failure_does_not_expose_internal_exception_text(monkeypatch):
    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)

    async def failing_sources(*_args, **_kwargs):
        raise RuntimeError("provider failed at C:/private/path?api_key=secret")

    monkeypatch.setattr(discovery_module, "_gather_sources", failing_sources)
    response = client.post(
        "/api/discovery/run",
        json={"analysis_id": analysis_id},
        headers={"Authorization": auth},
    )
    assert response.status_code == 200

    run = client.get(
        f"/api/discovery/{response.json()['run_id']}",
        headers={"Authorization": auth},
    ).json()
    assert run["status"] == "failed"
    assert "secret" not in run["error"]
    assert "C:/private" not in run["error"]
    assert "try again" in run["error"].lower()


def test_unknown_run_id_is_404():
    auth, _ = _register()
    response = client.get(f"/api/discovery/{uuid.uuid4().hex}", headers={"Authorization": auth})
    assert response.status_code == 404


def test_starting_a_run_on_someone_elses_analysis_is_404():
    _, owner_id = _register()
    other_auth, _ = _register()

    _save_parse()
    analysis_id = _save_analysis(owner_id)

    response = client.post(
        "/api/discovery/run",
        json={"analysis_id": analysis_id},
        headers={"Authorization": other_auth},
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Starting a run
# --------------------------------------------------------------------------


def test_starting_a_run_returns_a_run_id_immediately(monkeypatch):
    """POST returns before the pipeline finishes -- the client polls GET
    for progress. The background task is stubbed so no network is touched.
    """
    executed = []

    async def fake_execute(run_id):
        executed.append(run_id)
        return {}

    monkeypatch.setattr(discovery_module, "execute_run", fake_execute)

    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "run_id" in body
    assert body["status"] == "pending"
    # TestClient runs background tasks synchronously once the response is
    # returned, so this confirms the task was actually scheduled.
    assert executed == [body["run_id"]]


def test_discovery_run_stats_include_all_official_ats_sources(monkeypatch):
    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)
    analysis = load_json("analyses", analysis_id)
    analysis["location"] = "India"  # Avoid a second widened fetch in this test.
    save_json("analyses", analysis_id, analysis)

    def stub_source(module, source):
        async def fake_fetch(role, location, limit=None):
            return [
                {
                    "source": source,
                    "title": "Backend Developer",
                    "company": f"{source.title()} Co",
                    "location": location,
                    "description": f"Full {source} description with Python and Django.",
                    "url": f"https://{source}.test/job/1",
                    "created": datetime.now(timezone.utc).isoformat(),
                    "description_truncated": source == "adzuna",
                }
            ]

        monkeypatch.setattr(module, "fetch", fake_fetch)

    stub_source(discovery_module.adzuna_source, "adzuna")
    stub_source(discovery_module.jsearch, "jsearch")
    stub_source(discovery_module.greenhouse, "greenhouse")
    stub_source(discovery_module.lever, "lever")
    stub_source(discovery_module.ashby, "ashby")
    monkeypatch.setattr(discovery_module, "_cached_source_postings", lambda *args: None)
    monkeypatch.setattr(discovery_module, "_store_source_postings", lambda *args: None)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", False)

    response = client.post(
        "/api/discovery/run",
        json={"analysis_id": analysis_id},
        headers={"Authorization": auth},
    )
    assert response.status_code == 200
    run = client.get(
        f"/api/discovery/{response.json()['run_id']}",
        headers={"Authorization": auth},
    ).json()

    assert run["status"] == "complete"
    by_source = run["stats"]["by_source"]
    assert set(by_source) == {
        "adzuna",
        "jsearch",
        "greenhouse",
        "lever",
        "ashby",
        "after_dedupe",
    }
    assert all(by_source[source] == 1 for source in ("lever", "ashby"))
    assert by_source["after_dedupe"] == 5


def test_starting_a_run_on_an_analysis_with_no_recoverable_resume_is_409():
    """An analysis saved before resume_file_key existed can't be matched
    against jobs. That's a 409 with a fix-it message, not a silent empty
    run -- see discovery._resume_for_analysis.
    """
    auth, user_id = _register()
    analysis_id = _save_analysis(user_id, resume_file_key=None)

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )

    assert response.status_code == 409
    assert "re-run the analysis" in response.json()["detail"].lower()


# --------------------------------------------------------------------------
# Per-posting detail
# --------------------------------------------------------------------------


def test_job_detail_rescores_against_that_postings_own_description():
    """The detail view recomputes rather than echoing the stored number,
    so its keyword component reflects this posting's text alone.
    """
    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)

    job = {
        "fingerprint": "detail-fp",
        "source": "adzuna",
        "title": "Backend Developer",
        "company": "Acme",
        "location": "Ahmedabad, Gujarat",
        "is_remote": False,
        "description": "We need Python and Django, plus Kubernetes.",
        "url": "https://example.test/job",
        "posted_at": datetime.now(timezone.utc).isoformat(),
        # Deliberately wrong stored values: if the route echoed these
        # instead of rescoring, the assertions below would fail.
        "match_score": 0.0,
        "matched_skills": [],
        "missing_skills": [],
    }
    run_id = _save_run(user_id, analysis_id, jobs=[job])

    response = client.get(
        f"/api/discovery/{run_id}/jobs/detail-fp", headers={"Authorization": auth}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_score"] > 0
    assert "python" in body["matched_skills"]
    assert "django" in body["matched_skills"]
    assert "kubernetes" in body["missing_skills"]
    assert body["meta"]["description_truncated"] is True


def test_unknown_job_fingerprint_is_404():
    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)
    run_id = _save_run(user_id, analysis_id, jobs=[])

    response = client.get(
        f"/api/discovery/{run_id}/jobs/does-not-exist", headers={"Authorization": auth}
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------
# DEMO_MODE contract
# --------------------------------------------------------------------------


def test_demo_mode_serves_a_warmed_run_instead_of_hitting_the_network(monkeypatch):
    """Same contract as roleprofile/cache.py: in demo mode a warmed run
    for this (role, location) is served, and adzuna.search is never called.
    """
    called = []

    async def exploding_fetch(*args, **kwargs):
        called.append(args)
        raise AssertionError("DEMO_MODE must never hit the network")

    for module in (
        discovery_module.adzuna_source,
        discovery_module.jsearch,
        discovery_module.greenhouse,
        discovery_module.lever,
        discovery_module.ashby,
    ):
        monkeypatch.setattr(module, "fetch", exploding_fetch)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", True)

    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)

    warmed_job = {
        "fingerprint": "warm-fp",
        "title": "Backend Developer",
        "company": "Acme",
    }
    _save_run(user_id, analysis_id, jobs=[warmed_job])

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    run = client.get(f"/api/discovery/{run_id}", headers={"Authorization": auth}).json()
    assert run["status"] == "complete"
    assert [job["fingerprint"] for job in run["jobs"]] == ["warm-fp"]
    assert called == []


def test_demo_mode_with_no_warmed_run_fails_with_a_message_naming_the_fix(monkeypatch):
    """The miss case is "nobody has warmed this role/location", not "this
    user hasn't" -- see find_cached_run. So this uses a role/location no
    other test warms, rather than just a fresh user.
    """
    async def exploding_fetch(*args, **kwargs):
        raise AssertionError("DEMO_MODE must never hit the network")

    for module in (
        discovery_module.adzuna_source,
        discovery_module.jsearch,
        discovery_module.greenhouse,
        discovery_module.lever,
        discovery_module.ashby,
    ):
        monkeypatch.setattr(module, "fetch", exploding_fetch)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", True)

    auth, user_id = _register()
    _save_parse()
    analysis_id = _save_analysis(user_id)

    # A role nothing else in the suite warms, so the cache genuinely misses.
    record = load_json("analyses", analysis_id)
    record["role"] = f"unwarmed role {uuid.uuid4().hex}"
    save_json("analyses", analysis_id, record)

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )
    run_id = response.json()["run_id"]

    run = client.get(f"/api/discovery/{run_id}", headers={"Authorization": auth}).json()
    assert run["status"] == "failed"
    assert "prep_demo.py" in run["error"]


def test_demo_mode_serves_a_run_warmed_under_a_different_account(monkeypatch):
    """prep_demo.py warms its runs under the demo account, but a presenter
    may well be signed in as themselves. Scoping the DEMO_MODE cache
    lookup strictly by owner meant they got "no cached run exists" -- the
    exact failure DEMO_MODE exists to prevent. See find_cached_run.
    """
    async def exploding_fetch(*args, **kwargs):
        raise AssertionError("DEMO_MODE must never hit the network")

    for module in (
        discovery_module.adzuna_source,
        discovery_module.jsearch,
        discovery_module.greenhouse,
        discovery_module.lever,
        discovery_module.ashby,
    ):
        monkeypatch.setattr(module, "fetch", exploding_fetch)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", True)

    # Someone else (stand-in for the demo account) warmed the run.
    _, warmer_id = _register()
    _save_parse()
    warmer_analysis = _save_analysis(warmer_id)
    _save_run(
        warmer_id,
        warmer_analysis,
        jobs=[
            {
                "fingerprint": "warmed-by-someone-else",
                "title": "Backend Developer",
                "company": "Acme",
            }
        ],
    )

    # A different user now asks for the same role/location.
    auth, user_id = _register()
    analysis_id = _save_analysis(user_id)

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )
    run_id = response.json()["run_id"]
    run = client.get(f"/api/discovery/{run_id}", headers={"Authorization": auth}).json()

    assert run["status"] == "complete"
    assert [job["fingerprint"] for job in run["jobs"]] == ["warmed-by-someone-else"]
    # The copy lands in a run owned by the caller, so ownership on read is
    # unaffected -- the other user's original run is untouched.
    assert run["run_id"] == run_id


def test_demo_mode_reranks_another_users_cached_postings_for_current_resume(
    monkeypatch,
):
    """Cached runs share postings, never another resume's match results."""
    async def exploding_fetch(*args, **kwargs):
        raise AssertionError("DEMO_MODE must never hit the network")

    for module in (
        discovery_module.adzuna_source,
        discovery_module.jsearch,
        discovery_module.greenhouse,
        discovery_module.lever,
        discovery_module.ashby,
    ):
        monkeypatch.setattr(module, "fetch", exploding_fetch)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", True)

    warmer_key = f"warmer-resume-{uuid.uuid4().hex}"
    _save_parse(warmer_key, skills=["Python", "Django"])
    _, warmer_id = _register()
    warmer_analysis = _save_analysis(warmer_id, resume_file_key=warmer_key)

    now = datetime.now(timezone.utc).isoformat()
    cached_jobs = [
        {
            "fingerprint": "python-fp",
            "source": "greenhouse",
            "source_label": "via Cached Provider",
            "title": "Python Backend Developer",
            "company": "Python Co",
            "location": "Ahmedabad, Gujarat",
            "is_remote": False,
            "description": "Build services with Python and Django.",
            "posted_at": now,
            # Deliberately stale, resume-specific values from the warmer.
            "match_score": 99.0,
            "matched_skills": ["python", "django"],
            "missing_skills": [],
            "score_breakdown": {"cached_user_only": True},
            "meta": {
                "description_truncated": False,
                "description_chars": 999,
                "skills_detected_in_posting": 999,
                "low_confidence": False,
                "skills_unscored": False,
            },
        },
        {
            "fingerprint": "java-fp",
            "source": "greenhouse",
            "source_label": "via Cached Provider",
            "title": "Backend Java Cloud Engineer",
            "company": "Java Co",
            "location": "Ahmedabad, Gujarat",
            "is_remote": False,
            "description": "Build services with Java and AWS.",
            "posted_at": now,
            "match_score": 1.0,
            "matched_skills": [],
            "missing_skills": ["python"],
            "score_breakdown": {"cached_user_only": True},
            "meta": {
                "description_truncated": False,
                "description_chars": 999,
                "skills_detected_in_posting": 999,
                "low_confidence": False,
                "skills_unscored": False,
            },
        },
    ]
    warmed_run_id = _save_run(warmer_id, warmer_analysis, jobs=cached_jobs)
    warmed_run = load_json("discovery_runs", warmed_run_id)
    warmed_run["stats"]["by_source"] = {
        "greenhouse": 2,
        "after_dedupe": 2,
    }
    warmed_run["queries"] = ["backend developer python"]
    save_json("discovery_runs", warmed_run_id, warmed_run)

    consumer_key = f"consumer-resume-{uuid.uuid4().hex}"
    _save_parse(consumer_key, skills=["Java", "AWS"])
    consumer_auth, consumer_id = _register()
    consumer_analysis = _save_analysis(
        consumer_id, resume_file_key=consumer_key
    )

    response = client.post(
        "/api/discovery/run",
        json={"analysis_id": consumer_analysis},
        headers={"Authorization": consumer_auth},
    )
    run_id = response.json()["run_id"]
    run = client.get(
        f"/api/discovery/{run_id}", headers={"Authorization": consumer_auth}
    ).json()

    assert run["status"] == "complete"
    # The warmer's ordering is reversed for the Java/AWS resume.
    assert [job["fingerprint"] for job in run["jobs"]] == ["java-fp", "python-fp"]
    java_job, python_job = run["jobs"]

    assert set(java_job["matched_skills"]) == {"java", "aws"}
    assert java_job["missing_skills"] == []
    assert python_job["matched_skills"] == []
    assert set(python_job["missing_skills"]) == {"python", "django"}
    assert "cached_user_only" not in java_job["score_breakdown"]
    assert java_job["score_breakdown"]["keyword_effective"] > 0
    assert python_job["score_breakdown"]["keyword_effective"] == 0
    assert java_job["meta"] == {
        "description_truncated": False,
        "description_chars": len(cached_jobs[1]["description"]),
        "skills_detected_in_posting": 2,
        "low_confidence": True,
        "skills_unscored": False,
    }

    # Cached provider/location metadata and source statistics survive the
    # re-rank; only the current user's resume-derived fields are replaced.
    assert java_job["source"] == "greenhouse"
    assert java_job["source_label"] == "via Cached Provider"
    assert java_job["location"] == "Ahmedabad, Gujarat"
    assert run["stats"]["by_source"] == warmed_run["stats"]["by_source"]
    assert any("java" in query for query in run["queries"])
    assert all("python" not in query for query in run["queries"])

    detail = client.get(
        f"/api/discovery/{run_id}/jobs/java-fp",
        headers={"Authorization": consumer_auth},
    )
    assert detail.status_code == 200, detail.text
    detail_job = detail.json()
    assert detail_job["match_score"] == java_job["match_score"]
    assert set(detail_job["matched_skills"]) == {"java", "aws"}
    assert detail_job["missing_skills"] == []
    assert "cached_user_only" not in detail_job["score_breakdown"]
    assert detail_job["meta"] == java_job["meta"]


def test_demo_mode_prefers_the_callers_own_run_over_someone_elses(monkeypatch):
    async def exploding_fetch(*args, **kwargs):
        raise AssertionError("DEMO_MODE must never hit the network")

    for module in (
        discovery_module.adzuna_source,
        discovery_module.jsearch,
        discovery_module.greenhouse,
        discovery_module.lever,
        discovery_module.ashby,
    ):
        monkeypatch.setattr(module, "fetch", exploding_fetch)
    monkeypatch.setattr(discovery_module.settings, "demo_mode", True)

    _, other_id = _register()
    _save_parse()
    _save_run(
        other_id,
        _save_analysis(other_id),
        jobs=[
            {
                "fingerprint": "someone-elses",
                "title": "Backend Developer",
                "company": "Acme",
            }
        ],
    )

    auth, user_id = _register()
    analysis_id = _save_analysis(user_id)
    _save_run(
        user_id,
        analysis_id,
        jobs=[
            {
                "fingerprint": "my-own",
                "title": "Backend Developer",
                "company": "Acme",
            }
        ],
    )

    response = client.post(
        "/api/discovery/run", json={"analysis_id": analysis_id}, headers={"Authorization": auth}
    )
    run_id = response.json()["run_id"]
    run = client.get(f"/api/discovery/{run_id}", headers={"Authorization": auth}).json()

    assert [job["fingerprint"] for job in run["jobs"]] == ["my-own"]

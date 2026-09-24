"""HTTP contract for the provider-free persistent job map."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import job_map as job_map_router
from app.services.job_map import JobMapUnavailableError

client = TestClient(app)


def test_job_map_is_public_and_never_returns_internal_identifiers(monkeypatch):
    def fake_search(**kwargs):
        assert kwargs["role"] == "frontend"
        return {
            "jobs": [
                {
                    "job_id": "a" * 64,
                    "title": "Frontend Developer",
                    "company": "Acme",
                    "location": "Ahmedabad",
                    "source": "greenhouse",
                    "source_label": "via Greenhouse",
                    "url": "https://example.test/job",
                }
            ],
            "meta": {"count": 1, "limit": 100, "mapped": 1, "last_ingested_at": None},
            "notice": "Approved sources only",
        }

    monkeypatch.setattr(job_map_router, "search_map", fake_search)
    response = client.get("/api/job-map?role=frontend&limit=100")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["count"] == 1
    assert "external_id" not in body["jobs"][0]
    assert "source_key" not in body["jobs"][0]


def test_job_map_rejects_a_partial_coordinate_pair():
    response = client.get("/api/job-map?latitude=23.0")

    assert response.status_code == 422
    assert "together" in response.json()["detail"]


def test_job_map_returns_a_plain_language_unavailable_error(monkeypatch):
    def unavailable(**_kwargs):
        raise JobMapUnavailableError("The job map requires MongoDB.")

    monkeypatch.setattr(job_map_router, "search_map", unavailable)
    response = client.get("/api/job-map")

    assert response.status_code == 503
    assert response.json()["detail"] == "The job map requires MongoDB."


def test_job_map_detail_rejects_invalid_or_unknown_ids(monkeypatch):
    monkeypatch.setattr(job_map_router, "get_map_job", lambda _job_id: None)

    assert client.get("/api/job-map/not-a-sha").status_code == 404
    assert client.get("/api/job-map/" + "f" * 64).status_code == 404

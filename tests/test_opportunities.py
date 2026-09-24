"""Tests for the resume-free approved-source opportunity search."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import discovery, opportunities
from app.services.opportunities import search_opportunities
from app.services.jobs.base import raw_posting

client = TestClient(app)


def _posting(source: str, title: str, company: str) -> dict:
    return raw_posting(
        source=source,
        external_id=f"{source}-{title}",
        title=title,
        company=company,
        location="Ahmedabad, Gujarat, India",
        description="Python and Django backend role.",
        url=f"https://{source}.test/job",
        created="2026-09-20T10:00:00Z",
    )


@pytest.mark.anyio
async def test_search_opportunities_uses_configured_sources_without_a_resume(monkeypatch):
    async def fake_fetch(queries, location, role=None):
        postings = [
            discovery.normalise_posting(
                _posting("greenhouse", f"Backend Engineer {index}", f"Acme {index}")
            )
            for index in range(20)
        ]
        postings.append(
            discovery.normalise_posting(_posting("lever", "Python Developer", "Globex"))
        )
        return postings, {"greenhouse": 20, "lever": 1, "jsearch": 0, "adzuna": 0, "ashby": 0}, len(postings)

    monkeypatch.setattr(discovery, "_fetch_queries", fake_fetch)
    result = await search_opportunities("Backend Developer", "Ahmedabad", limit=10)

    assert result["target"] == {"role": "Backend Developer", "location": "Ahmedabad"}
    assert result["widened"] is None
    assert len(result["jobs"]) == 10
    assert result["stats"]["unique"] == 21
    assert result["stats"]["by_source"]["greenhouse"] == 20
    assert result["notice"].startswith("Opportunities are collected from configured job APIs")


@pytest.mark.anyio
async def test_search_opportunities_widens_thin_city_results(monkeypatch):
    calls = []

    async def fake_fetch(queries, location, role=None):
        calls.append(location)
        if location == "Ahmedabad":
            return [], {"greenhouse": 0, "lever": 0, "jsearch": 0, "adzuna": 0, "ashby": 0}, 0
        return (
            [discovery.normalise_posting(_posting("adzuna", "Backend Engineer", "Acme"))],
            {"greenhouse": 0, "lever": 0, "jsearch": 0, "adzuna": 1, "ashby": 0},
            1,
        )

    monkeypatch.setattr(discovery, "_fetch_queries", fake_fetch)
    result = await search_opportunities("Backend Developer", "Ahmedabad", limit=10)

    assert calls == ["Ahmedabad", "India"]
    assert result["widened"]["to"] == "India"
    assert result["target"]["location"] == "India"
    assert result["jobs"][0]["company"] == "Acme"


def test_opportunities_route_requires_authentication():
    response = client.get("/api/opportunities?role=backend&location=Ahmedabad")
    assert response.status_code == 401


def test_opportunities_route_validates_and_returns_results(monkeypatch):
    async def fake_search(role, location, limit):
        assert role == "backend"
        assert location == "Ahmedabad"
        return {"jobs": [{"title": "Backend Engineer"}], "stats": {"unique": 1}}

    monkeypatch.setattr("app.routers.opportunities.search_opportunities", fake_search)
    auth_response = client.post(
        "/api/auth/register",
        json={
            "name": "Opportunity Tester",
            "email": f"opportunity-{uuid.uuid4().hex}@example.com",
            "password": "testpass123",
        },
    )
    assert auth_response.status_code == 201
    token = auth_response.json()["access_token"]

    response = client.get(
        "/api/opportunities?role=backend&location=Ahmedabad",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["jobs"] == [{"title": "Backend Engineer"}]

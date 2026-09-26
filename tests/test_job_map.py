"""Job-map normalization, ingestion, and snapshot-query tests."""

import asyncio
from datetime import datetime, timezone

import mongomock

from app import database
from app.config import settings
from app.services import job_map


def _posting(
    source: str,
    external_id: str,
    *,
    title: str = "Frontend Developer",
    company: str = "Acme Labs",
    location: str = "Ahmedabad, Gujarat",
    description: str = "React and TypeScript role",
) -> dict:
    return {
        "id": external_id,
        "source": source,
        "source_label": f"via {source.title()}",
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "description_truncated": source == "adzuna",
        "url": f"https://example.test/jobs/{external_id}",
        "created": datetime.now(timezone.utc).isoformat(),
        "is_remote": False,
    }


def test_location_resolver_uses_curated_aliases_and_geojson_order():
    bangalore = job_map.resolve_location(" Bangalore, Karnataka ")
    pune = job_map.resolve_location("Pimpri, Maharashtra")

    assert bangalore["city"] == "Bengaluru"
    assert bangalore["geo"]["coordinates"] == [77.5946, 12.9716]
    assert pune["city"] == "Pune"
    assert job_map.resolve_location("A secret island") is None


def test_canonical_job_identity_keeps_same_title_in_different_cities():
    ahmedabad = job_map.canonical_job_id(
        "Frontend Developer", "Acme Labs", "in|ahmedabad|gujarat", "Ahmedabad"
    )
    pune = job_map.canonical_job_id(
        "Frontend Developer", "Acme Labs", "in|pune|maharashtra", "Pune"
    )

    assert ahmedabad != pune


def test_map_normalization_rejects_unsafe_provider_url():
    document = job_map.normalize_map_posting(
        {**_posting("greenhouse", "1"), "url": "javascript:alert(1)"},
        target_role="frontend developer",
    )

    assert document is not None
    assert document["url"] is None
    assert document["location_quality"] == "curated"
    assert document["geo"]["coordinates"][0] == 72.5714


def test_map_dedupe_prefers_full_first_party_source():
    documents = [
        job_map.normalize_map_posting(
            _posting("adzuna", "a", description="short"),
            target_role="frontend developer",
        ),
        job_map.normalize_map_posting(
            _posting("greenhouse", "b", description="a much fuller posting"),
            target_role="frontend developer",
        ),
    ]

    deduplicated = job_map.dedupe_map_postings(
        [document for document in documents if document is not None]
    )

    assert len(deduplicated) == 1
    assert deduplicated[0]["source"] == "greenhouse"


def test_ingestion_persists_a_provider_free_searchable_snapshot(monkeypatch):
    client = mongomock.MongoClient(tz_aware=True)
    monkeypatch.setattr(database, "_client", client)
    original = (settings.storage_backend, settings.mongodb_database, settings.mongodb_uri)
    settings.storage_backend = "mongodb"
    settings.mongodb_database = "careerstack_test"
    settings.mongodb_uri = "mongodb+srv://example.invalid/careerstack_test"

    async def fake_sources(role, queries, location):
        postings = [
            _posting("greenhouse", "front-1"),
            _posting("jsearch", "front-1", description="Full React and TypeScript role"),
            _posting(
                "greenhouse",
                "backend-1",
                title="Java Backend Developer",
                location="Pune, Maharashtra",
            ),
        ]
        # Two values, matching discovery._gather_sources: (postings, counts).
        # This previously returned a third "fetched" count that the real
        # function does not produce, so the stub disagreed with production
        # and ingestion crashed on the live path while the test passed.
        return postings, {"greenhouse": 2, "jsearch": 1}

    monkeypatch.setattr(job_map.discovery, "_gather_sources", fake_sources)

    try:
        result = asyncio.run(
            job_map.ingest_targets(
                [{"role": "frontend developer", "location": "Ahmedabad", "enabled": True}],
                max_postings=50,
            )
        )
        assert result["upserted_jobs"] == 1

        response = job_map.search_map(role="frontend", location="Ahmedabad")
        assert response["meta"]["count"] == 1
        job = response["jobs"][0]
        assert job["title"] == "Frontend Developer"
        assert job["source"] == "jsearch"
        assert job["latitude"] == 23.0225
        assert job["longitude"] == 72.5714
        assert "external_id" not in job
        assert "source_key" not in job
        assert job_map.get_map_job(job["job_id"])["job_id"] == job["job_id"]
    finally:
        settings.storage_backend, settings.mongodb_database, settings.mongodb_uri = original

"""MongoDB adapter tests using an in-memory server double.

These tests never open an Atlas connection. They verify the same persistence
contract the application uses in production: key compatibility, _id hiding,
field lookup, atomic counters, and the declared indexes/TTLs.
"""

from datetime import datetime, timezone

import mongomock
import pytest

from app import database
from app.config import Settings, settings
from app.store import (
    create_json_if_absent,
    increment_json_field,
    list_keys,
    list_records,
    load_by_field,
    load_json,
    save_json,
)


@pytest.fixture
def mongo_backend(monkeypatch):
    original_backend = settings.storage_backend
    original_database = settings.mongodb_database
    original_uri = settings.mongodb_uri
    client = mongomock.MongoClient(tz_aware=True)
    db = client["careerstack_test"]

    monkeypatch.setattr(database, "_client", client)
    settings.storage_backend = "mongodb"
    settings.mongodb_database = "careerstack_test"
    settings.mongodb_uri = "mongodb+srv://example.invalid/careerstack_test"

    yield db

    settings.storage_backend = original_backend
    settings.mongodb_database = original_database
    settings.mongodb_uri = original_uri


def test_mongodb_round_trip_preserves_legacy_record_shape(mongo_backend):
    document = {
        "candidate": {"name": "Zoë 東京", "skills": ["Python", "SQL"]},
        "notes": [{"message": "café ☕", "enabled": True}],
    }

    save_json("résumés", "résumé-2026_✓.v1", document)

    assert load_json("résumés", "résumé-2026_✓.v1") == document
    assert list_keys("résumés") == ["résumé-2026_✓.v1"]
    stored = mongo_backend["résumés"].find_one({"_id": "résumé-2026_✓.v1"})
    assert stored["candidate"]["name"] == "Zoë 東京"
    assert "schema_version" in stored


def test_mongodb_atomic_create_preserves_logical_key(mongo_backend):
    assert create_json_if_absent("users", "email-key", {"user_id": "user-1"})
    assert not create_json_if_absent("users", "email-key", {"user_id": "user-2"})
    assert load_json("users", "email-key") == {"user_id": "user-1"}
    assert mongo_backend["users"].find_one({"_id": "email-key"})["user_id"] == "user-1"


def test_mongodb_hides_backend_id_from_service_records(mongo_backend):
    save_json("analyses", "analysis-1", {"analysis_id": "analysis-1"})

    loaded = load_json("analyses", "analysis-1")
    listed = list_records("analyses")

    assert loaded == {"analysis_id": "analysis-1"}
    assert listed == [loaded]
    assert "_id" not in loaded


def test_mongodb_supports_direct_field_lookup(mongo_backend):
    save_json("users", "email-key", {"user_id": "user-1", "email": "a@example.com"})
    save_json("users", "other-key", {"user_id": "user-2", "email": "b@example.com"})

    record = load_by_field("users", "user_id", "user-2")

    assert record is not None
    assert record["email"] == "b@example.com"
    assert load_by_field("users", "user_id", "missing") is None


def test_mongodb_counter_increment_is_atomic_at_the_repository_boundary(mongo_backend):
    totals = [
        increment_json_field(
            "api_quota",
            "jsearch-2026-09",
            "calls",
            set_fields={
                "source": "jsearch",
                "period": "2026-09",
                "source_period": "jsearch|2026-09",
                "last_call_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        for _ in range(5)
    ]

    assert totals == [1, 2, 3, 4, 5]
    assert load_json("api_quota", "jsearch-2026-09")["calls"] == 5


def test_mongodb_ttl_metadata_uses_bson_dates_but_stays_out_of_service_data(mongo_backend):
    sampled_at = "2026-09-24T12:00:00+00:00"
    save_json(
        "role_profiles",
        "profile-key",
        {
            "role": "backend developer",
            "sampled_at": sampled_at,
            "postings_sampled": 40,
            "skill_frequencies": {"python": {"frequency": 0.5, "count": 20}},
        },
    )

    stored = mongo_backend["role_profiles"].find_one({"_id": "profile-key"})
    assert isinstance(stored["_expires_at"], datetime)
    assert "_expires_at" not in load_json("role_profiles", "profile-key")
    assert load_json("role_profiles", "profile-key")["sampled_at"] == sampled_at


def test_mongodb_reserved_id_cannot_be_overwritten_by_service_data(mongo_backend):
    with pytest.raises(ValueError, match="_id"):
        save_json("users", "key", {"_id": "attacker-controlled", "email": "a@example.com"})


def test_mongodb_indexes_match_runtime_access_and_expiry_paths(mongo_backend):
    database.ensure_indexes(mongo_backend)

    user_indexes = mongo_backend["users"].index_information()
    analysis_indexes = mongo_backend["analyses"].index_information()
    role_indexes = mongo_backend["role_profiles"].index_information()
    source_indexes = mongo_backend["job_source_cache"].index_information()
    run_indexes = mongo_backend["discovery_runs"].index_information()
    quota_indexes = mongo_backend["api_quota"].index_information()
    map_indexes = mongo_backend["job_map_jobs"].index_information()
    map_source_indexes = mongo_backend["job_map_job_sources"].index_information()

    assert user_indexes["users_user_id_unique"]["unique"] is True
    assert user_indexes["users_email_unique"]["unique"] is True
    assert "analyses_user_created" in analysis_indexes
    assert role_indexes["role_profiles_expiry"]["expireAfterSeconds"] == 7 * 24 * 60 * 60
    assert source_indexes["job_source_cache_expiry"]["expireAfterSeconds"] == 6 * 60 * 60
    assert "discovery_runs_cached_lookup" in run_indexes
    assert quota_indexes["api_quota_source_period_unique"]["unique"] is True
    assert map_indexes["job_map_jobs_geo"]["key"] == [("geo", 1)]
    assert map_indexes["job_map_jobs_expiry"]["expireAfterSeconds"] == 0
    assert map_source_indexes["job_map_source_key_unique"]["unique"] is True


def test_atlas_settings_require_uri_only_for_mongodb_backend():
    with pytest.raises(ValueError, match="MONGODB_URI"):
        Settings(
            jwt_secret="test-secret",
            storage_backend="mongodb",
            mongodb_uri="",
        )

    configured = Settings(
        jwt_secret="test-secret",
        storage_backend="mongodb",
        mongodb_uri="mongodb+srv://user:pass@example.invalid/careerstack",
        mongodb_database="careerstack",
    )
    assert configured.storage_backend == "mongodb"

    offline = Settings(
        jwt_secret="test-secret",
        storage_backend="json",
        mongodb_uri="",
    )
    assert offline.storage_backend == "json"

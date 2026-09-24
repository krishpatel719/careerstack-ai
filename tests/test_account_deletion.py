"""Tests for authenticated, confirmed self-service account deletion."""

import uuid
from datetime import datetime, timezone

import mongomock
import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import settings
from app.main import app
from app.services import account as account_service
from app.services import auth as auth_service
from app.store import delete_json, load_json, save_json

client = TestClient(app)


def _register(email_prefix: str = "account-delete") -> tuple[str, str, str]:
    email = f"{email_prefix}-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"name": "Deletion Tester", "email": email, "password": "testpass123"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return f"Bearer {body['access_token']}", body["user"]["user_id"], email


def _save_analysis(user_id: str, resume_file_key: str) -> str:
    analysis_id = uuid.uuid4().hex
    save_json(
        "analyses",
        analysis_id,
        {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "resume_file_key": resume_file_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return analysis_id


def _save_run(user_id: str, analysis_id: str) -> str:
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
        },
    )
    return run_id


def test_delete_account_requires_authentication_and_explicit_true_confirmation():
    auth, _, _ = _register("account-delete-confirm")

    assert (
        client.request("DELETE", "/api/account", json={"confirm": True}).status_code
        == 401
    )
    assert client.delete("/api/account", headers={"Authorization": auth}).status_code == 422
    assert (
        client.request(
            "DELETE",
            "/api/account",
            headers={"Authorization": auth},
            json={"confirm": False},
        ).status_code
        == 422
    )


def test_delete_account_removes_only_owned_data_and_unshared_resume_cache():
    auth, user_id, email = _register("account-delete-owner")
    _, other_user_id, _ = _register("account-delete-other")
    shared_key = f"shared-{uuid.uuid4().hex}"
    private_key = f"private-{uuid.uuid4().hex}"
    orphan_key = f"orphan-{uuid.uuid4().hex}"

    own_analysis = _save_analysis(user_id, private_key)
    shared_own_analysis = _save_analysis(user_id, shared_key)
    other_analysis = _save_analysis(other_user_id, shared_key)
    own_run = _save_run(user_id, own_analysis)
    other_run = _save_run(other_user_id, other_analysis)
    for key in (shared_key, private_key, orphan_key):
        save_json("parsed_resumes", key, {"skills": ["Python"]})

    response = client.request(
        "DELETE",
        "/api/account",
        headers={"Authorization": auth},
        json={"confirm": True},
    )

    assert response.status_code == 200, response.text
    assert "deleted successfully" in response.json()["message"].lower()
    assert response.json()["deleted"] == {
        "analyses": 2,
        "discovery_runs": 1,
        "parsed_resumes": 1,
    }
    assert load_json("analyses", own_analysis) is None
    assert load_json("analyses", shared_own_analysis) is None
    assert load_json("analyses", other_analysis) is not None
    assert load_json("discovery_runs", own_run) is None
    assert load_json("discovery_runs", other_run) is not None
    assert load_json("parsed_resumes", shared_key) is not None
    assert load_json("parsed_resumes", private_key) is None
    assert load_json("parsed_resumes", orphan_key) is not None
    assert auth_service.get_user_by_id(user_id) is None
    assert auth_service.get_user_by_id(other_user_id) is not None
    assert load_json("users", auth_service._email_key(email)) is None

    # The existing token is rejected after its identity is removed. Calling the
    # service again is still safe and produces an empty, successful cleanup.
    assert client.get("/api/auth/me", headers={"Authorization": auth}).status_code == 401
    repeated = account_service.delete_account(user_id)
    assert repeated["deleted"] == {
        "analyses": 0,
        "discovery_runs": 0,
        "parsed_resumes": 0,
    }


def test_delete_json_is_safe_and_idempotent_for_json_backend():
    collection = f"account-delete-{uuid.uuid4().hex}"
    key = f"record-{uuid.uuid4().hex}"
    save_json(collection, key, {"value": "delete me"})

    assert delete_json(collection, key) is True
    assert delete_json(collection, key) is False
    with pytest.raises(ValueError, match="key"):
        delete_json(collection, "../outside")


def test_delete_json_uses_id_scoped_mongo_delete(monkeypatch):
    client = mongomock.MongoClient(tz_aware=True)
    database_name = f"account_delete_{uuid.uuid4().hex}"
    monkeypatch.setattr(database, "_client", client)
    monkeypatch.setattr(settings, "storage_backend", "mongodb")
    monkeypatch.setattr(settings, "mongodb_database", database_name)
    collection = database_name + "_records"
    key = f"record-{uuid.uuid4().hex}"
    save_json(collection, key, {"value": "delete me"})

    assert delete_json(collection, key) is True
    assert delete_json(collection, key) is False

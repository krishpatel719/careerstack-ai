"""Persistence facade for runtime records.

Production uses MongoDB Atlas. JSON remains an explicit fallback for offline
demos, migration input, and fast tests. Service code keeps the same small API,
so switching backends does not leak database concerns into scoring or routes.
"""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import get_database

DATA_DIR = Path("./data")
SCHEMA_VERSION = 1
_JSON_WRITE_LOCK = threading.Lock()


def _validate_component(name: str, value: str) -> None:
    """Require a single, non-special filesystem/key component."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        raise ValueError(f"{name} must not contain path separators or traversal")

    candidate = Path(value)
    if candidate.anchor or candidate.drive or candidate.name != value:
        raise ValueError(f"{name} must be a single path component")


def _validate_field_path(field: str) -> str:
    if not isinstance(field, str) or not field or field.startswith("$") or "\x00" in field:
        raise ValueError("field must be a non-empty MongoDB field path")
    return field


def _collection_dir(collection: str) -> Path:
    _validate_component("collection", collection)
    data_dir = DATA_DIR.resolve()
    path = DATA_DIR / collection
    path.mkdir(parents=True, exist_ok=True)

    # A collection path can be lexically safe while resolving outside the
    # configured data directory (for example, through a pre-existing symlink).
    resolved = path.resolve()
    try:
        resolved.relative_to(data_dir)
    except ValueError as exc:
        raise ValueError("collection must resolve inside DATA_DIR") from exc
    return resolved


def _json_path(collection: str, key: str) -> Path:
    _validate_component("key", key)
    return _collection_dir(collection) / f"{key}.json"


def _mongo_collection(collection: str):
    _validate_component("collection", collection)
    return get_database()[collection]


def _mongo_record(collection: str, data: dict) -> dict:
    """Add internal MongoDB metadata while preserving public ISO timestamps."""
    record = {**data, "schema_version": SCHEMA_VERSION}
    if collection == "api_quota" and data.get("source") and data.get("period"):
        record["source_period"] = f'{data["source"]}|{data["period"]}'
    timestamp_field = {
        "role_profiles": "sampled_at",
        "job_source_cache": "cached_at",
    }.get(collection)
    if timestamp_field:
        try:
            expires_at = datetime.fromisoformat(str(data[timestamp_field]))
        except (KeyError, TypeError, ValueError):
            pass
        else:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            record["_expires_at"] = expires_at
    return record


def _public_document(document: dict | None) -> dict | None:
    """Hide backend metadata while preserving the historical service shape."""
    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    result.pop("schema_version", None)
    result.pop("source_period", None)
    result.pop("_expires_at", None)
    return result


def _json_save_unlocked(collection: str, key: str, data: dict) -> None:
    path = _json_path(collection, key)
    serialized = json.dumps(data, indent=2)
    temporary_path: Path | None = None

    try:
        # The temporary file shares the destination directory so replace is an
        # atomic same-filesystem operation. Each save gets a unique name.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())

        # Windows can transiently deny replacement while another writer is
        # replacing the same destination. Retry the complete temporary file.
        for attempt in range(100):
            try:
                os.replace(temporary_path, path)
                break
            except PermissionError:
                if attempt == 99:
                    raise
                time.sleep(min(0.001 * (attempt + 1), 0.01))
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_json(collection: str, key: str, data: dict) -> None:
    """Insert or replace one record, keyed by the legacy hashed/UUID key."""
    _validate_component("key", key)
    if not isinstance(data, dict):
        raise TypeError("stored data must be a dictionary")
    if "_id" in data:
        raise ValueError("stored data must not include MongoDB's reserved _id field")

    if settings.storage_backend == "mongodb":
        _mongo_collection(collection).replace_one(
            {"_id": key}, _mongo_record(collection, data), upsert=True
        )
        return
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    with _JSON_WRITE_LOCK:
        _json_save_unlocked(collection, key, data)


def delete_json(collection: str, key: str) -> bool:
    """Delete one record, returning whether it existed.

    Deletion is idempotent: a missing record is a successful ``False``
    result, not an error. Collection and key validation plus the resolved
    directory boundary keep the JSON path from becoming a filesystem escape.
    """
    _validate_component("key", key)

    if settings.storage_backend == "mongodb":
        return _mongo_collection(collection).delete_one({"_id": key}).deleted_count == 1
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    with _JSON_WRITE_LOCK:
        path = _json_path(collection, key)
        for attempt in range(5):
            try:
                path.unlink()
                return True
            except FileNotFoundError:
                return False
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(min(0.001 * (attempt + 1), 0.01))
    raise AssertionError("unreachable")


def create_json_if_absent(collection: str, key: str, data: dict) -> bool:
    """Atomically create a record, returning False when its key exists."""
    _validate_component("key", key)
    if not isinstance(data, dict):
        raise TypeError("stored data must be a dictionary")
    if "_id" in data:
        raise ValueError("stored data must not include MongoDB's reserved _id field")

    if settings.storage_backend == "mongodb":
        try:
            _mongo_collection(collection).insert_one(
                {"_id": key, **data, "schema_version": SCHEMA_VERSION}
            )
            return True
        except DuplicateKeyError:
            return False
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    with _JSON_WRITE_LOCK:
        path = _json_path(collection, key)
        if path.exists():
            return False
        _json_save_unlocked(collection, key, data)
        return True


def load_json(collection: str, key: str) -> dict | None:
    """One record by key, or None."""
    _validate_component("key", key)
    if settings.storage_backend == "mongodb":
        return _public_document(_mongo_collection(collection).find_one({"_id": key}))
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    path = _json_path(collection, key)
    if not path.exists():
        return None

    # Windows can briefly deny a read while another thread atomically replaces
    # the same file. Retry only that narrow transient condition.
    for attempt in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(min(0.001 * (attempt + 1), 0.01))
    raise AssertionError("unreachable")


def list_keys(collection: str) -> list[str]:
    """All record keys in a collection."""
    if settings.storage_backend == "mongodb":
        return sorted(_mongo_collection(collection).distinct("_id"))
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")
    path = _collection_dir(collection)
    return sorted(item.stem for item in path.glob("*.json"))


def load_by_field(collection: str, field: str, value: object) -> dict | None:
    """One record by an internal field path, without a collection scan."""
    _validate_field_path(field)
    if settings.storage_backend == "mongodb":
        return _public_document(_mongo_collection(collection).find_one({field: value}))
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    for key in list_keys(collection):
        record = load_json(collection, key)
        if record and record.get(field) == value:
            return record
    return None


def list_records(collection: str) -> list[dict]:
    """All records in one collection without their backend-specific _id."""
    if settings.storage_backend == "mongodb":
        return [_public_document(document) for document in _mongo_collection(collection).find({})]
    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")
    return [record for key in list_keys(collection) if (record := load_json(collection, key))]


def increment_json_field(
    collection: str,
    key: str,
    field: str,
    amount: int = 1,
    set_fields: dict | None = None,
) -> int:
    """Atomically increment one numeric field and return the new value.

    MongoDB performs this as one ``$inc``. The JSON fallback uses a process
    lock, which is sufficient for the single-process offline/demo path.
    """
    _validate_component("key", key)
    _validate_field_path(field)
    updates = dict(set_fields or {})

    if settings.storage_backend == "mongodb":
        document = _mongo_collection(collection).find_one_and_update(
            {"_id": key},
            {
                "$inc": {field: amount},
                "$set": updates,
                "$setOnInsert": {"schema_version": SCHEMA_VERSION},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int((document or {}).get(field, 0))

    if settings.storage_backend != "json":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend!r}")

    with _JSON_WRITE_LOCK:
        record = load_json(collection, key) or {field: 0}
        record[field] = int(record.get(field, 0)) + amount
        record.update(updates)
        _json_save_unlocked(collection, key, record)
        return int(record[field])

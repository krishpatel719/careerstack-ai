import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app import store


@pytest.fixture
def store_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(store, "DATA_DIR", data_dir)
    return data_dir


def test_nested_unicode_data_round_trip(store_data_dir: Path) -> None:
    collection = "профили"
    key = "résumé-2026_✓.v1"
    data = {
        "candidate": {"name": "Zoë 東京", "skills": ["Python", "SQL"]},
        "notes": [{"nested": {"message": "café ☕", "enabled": True}}],
    }

    store.save_json(collection, key, data)

    destination = store_data_dir / collection / f"{key}.json"
    assert json.loads(destination.read_text(encoding="utf-8")) == data
    assert store.load_json(collection, key) == data
    assert store.list_keys(collection) == [key]
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.parametrize(
    "key",
    [
        "../escaped",
        "..\\escaped",
        "nested/key",
        "nested\\key",
        "/absolute",
        "C:\\absolute",
        ".",
        "..",
        "",
    ],
)
def test_save_json_rejects_unsafe_keys(store_data_dir: Path, key: str) -> None:
    with pytest.raises(ValueError, match="key"):
        store.save_json("safe_collection", key, {"unsafe": True})

    assert not store_data_dir.exists()


@pytest.mark.parametrize(
    "collection",
    [
        "../escaped",
        "..\\escaped",
        "nested/child",
        "nested\\child",
        "/absolute",
        "C:\\absolute",
        ".",
        "..",
        "",
    ],
)
def test_storage_apis_reject_unsafe_collections(store_data_dir: Path, collection: str) -> None:
    with pytest.raises(ValueError, match="collection"):
        store.save_json(collection, "safe_key", {"unsafe": True})

    assert not store_data_dir.exists()


def test_load_retries_transient_windows_replace_denial(
    store_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.save_json("read_retry", "record", {"value": 7})
    original_read_text = Path.read_text
    calls = 0

    def transient_read(path: Path, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("temporarily locked by atomic replace")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", transient_read)
    assert store.load_json("read_retry", "record") == {"value": 7}
    assert calls == 2


def test_repeated_and_concurrent_writes_are_always_valid_json(store_data_dir: Path) -> None:
    collection = "concurrent"
    key = "same-record"
    destination = store_data_dir / collection / f"{key}.json"
    payloads = [
        {
            "writer": writer,
            "iteration": iteration,
            "items": [{"index": item, "text": f"writer-{writer}-item-{item}"} for item in range(200)],
        }
        for writer in range(8)
        for iteration in range(8)
    ]
    for payload in payloads:
        store.save_json(collection, key, payload)
        assert store.load_json(collection, key) == payload

    start = threading.Barrier(len(payloads))
    errors: list[Exception] = []

    def write(payload: dict) -> None:
        start.wait()
        try:
            store.save_json(collection, key, payload)
        except Exception as exc:  # pragma: no cover - assertion reports the worker failure
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        futures = [executor.submit(write, payload) for payload in payloads]
        for future in futures:
            future.result()

    assert not errors
    assert store.load_json(collection, key) in payloads
    assert list(destination.parent.glob("*.json")) == [destination]

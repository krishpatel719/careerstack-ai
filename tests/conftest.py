"""Test-wide fixtures.

The important one is isolate_data_dir: it selects the repository's JSON
fallback and points it at a temporary directory for the whole test session, so
service tests never write into the real ./data/ or contact MongoDB Atlas.

This is not hypothetical tidiness. Before this existed, running the suite
wrote real cache entries into ./data/role_profiles/ -- including a
"backend developer"/"Ahmedabad" profile containing a single skill
("python"), seeded by a route test. The demo resume has Python, so its
keyword coverage scored 1/1 = 100%, and demo_before.pdf came out at 81.7
instead of its true 45.4. The prep_demo numbers and the numbers the
running app produced silently disagreed, and nothing failed to flag it.

Tests that deliberately exercise the cache (test_cache.py,
test_analyze_degraded.py, the discovery route tests) still write real
files -- they just write them somewhere disposable now.
"""

import os

# Test collection imports application modules before fixtures run. Give the
# settings loader a non-production secret first so a fresh checkout does not
# need a developer-local .env merely to collect and run the suite.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production"
# Most service tests exercise repository behaviour through the fast, isolated
# JSON fallback. test_store_mongodb.py explicitly switches to mongomock and
# exercises the MongoDB adapter independently.
os.environ["STORAGE_BACKEND"] = "json"

import pytest

from app import store


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Prevent one test's client-IP windows from throttling another test."""
    from app.main import rate_limiter

    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture(autouse=True, scope="session")
def isolate_data_dir(tmp_path_factory):
    """Redirect store.DATA_DIR at a temp directory for the whole session.

    Session-scoped rather than per-test: several tests write a record in
    one step and read it back in another through the service layer, so a
    per-test directory would break them for no benefit. The goal is
    isolation from ./data/, not isolation between tests.
    """
    original = store.DATA_DIR
    store.DATA_DIR = tmp_path_factory.mktemp("data")
    yield
    store.DATA_DIR = original

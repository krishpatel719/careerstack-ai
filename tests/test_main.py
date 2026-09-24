"""Tests for the FastAPI routes in main.py.

Covers only the parts of /api/analyze that don't need a live Groq or
Adzuna call (input validation, needs_ocr), plus the two simple GET
routes -- consistent with the rest of this suite staying network-free.
The full pipeline (parse_resume + get_or_mine + scoring) was verified
manually against a real fixture; see the conversation, not this file.

/api/analyze and /api/analyze/{id} require auth now -- see test_auth.py
for the auth flow itself; here each test just registers its own throwaway
user (a fresh, unique email per test, so tests never collide with each
other's leftover ./data/users/ state across runs) to get past the
Depends(get_current_user) gate.
"""

import uuid
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def _auth_headers() -> dict:
    email = f"test-{uuid.uuid4().hex}@example.com"
    response = client.post(
        "/api/auth/register", json={"name": "Test User", "email": email, "password": "testpass123"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_root_and_browser_routes_serve_built_react_product():
    react_index = Path(__file__).parents[1] / "frontend" / "dist" / "index.html"
    if not react_index.exists():
        pytest.skip("React production build not present")

    expected = react_index.read_bytes()
    root = client.get("/")
    route = client.get("/app/jobs", headers={"Accept": "text/html"})

    assert root.status_code == 200
    assert root.headers["content-type"].startswith("text/html")
    assert root.content == expected
    assert route.status_code == 200
    assert route.content == expected


def test_built_react_favicon_is_served_when_available():
    favicon = Path(__file__).parents[1] / "frontend" / "dist" / "favicon.svg"
    if not favicon.exists():
        pytest.skip("React production build not present")

    response = client.get("/favicon.svg")
    compatibility = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.content == favicon.read_bytes()
    assert compatibility.status_code == 200
    assert compatibility.content == favicon.read_bytes()


@pytest.mark.parametrize("backup_path", ["/index_v1.html.bak", "/index_v2.html.bak", "/static/index_v1.html.bak"])
def test_backup_html_is_not_publicly_served(backup_path):
    response = client.get(backup_path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", ["/", "/api/health", "/api/does-not-exist"])
def test_security_headers_are_present_on_html_api_and_404_responses(path):
    response = client.get(path)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "font-src 'self'" in csp
    assert "worker-src 'self' blob:" in csp
    assert "script-src 'self'" in csp


def test_health_authenticated_and_api_responses_are_not_stored_in_caches():
    health = client.get("/api/health")
    unauthenticated_analyses = client.get("/api/analyses")
    api_404 = client.get("/api/does-not-exist")

    assert health.headers["Cache-Control"] == "no-store"
    assert unauthenticated_analyses.status_code == 401
    assert unauthenticated_analyses.headers["Cache-Control"] == "no-store"
    assert api_404.headers["Cache-Control"] == "no-store"


def test_unknown_api_path_returns_actionable_json_404():
    response = client.get("/api/analyses/does-not-exist-endpoint")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "API endpoint not found" in detail
    assert "/api/health" in detail
    assert "/docs" in detail


def test_production_demo_mode_emits_startup_warning(monkeypatch, caplog):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "demo_mode", True)

    with caplog.at_level("WARNING", logger="app.main"):
        with TestClient(app):
            pass

    assert "DEMO_MODE is enabled in production" in caplog.text


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["demo_mode"], bool)


def test_get_missing_analysis_returns_404():
    response = client.get("/api/analyze/does-not-exist", headers=_auth_headers())
    assert response.status_code == 404
    assert "detail" in response.json()


def test_analyze_requires_auth():
    response = client.post(
        "/api/analyze",
        files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
        data={"role": "backend developer", "location": "India"},
    )
    assert response.status_code == 401


def test_analyze_rejects_unsupported_extension():
    response = client.post(
        "/api/analyze",
        files={"file": ("resume.txt", b"hello", "text/plain")},
        data={"role": "backend developer", "location": "India"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert ".txt" in response.json()["detail"]


@pytest.mark.parametrize(
    ("filename", "file_bytes", "expected_status", "expected_detail"),
    [
        ("resume.pdf", b"this is not a PDF", 422, "couldn't read this PDF"),
        ("resume.docx", b"this is not a DOCX", 422, "couldn't read this DOCX"),
        (
            "resume.doc",
            b"legacy binary document",
            400,
            "Legacy .doc files must be saved as .docx first",
        ),
    ],
)
def test_analyze_returns_plain_language_error_for_unreadable_or_legacy_word_files(
    filename, file_bytes, expected_status, expected_detail
):
    response = client.post(
        "/api/analyze",
        files={"file": (filename, file_bytes, "application/octet-stream")},
        data={"role": "backend developer", "location": "India"},
        headers=_auth_headers(),
    )

    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"]


def test_analyze_rejects_oversized_file():
    oversized = b"a" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/analyze",
        files={"file": ("resume.pdf", oversized, "application/pdf")},
        data={"role": "backend developer", "location": "India"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert "5MB" in response.json()["detail"]


def test_analyze_rejects_blank_role_or_location():
    response = client.post(
        "/api/analyze",
        files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
        data={"role": "  ", "location": "India"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert "required" in response.json()["detail"].lower()


def test_analyze_returns_422_for_a_blank_page_pdf():
    """No selectable text at all -- needs_ocr should fire with the exact
    plain-language message specified for this case.
    """
    doc = fitz.open()
    doc.new_page()
    blank_pdf_bytes = doc.tobytes()
    doc.close()

    response = client.post(
        "/api/analyze",
        files={"file": ("blank.pdf", blank_pdf_bytes, "application/pdf")},
        data={"role": "backend developer", "location": "India"},
        headers=_auth_headers(),
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "couldn't find any selectable text" in detail
    assert "export a text-based PDF" in detail

"""FastAPI app: routes only, zero logic. Every route validates its input,
calls a service, and returns the result -- see CLAUDE.md's routing rule.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_database, initialize_database
from app.dependencies import get_current_user
from app.models.user import UserPublic
from app.rate_limit import FixedWindowRateLimiter
from app.routers.account import router as account_router
from app.routers.auth import router as auth_router
from app.routers.discovery import router as discovery_router
from app.routers.job_map import router as job_map_router
from app.routers.opportunities import router as opportunities_router
from app.services.analyze import (
    NeedsOcrError,
    RoleProfileUnavailableError,
    list_user_analyses,
    run_analysis,
)
from app.services.extraction.text_extract import ExtractionError
from app.store import load_json

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

ANALYSES_COLLECTION = "analyses"

REACT_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
REACT_INDEX = REACT_DIST / "index.html"


CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        # React/Tailwind and the current interaction layer use inline style
        # attributes. Executable JavaScript remains restricted to self.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.storage_backend == "mongodb":
        # Fail startup if Atlas is unreachable or indexes cannot be created;
        # silently serving an app whose writes will fail is worse than a
        # clear deployment failure.
        initialize_database()

    if settings.environment == "production" and settings.demo_mode:
        logger.warning(
            "DEMO_MODE is enabled in production. Demo data is not isolated "
            "from real users; set DEMO_MODE=false before production exposure."
        )
    if settings.demo_mode:
        print("=" * 64)
        print("  DEMO_MODE IS ON")
        print("  Role profile mining will never hit the network -- only")
        print("  cached profiles are served. Run scripts/prep_demo.py first")
        print("  if the profiles you need aren't cached yet.")
        print("=" * 64)
    try:
        yield
    finally:
        close_database()


app = FastAPI(title="CareerStack AI - Resume Analysis", lifespan=lifespan)
rate_limiter = FixedWindowRateLimiter()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def response_security_policy(request: Request, call_next):
    """Apply rate limits and transport-independent response hardening."""
    bucket = None
    if request.method == "POST" and request.url.path == "/api/auth/register":
        bucket = "auth_register"
    elif request.method == "POST" and request.url.path == "/api/auth/login":
        bucket = "auth_login"
    elif request.method == "POST" and request.url.path == "/api/analyze":
        bucket = "resume_analysis"
    elif request.method == "POST" and request.url.path == "/api/discovery/run":
        bucket = "discovery_start"
    elif request.url.path == "/api/opportunities":
        bucket = "opportunity_search"
    elif request.url.path == "/api/job-map":
        bucket = "job_map_read"

    if bucket:
        client_ip = request.client.host if request.client else "unknown"
        result = rate_limiter.check(client_ip, bucket)
        if not result.allowed:
            response = JSONResponse(
                status_code=429,
                headers={"Retry-After": str(result.retry_after)},
                content={
                    "detail": "Too many requests for this action. Please wait and try again."
                },
            )
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)

    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY

    is_api_path = request.url.path == "/api" or request.url.path.startswith("/api/")
    has_auth = bool(request.headers.get("authorization"))
    if is_api_path or has_auth:
        # API data and authentication failures must not remain in browser,
        # proxy, or shared-cache storage between users.
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safety net for every route: never let a raw traceback reach the
    client. Explicitly-raised HTTPExceptions (with their own plain-
    language detail messages) bypass this and are handled by FastAPI's
    default HTTPException handling instead.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong while processing your request. Please try again."},
    )


app.include_router(auth_router)
app.include_router(discovery_router)
app.include_router(opportunities_router)
app.include_router(job_map_router)
app.include_router(account_router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> Response:
    """Return an actionable response for mistyped API routes, and serve the
    React shell for client-side routes.

    The frontend is a single-page app: React Router owns /upload, /auth,
    /app/jobs/map and the rest, and those paths have no server route. They
    work while navigating inside the app, but a refresh, a bookmark or a
    shared link is a fresh GET the server has never heard of -- without
    this fallback the user gets raw JSON instead of the product.

    /api/* keeps the JSON 404: an unknown API path is a real error, and
    answering it with an HTML page would turn a clear mistake into a
    confusing one for anyone calling the API.
    """
    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={
                "detail": (
                    "API endpoint not found. Use /api/health for service status "
                    "or /docs for the API reference."
                )
            },
        )

    # Only extensionless paths are client-side routes. A request carrying a
    # file extension is asking for a file, so it must keep 404ing:
    #
    #   - /assets/missing.js would otherwise be handed HTML where the
    #     browser expects JavaScript, failing later and less clearly.
    #   - /index_v1.html.bak must stay a hard 404 rather than resolving to
    #     the live app, which would mask whether a stray backup is exposed.
    #     tests/test_main.py asserts exactly that.
    last_segment = path.rsplit("/", 1)[-1]
    looks_like_a_file = "." in last_segment

    if not looks_like_a_file and REACT_INDEX.exists():
        return FileResponse(REACT_INDEX, media_type="text/html", status_code=200)

    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the built React product shell."""
    if not REACT_INDEX.exists():
        raise HTTPException(
            status_code=503,
            detail="The frontend build is missing. Run npm --prefix frontend run build.",
        )
    return FileResponse(REACT_INDEX, media_type="text/html")


if (REACT_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=REACT_DIST / "assets"), name="react-assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_compat() -> FileResponse:
    """Serve the SVG favicon for browsers that request the legacy path."""
    return await favicon()


@app.get("/favicon.svg", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the built product favicon without exposing the whole dist tree."""
    path = REACT_DIST / "favicon.svg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/svg+xml")


@app.get("/career-workspace.jpg", include_in_schema=False)
async def career_workspace_image() -> FileResponse:
    path = REACT_DIST / "career-workspace.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/resume-review.jpg", include_in_schema=False)
async def resume_review_image() -> FileResponse:
    path = REACT_DIST / "resume-review.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "demo_mode": settings.demo_mode}


@app.get("/api/analyses")
async def list_analyses(current_user: UserPublic = Depends(get_current_user)) -> list[dict]:
    return list_user_analyses(current_user.user_id)


@app.get("/api/analyze/{analysis_id}")
async def get_analysis(
    analysis_id: str, current_user: UserPublic = Depends(get_current_user)
) -> dict:
    analysis = load_json(ANALYSES_COLLECTION, analysis_id)
    # Same 404 for "doesn't exist" and "belongs to someone else" -- a 403
    # here would confirm the ID is real, just not yours.
    if analysis is None or analysis.get("user_id") != current_user.user_id:
        raise HTTPException(status_code=404, detail="No analysis found with that ID.")
    return analysis


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    role: str = Form(...),
    location: str = Form(...),
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension or filename}'. "
                "Upload a PDF or Word document (.pdf, .docx). Legacy .doc files "
                "must be saved as .docx first."
            ),
        )

    # Read at most one byte beyond the limit. UploadFile.read(size) keeps an
    # oversized request from being materialised in full before rejection; the
    # reverse proxy should still enforce an equivalent request-body limit.
    file_bytes = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File is too large. Please upload a resume under 5MB.",
        )

    role = role.strip()
    location = location.strip()
    if not role or not location:
        raise HTTPException(status_code=400, detail="Both role and location are required.")

    try:
        return await run_analysis(file_bytes, filename, role, location, current_user.user_id)
    except NeedsOcrError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExtractionError as exc:
        logger.warning("Extraction failed for %s: %s", filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RoleProfileUnavailableError as exc:
        # run_analysis already tried get_or_mine and the most-recent-
        # cached-profile-for-any-role fallback; there is truly nothing to
        # score against.
        logger.warning("No role profile available at all for role=%r location=%r: %s", role, location, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        # DEMO_MODE with no cached parse for this exact file -- see
        # parse_cache.py's get_or_parse. The only remaining source of a
        # bare RuntimeError reaching here; get_or_mine's own RuntimeError
        # is already absorbed inside run_analysis's fallback handling.
        logger.warning("Resume parse cache miss in DEMO_MODE for %s: %s", filename, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/{full_path:path}", include_in_schema=False)
async def react_spa_fallback(full_path: str, request: Request) -> FileResponse:
    """Allow React BrowserRouter URLs such as /auth and /app/jobs.

    API routes and legacy backup paths must remain 404s. Only a browser HTML
    navigation gets the SPA shell; this prevents the fallback from masking
    API errors or exposing sibling static backups.
    """
    if full_path == "api" or full_path.startswith("api/") or full_path.endswith(".bak"):
        raise HTTPException(status_code=404, detail="Not Found")
    if REACT_INDEX.exists() and "text/html" in request.headers.get("accept", ""):
        return FileResponse(REACT_INDEX, media_type="text/html")
    raise HTTPException(status_code=404, detail="Not Found")

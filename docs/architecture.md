# CareerStack AI — Architecture Requirements and Boundaries

**Status:** Current implementation baseline  
**Last reviewed:** 2026-09-25

## 1. System shape

CareerStack is a same-origin web application:

```text
Browser
  |
  +-- React 19 + TypeScript + Vite
        |
        +-- FastAPI /api routes
              |
              +-- auth, account, analysis, discovery, opportunities, job-map services
                    |
                    +-- JSON repository (local/tests/demo)
                    +-- MongoDB repository (optional production persistence)
                    +-- Groq, Adzuna, JSearch, approved public ATS sources
                    +-- local sentence-transformers MiniLM model
```

The production backend serves the compiled frontend from `frontend/dist`. The Vite development server may run on port 5173 and proxies API requests to the backend.

## 2. Layering requirements

### Routers

Routers are HTTP adapters only. They may:

- parse and validate request data;
- apply authentication dependencies;
- call one or more services;
- map domain errors to HTTP responses; and
- shape a public response.

Routers shall not contain scoring, ranking, provider orchestration, date arithmetic, or persistence algorithms.

### Services

Services own application behavior and algorithms:

- `services/extraction/` — file text/layout extraction and structured parsing;
- `services/roleprofile/` — role-profile mining and caching;
- `services/scoring/` — deterministic scoring and action-plan assembly;
- `services/jobs/` — provider-specific adapters and quota behavior;
- `services/discovery.py` — resume-backed discovery orchestration;
- `services/opportunities.py` — resume-free search;
- `services/job_map.py` — persisted map reads and job-map data access;
- `services/auth.py` and `services/account.py` — identity and account lifecycle.

External calls shall be wrapped with controlled retry behavior. A provider adapter shall return an empty collection on permanent or transient provider failure so the surrounding run can continue.

### Models

Pydantic models define request and response contracts. Models shall not call providers, access storage, or perform scoring.

## 3. Data and persistence

### JSON mode

- `STORAGE_BACKEND=json` is the zero-configuration default.
- Records are stored under `data/`.
- Tests and offline demos use isolated temporary storage.
- JSON caches are part of the demo data lifecycle and shall not be mistaken for source code.

### MongoDB mode

- `STORAGE_BACKEND=mongodb` requires `MONGODB_URI`.
- One process-wide PyMongo client is created lazily and closed during FastAPI lifespan shutdown.
- Startup pings Atlas and creates indexes; failure to initialize shall fail fast.
- TTL indexes support the implemented cache/retention windows.
- `app/store.py` is the repository facade used by services so the backend choice is not leaked into algorithms.

## 4. Data flows

### Analysis

1. FastAPI validates upload type, size, role, and location.
2. The extraction service obtains text and layout signals.
3. The parser obtains or creates a structured `ParsedResume`.
4. The role-profile service obtains a cached or mined role profile.
5. Keyword, semantic, formatting, and experience services calculate independent components.
6. The ATS service combines components, rounds output, and assembles the action plan.
7. The analysis is persisted and associated with the authenticated user.
8. The frontend renders score breakdowns, confidence metadata, and actions.

### Discovery

1. The client submits an owned analysis ID.
2. The service creates a pending run.
3. A background task queries enabled approved adapters.
4. Results are normalized, deduplicated, cached, scored, and persisted.
5. The client polls the owner-scoped run endpoint.
6. The UI displays attribution, source caveats, and match breakdowns.

### Job map

1. An operator or scheduler runs `scripts/ingest_job_map.py`.
2. Configured sources are fetched, normalized, deduplicated, and geocoded using curated location data.
3. MongoDB receives idempotent upserts with provenance and first/last-seen timestamps.
4. `/api/job-map` reads only this snapshot and never calls a provider.

## 5. Frontend boundaries

The frontend may own:

- presentation state;
- browser navigation;
- request/response handling through `src/lib/api.ts`;
- user-visible formatting and chart visualization;
- local PDF preview.

The frontend shall not:

- calculate ATS or job match scores;
- duplicate provider ranking logic;
- expose secrets;
- treat cached sample data as live provider output.

## 6. Trust and security boundaries

- JWTs and passwords are security-sensitive and shall never be written to logs or client-visible errors.
- Passwords are hashed with bcrypt; JWT signing requires an explicit non-blank secret.
- User-owned IDs are checked server-side for every analysis, discovery run, and job lookup.
- Unknown and unauthorized records use indistinguishable `404` behavior where the implementation specifies it.
- Upload size and extension validation occur before expensive processing.
- The backend applies a restrictive CSP and security headers.
- API/authenticated responses use `no-store` to prevent cross-user browser/proxy cache leakage.
- Provider adapters preserve original posting URLs and attribution.
- No adapter may bypass authentication, paywalls, CAPTCHAs, or provider rate limits.

## 7. Cache and quota policy

| Data | Intended lifetime | Enforcement |
|---|---:|---|
| Parsed resume | Implementation-defined cache | Application cache; demo must have a prewarmed entry |
| Role profile | 7 days | Application checks plus Mongo TTL where enabled |
| Job-source response | 6 hours | Per-source cache |
| Persistent job-map observation | 90 days after latest observation | Mongo retention/TTL policy |
| JSearch monthly usage | Calendar month | Local quota counter checked before calls |

The product shall expose source degradation as a normal outcome. Optional providers shall not be required for tests or offline demo startup.

## 8. Required operational jobs

- `scripts/prep_demo.py` — warm the caches and demo account for offline demonstration.
- `scripts/migrate_json_to_mongodb.py` — preview and idempotently import JSON records; source JSON is not deleted.
- `scripts/check_quota.py` — report JSearch consumption.
- `scripts/verify_greenhouse.py` — verify configured Greenhouse boards still resolve.
- `scripts/ingest_job_map.py` — refresh the persistent job-map snapshot.

## 9. CI and release gates

A release candidate is acceptable only when all of the following pass:

```text
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m pytest -q
npm --prefix frontend exec tsc -- --noEmit
```

The release checklist shall also verify:

- `JWT_SECRET` is present and non-blank in the target environment;
- `STORAGE_BACKEND` and MongoDB settings are intentional;
- `DEMO_MODE` is false in production;
- approved provider credentials and subscriptions are configured;
- source boards and quota budgets are valid;
- the frontend build is present before starting FastAPI;
- account deletion, user isolation, and privacy/terms pages are available.

## 10. Architecture decisions that must not be silently changed

- LLM output is never the source of a score or date calculation.
- JSON remains the default local/test/demo storage; MongoDB is explicit opt-in.
- Job sources are approved adapters, not arbitrary scrapers.
- Provider failures are isolated and cached/quota-controlled.
- The router/service boundary is part of the testability contract.
- User-owned data is server-enforced and not inferred by the client.

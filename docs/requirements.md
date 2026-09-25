# CareerStack AI — Product and System Requirements

**Status:** Current implementation baseline  
**Last reviewed:** 2026-09-25  
**Scope:** The single `careerstack-ai` codebase in this repository

## 1. Product definition

CareerStack AI is an ATS-focused resume analysis and job-discovery product for students, early-career applicants, and job seekers.

A user registers or signs in, uploads a PDF or DOCX resume, supplies a target role and location, and receives:

- a deterministic ATS Parse Score;
- a deterministic Role Fit Score based on a sampled role profile;
- an evidence-based action plan ordered by potential point recovery; and
- optional job discovery and a read-only job map built from approved sources.

The product is an academic Software Group Project. It should remain understandable, reproducible, and defensible rather than expanding into a general-purpose recruiting platform.

## 2. Actors

| Actor | Needs | Permissions |
|---|---|---|
| Anonymous visitor | Understand the product and view public pages | Landing, authentication, legal pages; no analysis or discovery |
| Registered user | Analyse a resume, save analyses, search opportunities, view the job map | Access only to records owned by that user |
| Demo user | Rehearse the product without external calls | Use pre-warmed cached data only while `DEMO_MODE=true` |
| Operator | Deploy, warm caches, migrate data, and monitor quotas | Configure environment, run operational scripts |
| Scheduler | Refresh the persistent job map | Run the approved ingestion job against MongoDB and configured sources |

## 3. Product principles

1. **The LLM never produces a score.** Groq may extract structured resume data or explain already-computed values. All arithmetic, weighting, date calculations, and ranking formulas remain deterministic Python.
2. **Scores are reproducible and explainable.** Every user-visible number must be traceable to a scoring module and a stable formula.
3. **Provider failures are isolated.** A dead or rate-limited job source must not make a discovery run fail when another source can return results.
4. **Approved sources only.** Use provider APIs and documented public ATS JSON endpoints. Do not add HTML scrapers that bypass access controls, CAPTCHAs, paywalls, or rate limits.
5. **User data is isolated.** Analyses, discovery runs, and account data are owned by authenticated users and must not be exposed across accounts.
6. **Offline demos are deterministic.** `DEMO_MODE=true` blocks external model and provider calls; uncached operations fail with an actionable message rather than silently going online.

## 4. Scope

### 4.1 In scope

- Authentication with email/password and bearer JWTs.
- Resume upload for `.pdf` and `.docx` files.
- Text and layout extraction from PDFs and DOCX files.
- LLM-assisted structured resume parsing.
- Role-profile mining from approved job-market data.
- Deterministic keyword, semantic, formatting, and experience scoring.
- Action plan with quantified and unquantified recommendations.
- Saved analysis history scoped to the signed-in user.
- Resume-backed job discovery through approved job-source adapters.
- Resume-free opportunity search through approved sources.
- Persistent MongoDB-backed job map with scheduled ingestion.
- JSON storage for local development, tests, and offline demos.
- MongoDB Atlas as an optional production persistence backend.
- Account deletion and associated-data deletion.
- Operational scripts for demo preparation, migration, quota checks, and source verification.

### 4.2 Out of scope

Do not add these without a new explicit product decision:

- Resume bullet rewriting.
- Application tracking or an applicant-tracking system.
- OCR for scanned/image-only resumes.
- LangGraph or other additional orchestration frameworks.
- Docker packaging unless explicitly re-scoped.
- Arbitrary job-board HTML scraping.
- Resume retention or content copying beyond what an approved provider permits.

## 5. Functional requirements

### FR-1 — Configuration and startup

- The application shall load settings from `.env` and environment variables.
- Python shall be 3.11 or newer; Node.js shall be 20 or newer for the frontend.
- A non-blank `JWT_SECRET` shall be required at startup. The application shall not use an insecure fallback.
- When `STORAGE_BACKEND=mongodb`, `MONGODB_URI` shall be required and shall use a `mongodb://` or `mongodb+srv://` scheme.
- `MONGODB_DATABASE` shall contain only letters, numbers, `_`, or `-`.
- When `ENVIRONMENT=production` and `DEMO_MODE=true`, startup shall emit a prominent warning.
- The production server shall serve the built React shell from `frontend/dist`; if the shell is absent, the root route shall return a clear `503`.

### FR-2 — Authentication and account lifecycle

- A user shall be able to register with name, valid email, and password.
- Passwords shall contain at least 8 characters and no more than 72 UTF-8 bytes because of bcrypt.
- Registration shall return `201` with a bearer token and public user data.
- Login shall return a token and public user data.
- Invalid credentials shall return the same generic message for unknown email and incorrect password.
- `GET /api/auth/me` shall return the current user.
- Password hashes shall never be returned by the API.
- A user shall be able to delete their account by sending an explicit confirmation of `true`.
- Account deletion shall remove or anonymize all user-owned records according to the storage implementation and return a count of deleted records.

### FR-3 — Resume upload and analysis

- The upload endpoint shall accept multipart form data with:
  - `file`: PDF or DOCX;
  - `role`: non-empty target role;
  - `location`: non-empty target location.
- The maximum upload size shall be 5 MiB.
- Unsupported extensions, including legacy `.doc`, shall be rejected with a user-facing explanation.
- Oversized files shall be rejected before full materialization where the request implementation permits.
- The system shall extract selectable text and layout signals before analysis.
- Scanned or image-only input shall produce a clear OCR-needed or extraction error; OCR itself is not supported.
- The LLM extraction output shall be validated against the `ParsedResume` schema.
- The resulting analysis shall belong to the authenticated user.
- A user shall be able to list their own analyses and retrieve one of their own analyses.
- Looking up an analysis owned by another user shall return the same `404` as an unknown analysis.
- A missing role profile or unavailable external dependency shall return an actionable `503` where cached fallback is not possible.

### FR-4 — Role profiles and market evidence

- A role profile shall be generated or retrieved for the normalized target role and location.
- The role profile shall be based on a sampled set of real postings, targeting approximately 40 usable postings where provider data allows.
- Each mined skill shall retain its posting frequency and category where available.
- The system shall expose role-profile sample quality and confidence metadata in the analysis.
- Role profiles shall be cached for 7 days.
- Job-source responses shall be cached for 6 hours.
- Caching shall be maintained in JSON mode and through MongoDB TTL indexes in MongoDB mode.

### FR-5 — ATS scoring

The overall score shall be calculated as:

```text
ATS_SCORE = 0.40 * keyword_coverage
          + 0.25 * semantic_fit
          + 0.20 * format_compliance
          + 0.15 * experience_alignment
```

The components shall each be normalized to `[0, 1]`; the product shall present the overall result as a rounded percentage or equivalent user-facing score.

#### Keyword coverage

- Coverage shall be frequency-weighted rather than binary.
- Matching shall use, in order:
  1. exact normalized skill matching;
  2. word-boundary matching over resume text;
  3. fuzzy matching using a RapidFuzz ratio of at least 90.
- Skills below the configured market-frequency noise threshold shall not dominate the result.
- The result shall include matched and missing skills with frequencies and categories.

#### Semantic fit

- Semantic similarity shall be calculated per role requirement, not once for the whole document.
- For each requirement, the system shall find the best matching resume line and average those maxima.
- MiniLM cosine values shall be calibrated to the `[0, 1]` range.
- The system shall not substitute whole-document similarity for per-requirement matching.

#### Format compliance

The implementation currently has nine deterministic checks:

- email present;
- phone present;
- sufficient extractable text;
- core experience/projects, education, and skills sections present;
- no tables where layout is measurable;
- single column where layout is measurable;
- reasonable length where page count is measurable;
- sufficient date information;
- standard bullet characters.

Checks that are not applicable to the input type shall be reported as skipped and excluded from points possible. A DOCX shall not receive unearned points for page/layout checks that were not measured.

#### Experience alignment

- Experience alignment shall be `0.7 * years_component + 0.3 * education_component`.
- Employment intervals shall be merged in Python to prevent double-counting overlapping roles.
- Date arithmetic shall not be delegated to the LLM.
- Projects may substitute for a missing Experience section only where the implementation explicitly documents and surfaces that substitution.

#### Action plan

- The system shall produce a prioritized action plan.
- Recommendations shall identify why they matter and, when measurable, the points they can recover.
- Unquantified evidence recommendations shall be clearly marked as unquantified and shall not be included in a projected score sum.
- The system shall retain score component breakdowns for explainability.

### FR-6 — Resume-backed job discovery

- A signed-in user shall be able to start a discovery run from an analysis they own.
- The server shall validate ownership and resume availability synchronously before creating a run.
- The response shall return immediately with a run ID and pending status.
- The run shall execute in a background task.
- The user shall be able to poll run status and retrieve the public run representation.
- The public representation shall omit internal `user_id` data.
- A run or job belonging to another user shall return `404`, not `403`.
- A user shall be able to request a job from a run by fingerprint.
- The requested job shall be re-scored against its own posting description when the route provides that behavior.
- The UI shall receive source attribution, original posting URLs, score breakdowns, and confidence caveats.

### FR-7 — Resume-free opportunities

- An authenticated user shall be able to search approved opportunities with `role`, `location`, and a bounded `limit`.
- The endpoint shall not accept a resume and shall not perform resume-specific ranking.
- Results shall be deduplicated and ranked using the approved opportunity ranking behavior.
- If a city-level search is thin, the system may widen the search according to the implemented market rules.
- The endpoint shall be rate-limited to protect provider quota.

### FR-8 — Persistent job map

- A scheduled ingestion command shall refresh approved job sources and persist normalized records to MongoDB.
- Public job-map requests shall read the persisted snapshot only and shall not call providers.
- Ingestion shall be idempotent, use bulk upserts, preserve source provenance, and retain records for 90 days after the latest successful observation.
- Canonical identity shall distinguish same-title jobs in different locations.
- Coordinates shall come only from curated location data; unknown locations shall not receive guessed coordinates.
- Map records shall expose sanitized external links.
- Job-map storage failure shall return a clear `503`.

### FR-9 — User interface

The React/Vite frontend shall provide routes for:

- `/` — landing page;
- `/auth` — registration and login;
- `/upload` — resume upload and analysis setup;
- `/app` — saved analyses/dashboard;
- `/app/jobs` — job discovery and opportunities;
- `/app/jobs/map` — persistent job map;
- `/account` — account management and deletion;
- `/privacy` and `/terms` — legal information.

The frontend shall use the backend API rather than duplicating scoring, provider, or persistence logic.

### FR-10 — Security and operational safety

- The API shall not expose raw tracebacks to clients.
- Errors shall use plain-language messages.
- API and authenticated responses shall set `Cache-Control: no-store`.
- Responses shall include the configured security headers, including CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`.
- Registration, login, analysis, discovery start, opportunity search, and job-map read shall be rate-limited by client IP.
- External calls shall retry only transient failures such as timeouts, 408, 425, 429, and 5xx responses.
- Permanent provider responses such as 400, 401, 403, and 404 shall not be retried.
- Job-source adapters shall return an empty result on provider failure rather than aborting the whole discovery run.
- Quota consumption shall be counted before JSearch requests and checked with `scripts/check_quota.py`.

## 6. Non-functional requirements

### NFR-1 — Reproducibility

- Scoring functions shall be pure where practical and independently testable.
- Weights shall have one authoritative definition in `app/services/scoring/ats.py`.
- User-visible numbers shall be rounded consistently before display.
- Demo results shall be reproducible from warmed fixtures and cache data.

### NFR-2 — Availability and degradation

- A failed optional job source shall not fail a run with other available sources.
- A missing cache in demo mode shall fail explicitly with remediation guidance.
- Provider quota limits and cache behavior shall be visible to operators through logs and scripts.

### NFR-3 — Testability and isolation

- The Python test suite shall run without API keys.
- Tests shall use isolated temporary JSON storage by default.
- MongoDB adapter tests shall use a non-network test double such as `mongomock`.
- CI shall install dependencies from lock/manifest files, build the frontend, run tests, type-check TypeScript, and smoke-check the production bundle.

### NFR-4 — Privacy

- Resume and account data shall be scoped to the owning user.
- Public job-map responses shall not expose user data.
- External links shall be sanitized before being sent to clients.
- Demo mode shall not be presented as isolated when `ENVIRONMENT=production`.

### NFR-5 — Maintainability

- Routers shall validate input, call services, and shape responses.
- Algorithms shall remain in service modules rather than routers or UI components.
- Pydantic models shall define API and internal data contracts.
- New job sources shall conform to the common source interface and preserve attribution.

## 7. Acceptance criteria

The implementation is acceptable when:

1. A fresh clone with no API keys can install dependencies and run the full Python test suite.
2. `npm --prefix frontend ci && npm --prefix frontend run build` succeeds.
3. A user can register, log in, upload a valid PDF/DOCX, and retrieve only their own analysis.
4. The `demo_before.pdf` and `demo_after.pdf` fixtures produce the documented India role-profile improvement direction.
5. Invalid file type, oversized file, missing role/location, OCR-required input, and unavailable role profile return actionable errors.
6. Repeated scoring of the same parsed inputs produces the same component and overall values.
7. Formatting reports nine checks and reports unavailable DOCX layout checks as skipped.
8. A discovery run returns a run ID, transitions through its lifecycle, and remains scoped to the owner.
9. A failed source does not erase successful results from other approved sources.
10. Opportunity search is authenticated, bounded, rate-limited, and does not scrape prohibited job boards.
11. Job-map reads do not make provider calls and return `503` when the map store is unavailable.
12. `DEMO_MODE=true` makes no external model/provider calls and fails clearly for uncached operations.
13. Account deletion returns a success message and deletion counts.
14. CI passes the build, Python tests, TypeScript check, and frontend smoke check.

## 8. Known decisions and constraints

- Python 3.11+ is authoritative; older `CLAUDE.md` references to Python 3.12 are documentation drift.
- Nine format checks are authoritative; the removed header/footer check is not a current requirement.
- The current implementation has more routers, account functionality, job adapters, and map functionality than the original minimal layout in `CLAUDE.md` describes. Those later additions are now current requirements.
- Adzuna descriptions may be truncated by provider plan, so per-posting skill scores are preliminary and must carry confidence metadata.
- Lever and Ashby sources are opt-in and require curated, verified board tokens.
- JSearch requires both a RapidAPI key and a subscribed JSearch plan; missing/unsubscribed access is handled as source degradation.

## 9. Change control

Any request to add an out-of-scope capability, change scoring weights, add a prohibited scraping source, or weaken user/data isolation requires an explicit product decision and corresponding updates to this document, tests, and the user-facing documentation.

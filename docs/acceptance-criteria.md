# CareerStack AI — Acceptance and Verification Matrix

**Status:** Current implementation baseline  
**Last reviewed:** 2026-09-25

This file translates the requirements in `docs/requirements.md` into executable verification work. The test paths below are the current verification anchors; add tests with a requirement when behavior changes.

## 1. Core scoring

| Requirement | Verification | Expected result |
|---|---|---|
| Deterministic overall score | `tests/test_ats.py` | `WEIGHTS` combines four components; output is bounded and stable |
| Frequency-weighted keyword coverage | `tests/test_keywords.py` | Frequency affects coverage; exact, boundary, and fuzzy matching work |
| Per-requirement semantic fit | `tests/test_semantic.py` | Requirements use best-line matching and calibrated similarity |
| Nine format checks | `tests/test_formatting.py` | Checks report earned/possible points, issues, and skipped checks |
| Experience date arithmetic | `tests/test_experience.py` | Overlapping intervals are merged and education is combined deterministically |
| No LLM score arithmetic | `tests/test_ats.py`, `tests/test_analyze_degraded.py` | Missing LLM/provider access follows a defined degraded/error path rather than inventing a score |

## 2. Extraction and analysis API

| Requirement | Verification | Expected result |
|---|---|---|
| PDF/DOCX support | `tests/test_analyze*.py`, fixtures under `tests/fixtures/` | Valid files reach structured analysis |
| 5 MiB limit | API tests for `/api/analyze` | Oversized upload returns an actionable `400` |
| Type validation | API tests for `/api/analyze` | Unsupported extensions, including `.doc`, return `400` |
| Role/location validation | API tests for `/api/analyze` | Blank values return `400` |
| OCR boundary | `tests/test_analyze_degraded.py` | Scanned input returns a clear OCR-needed response; no OCR is added |
| User ownership | `tests/test_analyze*.py` | List/detail endpoints return only the caller’s analyses |

## 3. Authentication and accounts

| Requirement | Verification | Expected result |
|---|---|---|
| Registration and login | `tests/test_auth.py` | Valid credentials return a bearer token and public user |
| Generic login failure | `tests/test_auth.py` | Unknown email and wrong password share the same response |
| Password limits | `tests/test_auth.py` | Short and over-72-byte passwords are rejected without hashing errors |
| Password secrecy | `tests/test_auth.py` | No response exposes a password hash |
| Account deletion | `tests/test_account_deletion.py` | Explicit confirmation deletes owned records and returns counts |
| JWT configuration | `tests/conftest.py`, application startup tests | Missing/blank secret prevents startup |

## 4. Discovery and opportunities

| Requirement | Verification | Expected result |
|---|---|---|
| Discovery ownership | `tests/test_discovery.py` | User cannot start from another user’s analysis or read another run |
| Background run lifecycle | `tests/test_discovery.py` | Start returns a run ID; polling exposes pending/running/completed states |
| Provider isolation | `tests/test_discovery.py`, `tests/test_job_sources.py` | A failed source does not remove successful source results |
| Deduplication and attribution | `tests/test_job_sources.py` | Canonical identity and source priority are stable; original URLs remain |
| Retry policy | `tests/test_job_sources.py` | Transient failures retry; permanent 400/401/403/404 responses do not |
| Quota protection | `tests/test_job_sources.py` | Budget is checked before calls and can disable a source safely |
| Resume-free search | `tests/test_discovery.py` / opportunity tests | Search is authenticated, bounded, deduplicated, and provider-approved |
| Source confidence | `tests/test_job_sources.py` | Truncated, low-confidence, and skills-unscored metadata is preserved |

## 5. Job map and persistence

| Requirement | Verification | Expected result |
|---|---|---|
| JSON backend | `tests/conftest.py`, storage tests | Tests use isolated temporary JSON data |
| MongoDB facade | `tests/test_store_mongodb.py` | Store operations work against the test double without Atlas |
| Migration idempotence | migration tests/scripts | Import is repeatable and does not delete source JSON |
| Provider-free map reads | `tests/test_job_map.py` | Public map endpoints do not invoke providers |
| Map validation | `tests/test_job_map.py` | Coordinates, radius, source, and result limits are validated |
| Canonical identity/geocoding | `tests/test_job_map.py` | Same title in different locations remains distinct; unknown coordinates are not guessed |
| Map unavailable response | `tests/test_job_map.py` | Storage failure returns a clear `503` |

## 6. Frontend and release quality

| Requirement | Verification | Expected result |
|---|---|---|
| Route coverage | `frontend/src/App.tsx` and page tests | Landing, auth, upload, dashboard, jobs, map, account, and legal routes exist |
| API integration | `frontend/src/lib/api.ts` and page tests | UI consumes backend contracts rather than duplicating algorithms |
| Type safety | `npm --prefix frontend exec tsc -- --noEmit` | TypeScript check passes |
| Production bundle | `npm --prefix frontend run build` | `frontend/dist/index.html` and JavaScript assets are produced |
| Browser/API smoke | CI workflow and frontend tests | Root shell serves and API routes remain distinct from SPA fallback |
| Security headers | API tests / HTTP smoke checks | CSP and hardening headers are present; API responses are `no-store` |
| Test isolation | `tests/conftest.py` | Tests cannot write to real demo/cache data |

## 7. Manual release checks

These checks are required when preparing a deployment, even if automated coverage exists:

- [ ] Generate and store a random `JWT_SECRET` outside source control.
- [ ] Set `ENVIRONMENT=production`.
- [ ] Set `DEMO_MODE=false`.
- [ ] Select `STORAGE_BACKEND` intentionally and configure MongoDB if selected.
- [ ] Verify Groq and Adzuna credentials.
- [ ] Verify JSearch subscription, not only the presence of a RapidAPI key.
- [ ] Verify Lever/Ashby board tokens before enabling those adapters.
- [ ] Run `python scripts/check_quota.py`.
- [ ] Run `python scripts/verify_greenhouse.py`.
- [ ] Run `python scripts/ingest_job_map.py --dry-run`, then refresh the snapshot.
- [ ] Build the frontend before starting the product server.
- [ ] Confirm demo fixtures and offline preparation are not mixed with production user data.
- [ ] Verify privacy and terms content before public launch.

## 8. Change protocol

When a requirement changes:

1. Update `docs/requirements.md`.
2. Update the relevant API or architecture document if the contract/boundary changes.
3. Add or update the verification row in this file.
4. Run the smallest relevant tests first, then the full CI gate.
5. Do not update the score formula or source-policy boundary without an explicit product decision.

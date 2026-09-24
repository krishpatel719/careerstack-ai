# CareerStack AI - Resume Analysis Module

## What this is

An ATS resume analysis engine. A user uploads a resume (PDF/DOCX) and types a
target job role. The system scores the resume against what that role actually
demands in the live job market, and returns a prioritised list of fixes.

Academic project (Software Group Project, 7th sem CSE). Demo deadline: 22 Aug.
Scope is deliberately narrow - see "Out of scope" below and do not exceed it.

## The one rule that matters

**The LLM never produces the score.**

- LLM does: extract structured data from resume text, extract skills from job
  descriptions, write human-readable explanations of already-computed numbers.
- Deterministic Python does: all scoring, all arithmetic, all weighting.

Reason: the score must be reproducible across runs and explainable in a viva.
If you ever find yourself prompting a model for a number, stop and write a
function instead.

## Scoring formula

```
ATS_SCORE = 0.40 * keyword_coverage
          + 0.25 * semantic_fit
          + 0.20 * format_compliance
          + 0.15 * experience_alignment
```

Each term in [0, 1], multiplied by 100 at the end. Weights live in one constant
named WEIGHTS in app/services/scoring/ats.py. Never hardcode them elsewhere.

### keyword_coverage
Frequency-weighted, not binary. The requirement set is mined from ~40 real job
postings for the target role, so each skill carries its market frequency as its
weight:

```
score = sum(frequency_i * matched_i) / sum(frequency_i)
```

Skills below 0.15 frequency are dropped as noise. Skill matching is three-tier:
exact match on normalised skill list, then word-boundary regex over full resume
text, then rapidfuzz ratio >= 90.

### semantic_fit
Per-requirement, NOT whole-document. For each requirement sentence in the role
profile, find the best-matching line anywhere in the resume, then average those
maxima. Whole-document cosine similarity destroys the signal - do not do it.

Calibrate raw MiniLM cosine from the 0.30-0.85 band onto 0-1.

### format_compliance
Ten deterministic checks with individual point values (email present, text
extractable, single column, no tables, no header/footer text, core sections
present, reasonable length, dates parseable, standard bullets, phone present).
Each failure returns its own penalty so the UI can show "fixing this recovers
N points".

### experience_alignment
0.7 * years_component + 0.3 * education_component. Years come from merged,
non-overlapping employment intervals computed in Python - never ask the LLM to
do date arithmetic.

## Tech stack

- Python 3.12, FastAPI, uvicorn
- Optional MongoDB Atlas through one long-lived PyMongo client; JSON is the
  zero-config local/demo/test store
- PyMuPDF (text + layout), pdfplumber (table detection), docx2txt
- sentence-transformers all-MiniLM-L6-v2, CPU only, local
- groq SDK (openai/gpt-oss-120b), temperature=0
- rapidfuzz, httpx, tenacity, pydantic v2
- Adzuna API for mining role profiles (country code "in" for India)
- React 19 + TypeScript + Vite, Tailwind CSS v4, shadcn/ui source components
- Framer Motion for restrained Aceternity-style product moments
- react-pdf/pdf.js for browser-side PDF resume previews

The frontend is a Vite app under `frontend/`. The backend serves its
production build from `frontend/dist`; build it before starting the product
server.

## Storage

JSON files under ./data/ are the zero-config local/demo store. Production
deployments may explicitly select MongoDB Atlas through configuration. One
process-wide PyMongo client is created lazily and closed by FastAPI lifespan;
startup pings Atlas and creates query/TTL indexes. `app/store.py` is the
compatibility repository: its keyed record API works against either backend.
Legacy JSON can be imported with `scripts/migrate_json_to_mongodb.py`; the
importer is idempotent and never deletes source files.

Cache role profiles keyed on sha1(role + location) for 7 days and cache every
Adzuna/job-source response for 6 hours. Mongo TTL indexes enforce those windows
alongside the existing application checks. The free Adzuna tier is ~1000 calls per
month, so never remove caching.

`DEMO_MODE` blocks external model/provider calls. Atlas may still be used as the
persistence service; use `STORAGE_BACKEND=json` only when fully offline.

## Layout

```
app/
  main.py                       FastAPI app, routes only, zero logic
  config.py                     pydantic-settings from .env
  database.py                   MongoDB client lifecycle and indexes
  store.py                      MongoDB/JSON repository facade
  models/                       Pydantic schemas
  services/
    extraction/                 text_extract.py, layout.py, llm_parse.py
    scoring/                    ats.py, keywords.py, semantic.py,
                                formatting.py, experience.py
    roleprofile/                miner.py, adzuna.py, cache.py
  data/skill_aliases.json
tests/
  fixtures/                     sample resumes (real PDFs)
frontend/                       React + TypeScript + Vite product frontend
frontend/dist/                  local production build served by FastAPI (ignored)
data/                           JSON fallback/migration source, gitignored
```

Routers validate input, call a service, return a response. Every algorithm
lives in services/. This is non-negotiable - it is what makes the code testable.

## Conventions

- Type hints on every function signature
- Pure functions in services/ wherever possible; pass data in, return data out
- No global mutable state except the lru_cached embedding model and the
  process-wide MongoDB client owned by app/database.py
- Every external call wrapped in tenacity retry, and every job-source failure
  returns [] rather than raising - one dead source must not kill a run. Retry
  only transient HTTP failures (timeouts, 408/425/429, 5xx); never retry
  permanent 400/401/403/404 responses.
- Job discovery uses provider APIs or documented public JSON endpoints only.
  Do not add an HTML scraper that bypasses access controls, rate limits,
  CAPTCHAs, or provider terms. Preserve provider attribution and the original
  posting URL, and cache aggressively.
- Round every number that reaches the user
- Errors surface as plain-language messages, never raw exceptions

## Commands

```
uvicorn app.main:app --reload      run API server on :8000
npm --prefix frontend run dev      run Vite frontend on :5173
npm --prefix frontend run build    build the React production shell
pytest -q                          run tests
pytest tests/test_scoring.py -v    scoring tests only
```

## Build order

Do these strictly in sequence. Do not start a step before the previous one runs
correctly on real input.

1. text_extract.py - prove it on 5 real resume PDFs, print to terminal
2. llm_parse.py - structured extraction, validated against ParsedResume
3. adzuna.py + miner.py - mine a role profile, print the frequency table
4. formatting.py - pure Python, no network, cannot fail in a demo. Build first
   among the scoring components.
5. keywords.py - frequency-weighted coverage
6. semantic.py - per-requirement embeddings
7. experience.py
8. ats.py - combine
9. FastAPI routes
10. React product frontend under frontend/

## Testing

Write tests for scoring components as they are built, not afterwards. Scoring
functions are pure, so they are cheap to test and the tests catch silent
regressions in the numbers.

## Out of scope - do not build

Bullet rewriting, application tracker, OCR, LangGraph orchestration,
Docker.

If a change would require any of these, say so and stop rather than adding it.

### Deliberately added after the original scope

Three items were moved out of "do not build" by explicit decision, after
the original demo date. They are in scope now:

- **Authentication** - JWT (pyjwt + bcrypt directly, not passlib).
  See app/services/auth.py, app/routers/auth.py, app/dependencies.py.
- **Job discovery** - see app/services/discovery.py and the section below.
- **MongoDB persistence** - Atlas is the production store; see app/database.py,
  app/store.py, and scripts/migrate_json_to_mongodb.py.

Nothing else on the list above has moved. Ask before adding to it.

## Job discovery

Composition over the existing pipeline, not a new one: it reuses the
Adzuna client, the skill vocabulary and extractor, and keywords.py.

### Job sources

Five adapters behind one interface (app/services/jobs/base.py). Each
never raises -- a dead source returns [] and the run continues on the
others. They fan out concurrently and are cached per source with a 6-hour
TTL, so one source being rate-limited doesn't invalidate the others. Lever
and Ashby are opt-in public ATS adapters with curated board-token files.

Dedupe priority when the same posting arrives from several sources:

```
jsearch > greenhouse > lever > ashby > adzuna
```

JSearch wins because it returns full descriptions rather than Adzuna's
~500-character snippet, and the per-posting keyword score is computed over
that text. Greenhouse, Lever, and Ashby are first-party company ATS sources
for their configured boards, so their links and descriptions are authoritative
for those employers. Within a source, the fullest description wins.

**Greenhouse tokens must be verified, not assumed.** The list originally
specified (razorpay, phonepe, zerodha, cred, meesho, postman, freshworks,
...) was 14/15 dead -- only `groww` resolved, and Razorpay exists only as
`razorpaysoftwareprivatelimited`. 48 further spelling variants were probed
and none resolved. The shipped list in app/data/greenhouse_companies.json
is 28 boards, every one confirmed HTTP 200, mostly global companies that
hire in India. Run `python scripts/verify_greenhouse.py` before a demo: a
renamed board 404s silently and just costs coverage.

**RAPIDAPI_KEY is optional.** Without it JSearch logs one warning at first
use and returns [] forever, making no HTTP call; Adzuna and Greenhouse
still run.

**A RapidAPI key is not enough on its own - you must also subscribe to
JSearch.** A key that isn't subscribed returns exactly the same 403 and
message ("You are not subscribed to this API") as a completely invalid
key, so the failure is easy to misread as a bad key. Verified by sending a
deliberately invalid key and getting a byte-identical response. Subscribe
at rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch ("Subscribe to Test",
free Basic plan, 200 req/month); the same key then works. As of the last
check this repo's key is present but **not subscribed**, so JSearch
contributes nothing and discovery runs on the other configured sources.

**Quota is tracked locally** (app/services/jobs/quota.py), because the
free plan exposes no usable remaining-quota header. Every call is counted
before it is made -- a timed-out call still consumed quota upstream -- and
the count is keyed by calendar month, so the reset needs no scheduled job.
At MONTHLY_CALL_BUDGET (180 of the tier's 200) the source skips itself,
holding 20 back so a demo can't be what discovers the quota ran out.
`python scripts/check_quota.py` prints consumption.

Permanent statuses (400/401/403/404) are **not** retried. Before that
guard, the unsubscribed-key 403 was retried three times, burning three
calls of a 200/month tier on a failure that could never succeed.

### Ranking

```
keyword_component = 0.5 * coverage_ratio * coverage_confidence
                  + 0.5 * min(matched_count / 4, 1.0)

match = 0.70 * keyword_component
      + 0.20 * recency
      + 0.10 * location_fit
```

`coverage_confidence` is the one thing here not in the original module
spec, and it exists because of a measured problem, not a hunch. Adzuna's
free tier truncates each description to ~500 characters. On a live
65-posting run, 65% of postings yielded at most one detectable skill, and
every posting that scored 100% keyword coverage did so off a single
detected skill - a Shopify job outranked a genuinely relevant AI role
because its snippet happened to name one skill the resume had.

So coverage is damped linearly below MIN_SKILLS_FOR_FULL_CONFIDENCE (3
skills). The weights above are unchanged; what changed is how much of the
keyword term a thin posting may claim. Two flags surface this in the UI
rather than hiding it:

- `meta.low_confidence` - named some skills, too few to be sure.
- `meta.skills_unscored` - named none we recognise, so the skills term
  could not be computed at all. Ranked on recency and location alone.

For Adzuna postings, the per-posting score is preliminary because it reports
what the provider's shortened snippet named, not what the full job needs.
JSearch and Greenhouse supply fuller descriptions and are not labelled as
truncated.

**Why the keyword term is half ratio and half absolute count.** Coverage
alone is a ratio, and a ratio rewards postings that name few requirements.
Measured on a live 317-posting Bangalore run once Greenhouse was added:
Greenhouse postings name 6.9 skills on average (5700-char descriptions)
against Adzuna's 2.1 (500-char snippets), and matched more of the resume's
skills in absolute terms (0.22 vs 0.07 per posting) -- yet averaged 12.1
against Adzuna's 22.8, because matching 1 of 13 named skills is 8% while
matching 1 of 1 is 100%. The better-documented source was being penalised
for being better documented. Blending in a saturating match count
(MATCH_COUNT_SATURATION = 4) fixes that without special-casing any source.

Verified after the change, with a resume that genuinely fits the market:
the top result is a Full Stack Developer matching 5 of 5 named skills, and
a Greenhouse posting matching 4 of 11 correctly outranks an Adzuna snippet
matching 2 of 2.

## Demo safety

Two sample resumes live in tests/fixtures/: one deliberately bad (two-column,
contact details in the header, thin skills) and one fixed version of the same
resume. The demo is: score the bad one (~43), walk through the detected issues,
score the fixed one (~70). Both must have cached analyses on disk before the
demo so nothing depends on a live network call.

**Use location "India" for the scoring demo.** Those target numbers only
hold against the India profile (measured: 45.4 -> 71.6, a +26.2 gap).
Ahmedabad is a genuinely sparser market - 32 postings, sparse_profile=True -
and the same two resumes score 37.9 -> 54.9 there, a +17 gap. Both are
correct; India is the one the numbers in this file describe, and it's what
prep_demo.py mines.

Job discovery demos fine from any of the three warmed cities. Rajkot is the
one that shows the location-widening banner (0 postings there, widens to
India). Ahmedabad does NOT widen - it returns 65 unique postings, well above
the threshold.

### Never run the test suite against demo data without tests/conftest.py

The suite writes real cache files, and before conftest.py existed it wrote
them into ./data/. One route test seeded a "backend developer"/"Ahmedabad"
profile containing a single skill ("python"); the demo resume has Python, so
keyword coverage scored 1/1 = 100% and demo_before.pdf came out at **81.7
instead of 45.4**. prep_demo.py and the running app silently disagreed, and
nothing failed to flag it.

tests/conftest.py now points store.DATA_DIR at a temp directory for the whole
session. If that fixture is ever removed or bypassed, re-check ./data/
role_profiles for entries with no sparse_profile key - that's the fingerprint
of a test-authored profile.

# CareerStack AI - Resume Analysis

An ATS resume analysis engine. Upload a resume (PDF or DOCX), name a target
role and city, and it scores the resume against what that role actually
demands in the live job market - then lists the fixes worth making, in
priority order, and finds matching jobs.

Academic project (Software Group Project, 7th sem CSE).

---

## The one thing worth knowing about the design

**The LLM never produces the score.**

An LLM extracts structured data from the resume text and writes plain-English
explanations of numbers that have already been computed. Every number - every
weight, every subscore, every percentage - comes from deterministic Python.

That is a deliberate constraint, not an oversight. It means the score is
reproducible across runs and every figure can be traced to a line of code, so
the system can be defended in a viva rather than hand-waved at.

```
ATS_SCORE = 0.40 * keyword_coverage      # frequency-weighted against ~40 real postings
          + 0.25 * semantic_fit          # per-requirement MiniLM similarity
          + 0.20 * format_compliance     # 9 deterministic parseability checks
          + 0.15 * experience_alignment  # merged employment intervals + education
```

---

## Requirements

- **Python 3.11 or newer.** The code uses `X | Y` union syntax (3.10+) and is
  developed and tested on 3.11. Nothing requires 3.12.
- **Node.js 20 or newer** for the React/Vite production frontend.
- About 2 GB of disk space - `sentence-transformers` pulls a PyTorch build,
  and the MiniLM model (~90 MB) downloads on first use.
- JSON storage works with zero setup under `./data/`; production deployments
  can opt into MongoDB Atlas with `STORAGE_BACKEND=mongodb`.

---

## CI quality gate

Pull requests and pushes to `main` run `.github/workflows/ci.yml` on Ubuntu.
The job has read-only repository permissions and performs this sequence:

1. install Python 3.11, Node.js 22, and the project dependencies;
2. install the frontend from `package-lock.json` with `npm ci` and build the
   React production bundle;
3. run the full `pytest` suite with `STORAGE_BACKEND=json` and a CI-only,
   non-production `JWT_SECRET` (no GitHub repository secrets are used);
4. run the TypeScript compiler without emitting files; and
5. smoke-check that the production build contains the HTML root mount point and
   a JavaScript asset.

Run the equivalent gate locally from the repository root (Bash):

```bash
export JWT_SECRET="local-ci-test-secret-not-for-production"
export STORAGE_BACKEND=json

python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m pytest -q
npm --prefix frontend exec tsc -- --noEmit

test -f frontend/dist/index.html
grep -q 'id="root"' frontend/dist/index.html
test -n "$(find frontend/dist/assets -type f -name '*.js' -print -quit)"
```

The workflow uses current major action versions (`checkout@v6`, `setup-python@v6`,
and `setup-node@v5`). Full commit-SHA pinning is recommended for a longer-lived
production workflow, but mutable major tags keep this readiness workflow
straightforward to review and update.

---

## Quick start

```bash
git clone https://github.com/krishpatel719/careerstack-ai.git
cd careerstack-ai

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
npm --prefix frontend install
cp .env.example .env           # copy .env.example .env   on Windows cmd
```

Now generate a JWT secret - **the app refuses to start if this is missing or
blank**, so token-signing can never silently fall back to an insecure value:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the output into `.env` as `JWT_SECRET=...`. The default `json` backend is
ready immediately. For a hosted multi-user deployment, create a MongoDB Atlas
database user, allow the server IP in Network Access, and opt in:

```dotenv
STORAGE_BACKEND=mongodb
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=careerstack
```

Keep the populated URI secret. To import records from an older JSON checkout,
preview and then run the idempotent migration:

```bash
python scripts/migrate_json_to_mongodb.py --dry-run
python scripts/migrate_json_to_mongodb.py
```

The importer never deletes JSON. The application creates its MongoDB indexes on
startup and fails fast if Atlas is unreachable, preventing writes from failing
later behind a healthy-looking process.

Then start the product:

```bash
npm --prefix frontend run build
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

> Both a missing `JWT_SECRET` and a blank value make the app refuse to start
> with a clear pydantic error. Set a long, random value.

---

## Do I need API keys?

**To run the test suite: no.** The full test suite passes on a fresh clone with no
API keys configured - provider calls are mocked or avoided by design.

```bash
pytest -q
```

**To analyse a real resume: yes, two.** Both have free tiers.

| Key | What it unlocks | Without it |
|---|---|---|
| `GROQ_API_KEY` | Resume parsing (the structured extraction step) | Analysis fails - this one is required |
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` | Role profiles and the main job source | No market data to score against |
| `RAPIDAPI_KEY` | The JSearch job source (optional) | Job discovery runs on the other two sources |

- **Groq** - free at [console.groq.com](https://console.groq.com). Generous limits.
- **Adzuna** - free at [developer.adzuna.com](https://developer.adzuna.com).
  **~1000 calls/month**, and this project caches aggressively because of it
  (role profiles for 7 days, job-source results for 6 hours).
- **RapidAPI / JSearch** - optional, see the caveat below.
- **Lever / Ashby** - optional official public ATS adapters. They are disabled
  until reviewed board tokens are added to `app/data/lever_companies.json` and
  `app/data/ashby_companies.json`.

### The JSearch subscription trap

A RapidAPI key alone is **not** enough. You must also subscribe to the JSearch
API specifically, at
[rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch)
→ *Subscribe to Test* → free Basic plan (200 requests/month).

An unsubscribed key returns `403 {"message": "You are not subscribed to this
API."}` - **byte-identical to the response for a completely invalid key**. It
reads like a bad key when it is not. Verified by sending a deliberately
invalid key and diffing the responses.

The app handles this gracefully: JSearch logs one warning, returns nothing,
and discovery carries on with Adzuna and Greenhouse. Check your consumption
with `python scripts/check_quota.py`.

### Job-fetching policy

The discovery pipeline does not scrape arbitrary job-board HTML or bypass
login, paywalls, rate limits, CAPTCHAs, or access controls. It uses provider
APIs and documented public ATS JSON endpoints only, with a descriptive
source label and a link back to the original posting. Greenhouse, Lever, and
Ashby adapters retry transient failures only; permanent
400/401/403/404 responses are not retried. Results are cached and
quota-limited where the provider requires it.

Keep that boundary when adding sources. Prefer an official API, RSS feed, or
public JSON endpoint with documented terms; do not copy or retain resumes,
personal data, or content beyond what the provider permits. User-Agent and
attribution requirements should be reviewed before production launch.

The optional Lever and Ashby adapters are intentionally token-curated. Add a
board only after checking its current provider terms and endpoint:

```json
{
  "companies": [
    {
      "name": "Example",
      "token": "example-board-token",
      "enabled": true
    }
  ]
}
```

The adapters use public JSON endpoints, return full descriptions, retry only
transient failures, and link back to the employer's original posting. They
are not enabled by default because board tokens change and should not be
guessed.

---

## Using it

1. **Register** an account (or log in) - analyses belong to the user who
   created them.
2. **Upload** a resume, name a target role and city.
3. **Read the dashboard** - two scores kept deliberately distinct:
   - *ATS Parse Score* - can an applicant tracking system read your document?
   - *Role Fit Score* - how well do you match this role's market demand?
4. **Work the action plan** - each fix shows the points it recovers.
5. **Find matching jobs** - live postings ranked against your resume.

### Try it with the included samples

`tests/fixtures/` holds a deliberately bad resume and a fixed version of the
same one:

| File | Role | Location | Expected |
|---|---|---|---|
| `demo_before.pdf` | backend developer | **India** | ~45 (Needs work) |
| `demo_after.pdf` | backend developer | **India** | ~72 (Competitive) |

Use **India**, not a city. Those figures hold against the India role profile.
Ahmedabad is a genuinely sparser market and gives ~38 → ~55 for the same two
files. Both are correct - India is the one these numbers describe.

---

## Offline demo mode

`DEMO_MODE=true` in `.env` makes the app serve **only** from cached data and
never call Groq, Adzuna, JSearch, or the public ATS providers. MongoDB Atlas is
still the persistence service in this mode. For a fully offline machine, set
`STORAGE_BACKEND=json`; caches then live under `./data/`.

```bash
# 1. With DEMO_MODE=false, warm every cache the demo needs:
python scripts/prep_demo.py

# 2. Set DEMO_MODE=true in .env, restart the server.
```

`prep_demo.py` caches resume parses, mines the role profile, runs both demo
analyses, and warms three job-discovery runs in the configured storage backend.
It creates a demo account:
`demo@careerstack.ai` / `demo12345`.

In demo mode, anything **not** cached fails with a message naming the fix
rather than silently going online. That strictness is the point.

---

## Project layout

```
app/
  main.py                    FastAPI app - routes only, zero logic
  config.py                  pydantic-settings, reads .env
  models/                    Pydantic schemas (resume, job, user)
  services/
    extraction/              PDF/DOCX text, layout signals, LLM parsing
    scoring/                 ats, keywords, semantic, formatting, experience
    roleprofile/             Adzuna client, profile mining, caching
    jobs/                    Job source adapters (Adzuna, JSearch, Greenhouse,
                              optional Lever and Ashby public ATS sources)
    discovery.py             Job discovery pipeline
    auth.py                  JWT + bcrypt
  data/                      Skill vocabulary and aliases (source, not cache)
  database.py                MongoDB client lifecycle and indexes
tests/
  fixtures/                  Real sample resumes
frontend/                    React + TypeScript + Vite product frontend
frontend/dist/               Local production build served by FastAPI (ignored)
data/                        JSON fallback and migration source (gitignored)
scripts/migrate_json_to_mongodb.py  Idempotent legacy-data importer
```

Routers validate input, call a service, return a response. Every algorithm
lives in `services/`. That separation is what makes the scoring testable.

The product frontend is a React 19 + TypeScript + Vite app under `frontend/`.
FastAPI serves its production build and keeps the API on the same origin, so
there is no CORS requirement in the normal product flow.

---

## Commands

```bash
uvicorn app.main:app --reload       # product server on :8000
npm --prefix frontend run dev       # Vite dev server on :5173
npm --prefix frontend run build     # production frontend build
pytest -q                           # full suite (no API keys needed)
pytest tests/test_discovery.py -v   # one module

python scripts/prep_demo.py         # warm every cache for an offline demo
python scripts/migrate_json_to_mongodb.py --dry-run  # preview legacy import
python scripts/check_quota.py       # JSearch calls used this month
python scripts/verify_greenhouse.py # check the job boards still resolve
```

---

## Notes for anyone extending this

**Run the tests before trusting cached data.** `tests/conftest.py` selects the
isolated JSON fallback and points it at a temp directory for the whole session;
MongoDB adapter tests use `mongomock` and never contact Atlas. Without this
isolation the suite once wrote a one-skill test profile into real cache data and
silently inflated a demo score. Do not remove the fixture.

**Job-source coverage varies sharply by city.** The Greenhouse boards skew
towards Bangalore and Mumbai; for tier-2 cities Adzuna carries nearly
everything. `scripts/verify_greenhouse.py` reports per-board India counts.

**Per-posting match scores are preliminary, and the UI says so.** Adzuna
truncates descriptions to ~500 characters, so a posting's keyword coverage is
computed over whatever skills fall inside that snippet. Postings that name too
few skills are flagged `LOW CONFIDENCE`, and those naming none are flagged
`NOT SCORED ON SKILLS` rather than shown as a misleading 0%.

`CLAUDE.md` documents the measurements behind each non-obvious scoring
decision, including several where the obvious approach was tried first and
found wrong on real data.

---

## Tech stack

Python 3.11 · FastAPI · uvicorn · Pydantic v2 · PyMongo · MongoDB Atlas ·
PyMuPDF · pdfplumber · docx2txt · sentence-transformers
(all-MiniLM-L6-v2, CPU) · Groq · rapidfuzz · httpx · tenacity · pyjwt ·
bcrypt · React 19 · TypeScript · Vite · Tailwind CSS v4

Deliberately not used: LangChain, Docker, Firebase. JSON is the default
local/demo store; MongoDB Atlas is an optional production backend selected by
environment configuration.

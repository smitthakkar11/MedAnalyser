# MedAnalyser

**AI-assisted health assessment and doctor discovery — an educational / portfolio project.**

MedAnalyser lets an adult user describe symptoms, upload medical reports, answer
AI-generated follow-up questions, and receive an evidence-grounded summary with
possible explanations, treatment and medication *information*, and a suggested
medical specialty for further evaluation.

> ⚠️ **Not medical advice.** MedAnalyser does not diagnose conditions and does not
> prescribe medication. It is not a substitute for a licensed healthcare
> professional. Do not use it in an emergency — contact your local emergency
> services. Do not upload real patient records.

---

## Status

| Phase | Scope | State |
| --- | --- | --- |
| **1** | Foundation: repo, FastAPI, PostgreSQL + pgvector, SQLAlchemy, Alembic, React/Vite/Tailwind, Docker, health checks | ✅ Complete |
| **2** | Authentication: email/password (Argon2id), Google OAuth, JWT sessions, account linking, age 18+ verification, onboarding, protected routes | ✅ Complete |
| **3** | User profile (allergies, conditions, medications, emergency contact) and dashboard | ✅ Complete |
| **4** | ML foundation: dataset, preprocessing, model comparison, evaluation, inference service | ✅ Complete |
| **5** | Symptom processing & assessment engine: NLP extraction, follow-up state machine, prediction, persistence | ✅ Complete |
| 6 | Medical report/PDF + OCR processing | Not started |
| 7 | Combine report/lab features with the ML assessment | Not started |
| 8 | Safety / red-flag engine | Not started |
| 9 | Doctor-specialty recommendation | Not started |
| 10 | Treatment / medication knowledge base | Not started |
| 11 | Nearby doctor discovery | Not started |
| 12 | Medical timeline + trends | Not started |
| 13 | Testing, security, Docker & deployment | Not started |

---

## Tech stack

**Frontend** — React 19, Vite 7, TypeScript (strict), Tailwind CSS v4, React Router 7, Axios, Recharts, light/dark theming
**Backend** — Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic
**Database** — PostgreSQL 16 with pgvector
**ML** — scikit-learn, XGBoost, NumPy, pandas, joblib. Models are trained locally from a public dataset; **no external or paid AI API is used**
**Infrastructure** — Docker, docker compose

---

## Architecture

```
                    React Frontend
                          │
                    REST / HTTPS
                          │
                    FastAPI Backend
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
 Authentication      Assessment       Doctor Discovery
        │                 │
        ▼                 ▼
 PostgreSQL         ML Service Layer
        │                 │
        │        ┌────────┼──────────┐
        │        ▼        ▼          ▼
        │   Condition   Safety    Specialty
        │    model      rules      mapping
        │        │        │          │
        │        └────────┼──────────┘
        │                 │
        └───────────── PostgreSQL
```

Layering is enforced by convention: **routes** validate and serialise,
**services** hold business logic, **repositories** own queries. Route handlers
never contain business logic, and services never touch the ORM session directly.

See [`docs/architecture.md`](docs/architecture.md) for detail.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (developed on 22)
- **PostgreSQL 16+ with the `pgvector` extension** — via Docker (easiest) or Homebrew
  (use `postgresql@17` on Homebrew; see below)
- **Docker Desktop** — optional, but the simplest way to get PostgreSQL + pgvector

---

## Quick start

```bash
git clone <this-repo> medanalyser && cd medanalyser
cp .env.example .env          # then edit as needed
```

### 1. Start PostgreSQL + pgvector

With Docker:

```bash
docker compose up -d db
```

Or with Homebrew (no Docker):

```bash
brew install postgresql@17 pgvector
brew services start postgresql@17
createuser -s medanalyser
createdb -O medanalyser medanalyser
psql -d postgres -c "ALTER ROLE medanalyser WITH PASSWORD 'medanalyser';"
```

Use **postgresql@17**, not 16: Homebrew's `pgvector` bottle only ships extension
files for Postgres 17 and 18, so `CREATE EXTENSION vector` fails on 16. If
`psql` is not on your `PATH`, add it:

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

The `vector` extension itself is created by the first Alembic migration — you do
not need to `CREATE EXTENSION` by hand.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

API: <http://localhost:8000> · Interactive docs: <http://localhost:8000/docs>

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>

The Vite dev server proxies `/api` to `http://localhost:8000`, so the browser
stays same-origin. Override the target with `VITE_API_PROXY_TARGET`.

---

## Running the whole stack in Docker

```bash
cp .env.example .env
docker compose --profile full up -d --build
```

- Frontend → <http://localhost:8080>
- Backend → <http://localhost:8000>
- PostgreSQL → `localhost:5432`

The backend container runs `alembic upgrade head` before starting uvicorn, so a
fresh database is migrated automatically.

### Trained model artifacts

There is no inference server to run. `docker-compose.yml` mounts
`./ml/artifacts` read-only into the backend container, so train once on the host
and the container picks the artifacts up:

```bash
python -m ml.training.train_condition_model
docker compose up -d --build
```


---

## Health checks

| Endpoint | Purpose | Behaviour |
| --- | --- | --- |
| `GET /api/health` | Liveness | Always `200` while the process is up. Touches no dependency, so a database outage cannot cause an orchestrator to kill healthy pods. |
| `GET /api/health/ready` | Readiness | Checks PostgreSQL connectivity **and** that the `vector` extension is installed. `200 ok`, `200 degraded` (reachable but extension missing), or `503 unavailable`. |

```bash
curl http://localhost:8000/api/health
curl -i http://localhost:8000/api/health/ready
```

The landing page renders this live under **System status**, which makes the
whole browser → proxy → API → database chain visible at a glance.

---

## Authentication

| Method | Status |
| --- | --- |
| Email + password | Working (Argon2id hashing) |
| Google Sign-In | Implemented; needs a `GOOGLE_CLIENT_ID` to enable |

Sessions use a short-lived access token held **in memory** plus a long-lived
refresh token in an **httpOnly cookie**, so no credential is reachable from
browser script. Signing out revokes every outstanding refresh token server-side.

Every new account goes through a six-step onboarding wizard. The first step,
date of birth, is **required**: it is checked against an **18+** requirement
using the server's clock, and under-18 users are shown an age-restriction screen
with nothing stored. Every step after it — sex/gender, allergies, conditions,
medications, emergency contact — is **optional and skippable**, either one
question at a time or all at once, and can be filled in later from the profile
page.

### Enabling Google Sign-In

1. Create an OAuth 2.0 Client ID (type: *Web application*) in the
   [Google Cloud console](https://console.cloud.google.com/apis/credentials).
2. Add `http://localhost:5173` as an authorised JavaScript origin.
3. Set the credentials:

   ```bash
   # backend/.env or the repo-root .env  — the SECRET stays server-side
   GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=<your-client-secret>

   # frontend/.env — the client id is public by design
   VITE_GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   ```

Without a client id the Google button renders disabled and the API returns
`503` — the feature reports itself as unconfigured rather than failing obscurely.

> **Note.** The Google flow is covered by tests using a stub verifier, and has
> not been exercised against real Google credentials — see *Known limitations*.

### API

```
POST /api/auth/signup       POST /api/auth/google        GET  /api/auth/me
POST /api/auth/login        POST /api/auth/link-google   POST /api/auth/onboarding
POST /api/auth/logout       POST /api/auth/refresh
```

---

## Medical profile

The profile holds a user's standing clinical context, which every future
assessment reads alongside the symptoms they describe:

- Sex at birth (optional) — it changes laboratory reference ranges — and gender
  identity, recorded separately and never used for that
- Allergies, with reaction and severity
- Existing conditions, with status and year of diagnosis
- Current and past medications, recorded verbatim
- Emergency contact and free-text notes

```
GET /api/profile      PUT /api/profile      GET /api/dashboard
```

`PUT` replaces the whole document atomically, collections included. Every query
is scoped to the signed-in user's id in the repository layer, so no request can
reach another user's records.

---

## Machine learning

MedAnalyser's condition prediction is a **random forest trained locally** on a
public dataset. There is no LLM and no external AI API anywhere in the pipeline.

```bash
pip install -e "backend[ml]"
python -m ml.ingest                            # download the dataset (~30 KB)
python -m ml.eda                               # writes ml/reports/eda.md
python -m ml.training.train_condition_model    # trains, evaluates, saves artifacts
```

The API loads the saved artifacts once at startup and never trains. Without them
everything else still works and `/api/health/ready` reports the model as
`degraded`.

| | |
| --- | --- |
| Dataset | Disease Symptom Description Dataset (CC BY-SA 4.0) |
| Classes | 41 conditions |
| Features | 131 binary symptoms |
| Selected model | Random forest, chosen on cross-validated macro F1 with ties broken on robustness |

**The headline accuracy is not the interesting number.** The dataset is
synthetic and 93.8% duplicate rows; a naive split leaks and scores 1.000. After
deduplication the honest measure is how the model behaves on partial input —
~0.79 with three symptoms, ~0.39 with one.

Full dataset card, leakage analysis, model comparison and limitations:
[`ml/README.md`](ml/README.md) · [`ml/reports/`](ml/reports/)

> The model outputs **possible conditions requiring professional evaluation**,
> never a diagnosis. Scores are relative model outputs, not calibrated
> probabilities.

---

## Symptom assessment

```
"stomach ache and been throwing up since yesterday"
        ↓  rule-based NLP (synonyms, negation, duration, severity)
   abdominal_pain, vomiting · 1 day
        ↓  follow-up state machine — asks only what is still missing
        ↓  trained random forest
   ranked possible conditions, with the symptoms behind each
```

| Endpoint | |
| --- | --- |
| `POST /api/assessments` | free text in, first question out |
| `POST /api/assessments/{id}/messages` | answer, get the next question |
| `POST /api/assessments/{id}/analyze` | run the model, finalise |
| `GET /api/assessments` · `GET /api/assessments/{id}` · `DELETE` | history |

Symptom synonyms live in
[`symptom_synonyms.json`](backend/app/services/ml/feature_extraction/data/symptom_synonyms.json)
and follow-up rules in
[`question_rules.json`](backend/app/services/ml/followup/data/question_rules.json) —
both are data files, so extending either is a data change rather than a code
change. Neither uses an LLM.

Results are presented as **possible conditions to discuss with a clinician**.
Scores are banded qualitatively rather than shown as percentages, because they
are uncalibrated relative outputs and a number reads as a clinical probability.

---

## Theming

The UI ships light and dark themes. The toggle in the header switches between
them; with no explicit choice the app follows the operating system and keeps
following it live. An explicit choice is stored in `localStorage` and always
wins over the OS setting.

The stored theme is applied by an inline script in `index.html` **before first
paint**, so reloading never flashes the wrong colour scheme.

---

## Testing and checks

The backend integration tests need PostgreSQL running; they create and manage
their own `medanalyser_test` database and skip with an explanation if it is
unreachable.

```bash
# Backend (from backend/, venv active)
pytest                     # test suite (264 tests)
ruff check . && ruff format --check .
mypy                       # strict type checking

# Frontend (from frontend/)
npm run build              # type-check + production build
npm run lint
```

---

## Database migrations

```bash
cd backend
alembic upgrade head                       # apply
alembic downgrade -1                       # roll back one
alembic revision --autogenerate -m "..."   # generate from models
alembic current                            # show current revision
```

The database URL comes from application settings, **not** from `alembic.ini`, so
no credentials are committed. Always review autogenerated migrations before
committing them.

---

## Configuration

All configuration is environment-driven. Copy `.env.example` to `.env`; every
variable is documented there. Nothing in the codebase reads `os.environ`
directly — everything goes through the typed `Settings` object in
[`backend/app/core/config.py`](backend/app/core/config.py).

Only `VITE_`-prefixed variables reach browser code, and **no secret may ever be
placed in one** — the Vite bundle is public. The Google client secret and the
maps API key are backend-only.

---

## Project structure

```
medanalyser/
├── backend/
│   ├── app/
│   │   ├── api/            # routers + dependencies (thin)
│   │   ├── core/           # config, logging, errors, middleware
│   │   ├── db/             # engine, session, declarative base
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic API contract
│   │   ├── repositories/   # data access; owns all queries
│   │   ├── services/       # business logic
│   │   └── main.py         # application factory
│   ├── alembic/            # migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/ hooks/ layouts/ pages/ services/ types/
│       └── App.tsx
├── infra/docker/           # Dockerfiles + nginx config
├── docs/
├── docker-compose.yml
└── .env.example
```

Alembic lives under `backend/` rather than `infra/migrations/` because
`env.py` imports the application's models and settings; keeping them together
avoids fragile cross-directory path handling.

---

## Security notes

- Passwords are hashed with Argon2id and never stored or logged in plaintext.
- Validation errors are stripped of the submitted value, so a rejected password
  is never echoed back in a response or a log.
- Access tokens live in memory; refresh tokens are httpOnly cookies.
- `JWT_SECRET` must be a 32+ byte non-default value in production, enforced at startup.
- Google ID tokens are verified server-side against Google's JWKS.
- Every user-owned resource is ownership-checked server-side; the frontend is
  never trusted to enforce access.
- Logs contain request metadata only — never bodies, credentials, tokens, or
  extracted report contents.
- API docs are disabled when `ENVIRONMENT=production`.
- Security headers (`nosniff`, `DENY`, `no-referrer`, restrictive CSP) are
  applied to every response.
- Secrets live in `.env`, which is gitignored. Never commit real credentials.

---

## License

Educational / portfolio use.

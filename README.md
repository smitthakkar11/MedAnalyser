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
| 2 | Authentication (email/password, Google OAuth, JWT, age 18+ verification, onboarding) | Not started |
| 3 | User profile & dashboard | Not started |
| 4 | Symptom assessment & conversational AI follow-up | Not started |
| 5 | Medical report upload (PyMuPDF, OCR, structured extraction) | Not started |
| 6 | RAG: knowledge ingestion, embeddings, pgvector retrieval | Not started |
| 7 | Local AI: `LLMService` / `OllamaLLM` | Not started |
| 8 | Safety red-flag engine, treatment & medication information, specialty recommendation | Not started |
| 9 | Doctor discovery | Not started |
| 10 | Assessment history & medical timeline | Not started |
| 11 | Testing & security hardening | Not started |
| 12 | Production readiness | Not started |

---

## Tech stack

**Frontend** — React 19, Vite 7, TypeScript (strict), Tailwind CSS v4, React Router 7, Axios, Recharts, light/dark theming
**Backend** — Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic
**Database** — PostgreSQL 16 with pgvector
**AI** — provider-abstracted (`LLMService`); default implementation targets Ollama running locally
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
 PostgreSQL         AI Service Layer
        │                 │
        │        ┌────────┼─────────┐
        │        ▼        ▼         ▼
        │      LLM      RAG      Safety
        │        │        │         │
        │        └────────┼─────────┘
        │                 │
        └───────────── PostgreSQL
                       + pgvector
```

Layering is enforced by convention: **routes** validate and serialise,
**services** hold business logic, **repositories** own queries. Route handlers
never contain business logic, and services never touch the ORM session directly.

See [`docs/architecture.md`](docs/architecture.md) for detail.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (developed on 22)
- **PostgreSQL 16 with the `pgvector` extension** — via Docker (easiest) or Homebrew
- **Docker Desktop** — optional, but the simplest way to get PostgreSQL + pgvector
- **Ollama** — not needed until Phase 7

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
brew install postgresql@16 pgvector
brew services start postgresql@16
createuser -s medanalyser
createdb -O medanalyser medanalyser
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

### Reaching Ollama from the Docker backend

Ollama should run **natively on the Mac**, not in a container: local inference on
Apple Silicon needs the Metal GPU, which Linux containers cannot access. The
containerised backend reaches it through `host.docker.internal`:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

This is already the compose default. Ollama must be listening on all interfaces
rather than loopback only:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve
```

On Linux hosts the same works via the `host-gateway` entry already declared in
`docker-compose.yml`.

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

## Theming

The UI ships light and dark themes. The toggle in the header switches between
them; with no explicit choice the app follows the operating system and keeps
following it live. An explicit choice is stored in `localStorage` and always
wins over the OS setting.

The stored theme is applied by an inline script in `index.html` **before first
paint**, so reloading never flashes the wrong colour scheme.

---

## Testing and checks

```bash
# Backend (from backend/, venv active)
pytest                     # test suite
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

- Passwords are never stored in plaintext (Phase 2 uses Argon2/bcrypt).
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

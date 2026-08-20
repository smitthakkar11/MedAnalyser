# MedAnalyser — Architecture

This document records the structural decisions taken in Phase 1 and the
extension points later phases plug into. It is updated as each phase lands.

---

## 1. Layering

```
HTTP request
   │
   ▼
app/api/routes/*        Validate input, call a service, serialise the result.
   │                    No business logic. No queries.
   ▼
app/services/*          Business logic and orchestration. Depends on
   │                    repositories and other services — never on a raw session.
   ▼
app/repositories/*      All query construction. The single place where
   │                    ownership filters are applied.
   ▼
PostgreSQL
```

The rule that matters most for this product: **ownership filtering lives in the
repository layer**. Every query for a user-owned medical resource takes a
`user_id` and filters by it, so no route can accidentally return another user's
data by forgetting a check.

## 2. Configuration

A single typed `Settings` object (`app/core/config.py`), built by
`pydantic-settings` from the environment and `.env`, validated once at startup
and cached with `lru_cache`.

Nothing else in the codebase reads `os.environ`. Consequences:

- Invalid configuration fails fast and loudly at startup, not on first use.
- Tests construct `Settings(...)` directly and pass it to `create_app()`.
- Handlers resolve settings from `request.app.state.settings`
  (`app/api/deps.py::get_app_settings`), so an app built with test settings is
  actually *served* with them.

## 3. Database

- **PostgreSQL is the source of truth.** Relational modelling by default; JSONB
  only where the shape is genuinely open-ended (e.g. an LLM's structured
  extraction output, whose keys vary by report type).
- **Async throughout** — SQLAlchemy 2 with `asyncpg`. The application is
  I/O-bound on the database, file parsing and LLM calls, so async avoids a
  thread per in-flight LLM request.
- **UUID primary keys** (`app/models/mixins.py`). Medical resources appear in
  URLs; sequential integers would leak record counts and invite enumeration.
- **Deterministic constraint names** via a metadata naming convention
  (`app/db/base.py`), so Alembic diffs stay stable and constraints can be
  dropped by name.
- **Sessions are request-scoped** and never shared. Commit is the caller's
  responsibility, so one request can span several repository calls inside a
  single transaction.

### pgvector

The `vector` extension is created by migration `0001_enable_extensions`, before
any table exists. Readiness checks that it is actually installed and reports
`degraded` if it is not, which catches "connected to the wrong database" early.

Verified locally against PostgreSQL 17.11 with pgvector 0.8.6: the migration
applies, downgrades and re-applies cleanly, and readiness returns `ok`,
`degraded` (extension dropped) and `unavailable` (server down) as expected.

The docker compose stack pins `pgvector/pg16`, which bundles the extension. On
Homebrew, install `postgresql@17` — the `pgvector` bottle only ships extension
files for Postgres 17 and 18.

## 4. Provider abstractions

Four pieces of the system are expected to be swapped, so each gets an interface
and the application depends only on that interface:

| Concern | Interface | First implementation | Later |
| --- | --- | --- | --- |
| LLM inference | `LLMService` | `OllamaLLM` | OpenAI, Anthropic, Gemini, vLLM |
| Embeddings | `EmbeddingService` | local model via Ollama | any embedding API |
| File storage | `StorageService` | `LocalStorageProvider` | `S3StorageProvider` |
| Doctor discovery | `DoctorDiscoveryService` | mock provider | a maps/places API |

No module outside an implementation may import a provider SDK or call Ollama
directly. Provider selection is by environment variable
(`LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `STORAGE_PROVIDER`, `DOCTOR_PROVIDER`).

These are declared in Phase 1 as the intended shape; the interfaces themselves
land with the phases that need them (6, 7, 9) rather than being stubbed now.

## 5. Health and readiness

Two distinct probes, because they answer different questions:

- `GET /api/health` — *is this process alive?* Touches nothing. A database
  outage must not make an orchestrator restart healthy API processes.
- `GET /api/health/ready` — *can this process serve traffic?* Checks each
  dependency and aggregates worst-status-wins into `ok` / `degraded` /
  `unavailable`, returning `503` only for `unavailable`.

Startup does not block on the database: the process comes up and reports *not
ready* rather than crash-looping while PostgreSQL starts.

## 6. Errors

Every failure is rendered as one envelope:

```json
{ "error": { "code": "not_found", "message": "…", "request_id": "…" } }
```

Expected failures subclass `AppError` and carry their own status and code.
Unexpected exceptions are logged with a stack trace and reported to the client
as a generic message, so internals never leak. `request_id` correlates the
client-visible error with the server log line.

## 7. Observability

- Structured JSON logs (`app/core/logging.py`), one line per record.
- A correlation id per request, propagated via a `ContextVar` and echoed in the
  `X-Request-ID` response header; a client-supplied header is honoured so ids
  survive across services.
- **Logs carry request metadata only.** Never bodies, credentials, tokens, or
  extracted medical content. This is a hard rule, not a default.

## 8. Statelessness

The API layer holds no per-user state in process memory. Everything durable is
in PostgreSQL, everything request-scoped dies with the request. This is what
allows the production topology (load balancer → N FastAPI instances) without
sticky sessions.

The one deliberately non-stateless piece is local Ollama inference, which is why
it sits behind `LLMService` and is expected to become a shared inference server
in production.

## 9. Frontend

- **Vite dev proxy** forwards `/api` to the backend, and nginx does the same in
  the container image. The browser is therefore same-origin in both, which
  matters once auth cookies arrive in Phase 2.
- **One axios instance** (`services/apiClient.ts`) with a response interceptor
  that normalises every failure into an `ApiError`. Components never see raw
  axios errors.
- **Explicit async state machines** (`hooks/useAsync.ts`) — `loading` /
  `success` / `error` are distinct states, so every screen can render a real
  loading, empty and error state rather than inferring them from `null`.
  `loading` is *derived* during render rather than written from inside an
  effect, which avoids a cascading re-render on every refetch.
- **Safety wording lives in one component** (`MedicalDisclaimer`), so the
  disclaimer can never drift between pages.
- Strict TypeScript, including `exactOptionalPropertyTypes` and
  `noUncheckedIndexedAccess`.

### Visual design

High-contrast, typography-led layout: an oversized display scale, a monochrome
neutral ramp (`ink-0` … `ink-950`), full-bleed contrast bands, and rule-separated
list rows instead of decorative cards. Colour is used sparingly and carries
meaning — the reserved `danger` ramp is for medical red-flag warnings only and
must never be used for ordinary UI errors.

### Dark mode

Three-state preference: `light`, `dark`, or `system` (the default, which follows
the OS live via a `matchMedia` listener). An explicit choice is persisted to
`localStorage` and always beats the OS setting.

- `ThemeProvider` (`contexts/ThemeProvider.tsx`) owns the state and applies a
  `dark` class to `<html>`.
- Tailwind is configured with `@custom-variant dark (&:where(.dark, .dark *))`
  in `index.css`, so `dark:` follows that class rather than the media query —
  which is what makes a manual override possible at all.
- A small inline script in `index.html` applies the stored theme **before first
  paint**, so there is no flash of the wrong colour scheme. It duplicates the
  storage key deliberately; `contexts/theme.ts` documents that the two must be
  changed together.

## 10. Authentication and authorization

### Credentials

Passwords are hashed with **Argon2id** (`argon2-cffi` defaults). Hashes are
upgraded transparently on login when the parameters fall behind. Plaintext
passwords exist only inside `app/core/security.py`, are never logged, and are
stripped from validation errors before they reach a response — Pydantic puts the
offending value in its error output, which for a signup form is the password
itself.

Login is constant-shaped: an unknown address is verified against a dummy hash so
the response, the error code and the timing are identical to a wrong password.
Account existence is not disclosed to anonymous callers.

### Tokens

| | Access | Refresh |
| --- | --- | --- |
| Lifetime | 30 min | 14 days |
| Transport | `Authorization: Bearer` | httpOnly cookie, `SameSite=Lax`, path-scoped to `/api/auth` |
| Client storage | memory only | not readable by script |
| Revocable | no | yes, via `users.token_version` |

The access token is deliberately **not** in `localStorage`: anything script can
read, an XSS payload can read. Sessions survive a reload because the frontend
silently exchanges the refresh cookie for a new access token on startup, and
again whenever a request returns 401 (once, with concurrent 401s sharing a
single refresh).

Logout increments `token_version`, which invalidates every outstanding refresh
token for that user. The current access token remains valid until it expires —
inherent to stateless JWTs, and the reason its lifetime is short.

`JWT_SECRET` is validated at startup: production refuses to boot with the
placeholder value or a key under 32 bytes (RFC 7518 §3.2).

### Google sign-in

The browser obtains an ID token; the server verifies it against Google's JWKS —
signature, issuer, audience and expiry — before trusting any claim. An
unverified `email_verified` is rejected outright, since an unverified address
must never be used to match an existing account.

Verification sits behind a `GoogleTokenVerifier` Protocol, so the test suite
substitutes a stub and never touches the network. With no `GOOGLE_CLIENT_ID`
configured the endpoint reports 503 rather than pretending to work.

Accounts are keyed on Google's `sub` claim, not email: a user who changes their
Google address keeps the same account.

### Account linking

When a Google sign-in presents an email that already belongs to a password
account, MedAnalyser **refuses** and returns `reason: google_link_required`. It
does not create a second account, and it does not silently attach the provider
to an account whose owner never asked for it. The user signs in with their
password and links Google deliberately. A provider identity belongs to exactly
one user, enforced by a unique constraint rather than by application logic alone.

### Age verification

Date of birth is collected during onboarding — never from the OAuth provider,
which is not a trustworthy source for it. Age is computed from the **server's**
clock; a rejected date is not persisted at all. Leap-year birthdays are handled
by tuple comparison (29 February counts on 1 March in non-leap years).

`OnboardedUser` is the dependency every medical feature will depend on, so an
account that has not passed the age check cannot reach one.

### Authorization

Route guards in the frontend control navigation only. Authorization is decided
server-side on every request; the browser is never trusted to enforce who may
read what. From Phase 3, repositories filter user-owned rows by `user_id` so the
ownership check exists in one place rather than in each route.

## 11. Safety architecture (planned, Phase 8)

The red-flag engine is **deliberately not an LLM prompt**. It is a deterministic
rule layer that runs independently, after assessment generation, and can
override the result. An LLM that has been talked out of an emergency finding is
a realistic failure mode; a rule table is not.

Emergency output takes priority over every other section of an assessment.

---

## Deviations from the original specification

| Spec | Built | Why |
| --- | --- | --- |
| Migrations in `infra/migrations/` | `backend/alembic/` | `env.py` imports the app's models and settings; co-locating avoids fragile cross-directory path handling. `infra/docker/` is used as specified. |
| React 18 / Vite 5 / React Router 6 | React 19 / Vite 7 / React Router 7 | The originally pinned versions carry published security advisories (esbuild dev-server, React Router open redirect). The current majors install with `0 vulnerabilities` and required no code changes. |

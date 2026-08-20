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
| File storage | `StorageService` | `LocalStorageProvider` | `S3StorageProvider` |
| Doctor discovery | `DoctorDiscoveryService` | mock provider | a maps/places API |

Provider selection is by environment variable (`STORAGE_PROVIDER`,
`DOCTOR_PROVIDER`). The interfaces land with the phases that need them rather
than being stubbed now.

**Machine learning is deliberately not behind a provider abstraction.** The
model is not a swappable vendor: it is trained in this repository from a
documented dataset and loaded from a local artifact. An abstraction there would
be indirection with nothing to switch between. See section 12.

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

Model artifacts are read-only and loaded once per process, so ML inference does
not compromise this: any instance can serve any request.

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

## 11. The medical profile

The profile is a user's **standing clinical context** — allergies, existing
conditions, regular medications — as distinct from an assessment, which is a
point-in-time episode. Later phases combine both.

### Why relational, not JSONB

Each collection is its own table. These are discrete records that later phases
filter, compare against retrieved evidence, and cite in an assessment's
reasoning; a JSONB blob would make all of that awkward and unindexable. JSONB is
reserved for genuinely open-ended shapes, such as an LLM's extraction output
whose keys vary by report type.

Date of birth stays on `users` rather than being duplicated here, so age
verification has exactly one source of truth.

### Replacement semantics

`PUT /api/profile` replaces the whole document, collections included: whatever
is submitted becomes the profile. That matches how the form behaves — the user
edits a page and saves it — and avoids a per-item CRUD surface for data that is
only ever edited as a unit. Scalars and all three collections are written in one
transaction, so a partially-saved profile is never observable.

### Ownership

`ProfileRepository` takes a `user_id` on every method and filters on it, so
ownership is enforced by construction — there is no query in the layer capable
of returning another user's rows. Deletes are scoped the same way, which is what
stops one user's save from clearing another's records. The identity always comes
from the verified token, never from a request body or path parameter. Both
endpoints require `OnboardedUser`, so an account that has not passed the age
check cannot hold medical data at all.

### Onboarding as a wizard

Onboarding collects the whole profile, not just the date of birth, in six steps:

1. **Date of birth** — the only required step. It is the age gate, so it cannot
   be skipped, and it is saved through `POST /api/auth/onboarding` before the
   flow continues.
2–6. Sex/gender, allergies, conditions, medications, emergency contact and
   notes — each with *Skip this question* and *Skip the rest for now*.

The optional answers accumulate in a client-side draft and are written with a
single `PUT /api/profile` when the user finishes or leaves early, so a partial
walk-through never produces a partially-saved profile.

Two consequences of `PUT` being a full replacement:

* A user resuming the wizard (date of birth already recorded) **must** have
  their existing profile loaded into the draft first. Skipping from a blank
  draft would delete everything they had previously saved — this shipped as a
  bug and is now covered by tests on both the contract and the round trip.
* The form is rendered only once that load resolves.

Field editors live in `components/profile/editors.tsx` and are shared by the
wizard and the profile page, so the two cannot drift in labelling or behaviour.

### Recorded, not interpreted

Medication dose and frequency are free text, stored exactly as the user reports
them. MedAnalyser records what it is told and never derives, validates or
suggests a dose. Conditions are likewise the user's own account of their
history — Phase 8 must keep that separate from anything the model concludes.

## 12. Machine learning

MedAnalyser's core intelligence is a **locally trained scikit-learn model**. No
external, hosted or paid AI API is called on any code path.

```
ml/  (offline)                      backend/app/services/ml/  (online)
─────────────                       ────────────────────────
ingest → dataset → train            model_loader → inference
   │        │        │                    ▲
   └────────┴────────┴────────────────────┘
        shared: condition_prediction/features.py
```

### Training and inference are separate — and share features

Training lives outside the application; the API only ever *loads* artifacts, and
never trains on any code path. But both import the **same**
`features.py`. That is the single most important structural decision in this
package: if vectorisation drifted between fitting and serving, every prediction
would be silently wrong while every other test still passed. Sharing the module
makes the drift impossible rather than merely unlikely.

### Why no provider abstraction

Storage and doctor discovery sit behind interfaces because they are vendor
choices. The model is not: it is trained here, from a documented dataset, and
loaded from a local file. Wrapping it would be indirection with nothing to swap.
Model *versioning* — which the metadata file carries and every assessment will
record — is the substitute that actually matters.

### Loading

Artifacts load once per process, cached with `lru_cache`, warmed during startup.
A missing model is non-fatal by default (`ML_REQUIRE_MODEL=false`): everything
except prediction still works, and a fresh checkout has no artifacts until
training has been run. Readiness reports the model as `degraded` rather than
failing. Production sets `ML_REQUIRE_MODEL=true` to refuse to start without one.

### Honesty about what the model is

The Phase 4 dataset is synthetic and templated — 93.8% duplicate rows, and every
symptom set maps to exactly one disease. It is a deterministic lookup table, so
any capable model scores near-perfectly and that figure means nothing. Three
things follow, and they are enforced in code rather than merely documented:

* **Deduplication precedes splitting.** Training also reproduces the naive
  pre-deduplication split to quantify the inflation it prevents.
* **Scores are not probabilities.** No calibration has been performed, so the
  schema calls the field `score` and documents it as a relative model output.
* **Thin input is flagged.** Measured accuracy falls to ~0.79 at three symptoms
  and ~0.39 at one, so `low_information` is set below three recognised
  symptoms and the caller is expected to gather more before showing results.

Unrecognised symptoms are returned to the caller rather than dropped, and an
input with nothing recognisable yields *no* predictions — ranking classes from
an all-zero vector would return whichever class the model favours by default,
dressed up as an answer.

## 13. Symptom assessment

The pipeline from what a user types to a stored, explainable result:

```
free text → SymptomExtractor → AssessmentState → FollowUpQuestionEngine
                                      ↓
                     ConditionPredictionService → PostgreSQL
```

### Rule-based NLP, on purpose

Symptom extraction is a curated synonym dictionary plus longest-phrase matching
— no LLM, no statistical NLP model. The target is a **closed vocabulary of 131
symptoms**; for that, rules are more accurate than a model, run instantly, cost
nothing, and are inspectable: when an extraction is wrong you can point at the
line responsible. The dictionary lives in a JSON data file, so extending it is a
data change, not a code change. A test asserts every key is a real model symptom
and that no key is duplicated — JSON silently keeps the last of duplicate keys,
which would discard synonyms without any error.

**Negation is handled explicitly.** "no chest pain" must not become chest pain:
that is not merely lost signal, it is the opposite of what the user said. A cue
list scans backwards a bounded window, stopping at contrast words so "no fever
but a bad cough" negates only the fever. Denied symptoms are *stored* rather
than discarded — "no chest pain" is clinically meaningful and different from
"not mentioned".

Duration and severity are parsed from the same text, so the intake never asks
for something the user already wrote.

### Follow-up questions as a state machine

`question_rules.json` declares each question, its `answer_type`, and an
`asked_when` expression in a tiny predicate language that is **parsed, not
`eval`'d**. The engine returns the first applicable unanswered question. Adding
a question is an edit to that file.

One question is model-informed: `additional_symptoms` offers the symptoms that
best *discriminate* between the current candidate conditions — those present in
some candidates but not all — rather than asking in arbitrary order. This is
where Phase 4's robustness measurement pays off: accuracy climbs from ~0.39 at
one symptom to ~0.79 at three, so eliciting the right extra symptom is the most
valuable thing the intake can do.

Symptoms offered but *not* selected are recorded as rejected. Without that the
engine would offer the same list forever.

### What is stored, and why

Every assessment records the verbatim input, the extracted features, the
conversation transcript, the predictions, **and the model name and version**.
Version attribution is what keeps an old result interpretable after the model
changes; without it a stored prediction is an unattributable number.

### Honest presentation

The UI never shows a raw score as a percentage. The value is an uncalibrated
relative output, and "72%" reads as a clinical probability to a worried person,
so results are banded qualitatively. Explanations cite only symptoms the user
actually reported and are labelled as an explanation of the model, not evidence
of causation. Thin input carries a visible warning.

### Ownership

`AssessmentRepository` filters on `user_id` inside the query rather than
checking after the fact, so a missing assessment and someone else's assessment
are indistinguishable — the endpoint returns 404 either way and never confirms
that an id exists.

## 14. Medical report processing

    PDF → PyMuPDF text layer → (per page, if empty) OCR → lab value extraction

### Storage behind an interface

Business logic depends on `StorageService`, never on the filesystem, so moving
uploaded reports to object storage is a new provider plus one environment
variable. Two properties of the local provider matter more than the interface:

* **The stored name is generated, never the user's.** An uploaded filename is
  attacker-controlled — path separators, traversal, null bytes. The original is
  kept in the database as a display label and never touches the filesystem.
* **Keys are re-validated on read.** Even a corrupted database row cannot make
  the API read outside its root: the key must match the generated shape *and*
  the resolved path must still be under the root.

### Upload validation

The one endpoint that accepts arbitrary bytes from the internet, so a file is
checked four ways: declared content type, extension, size, and **actual magic
bytes**. A declared `application/pdf` is a claim, not evidence. The body is read
with a cap rather than trusting the client's `content-length`.

Uploads are deduplicated per user by SHA-256; a refused duplicate deletes the
copy it just wrote rather than leaving an orphan.

### OCR fallback is per page, not per document

Most lab reports are generated digitally and carry an exact text layer. Scans
have none. The fallback is decided **per page**, because a report whose results
table is a scanned image pasted into a digital letterhead would otherwise lose
exactly the part that matters. Which path ran is recorded and shown to the user:
OCR output is materially less reliable, and someone checking values deserves to
know which they are reading.

### Extracted, never inferred

Two rules govern the lab extractor, and both are enforced in code:

* **No value is invented.** A number that is not on the page is absent from the
  output. A label with no result yields nothing.
* **No reference range is invented.** Normal ranges vary by laboratory, assay,
  age and sex, so abnormality is judged *only* against a range printed on the
  report itself. Where none is printed, the value is stored and left unflagged
  rather than compared with a hard-coded number. A test asserts the analyte data
  file contains no ranges at all.

Unrecognised units are kept verbatim and flagged rather than normalised —
silently treating mg/dL as g/dL would change a value a thousandfold while
looking perfectly correct. Analyte names and unit spellings live in a JSON data
file; tests assert no duplicate keys and no alias owned by two analytes, since
either would silently attribute a value to the wrong test.

Values are read line by line, because lab reports are tabular and scanning
across lines pairs a label with the next row's number.

## 15. Safety architecture (planned, Phase 8)

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

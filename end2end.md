# RTI4All — End-to-End Walkthrough

This doc explains how the RTI4All system is wired up: every component, every
request hop, every piece of state. It's intended for a new engineer joining
the project who needs to understand the whole pipeline without reading every
file.

> RTI4All is a Right-to-Information citizen portal for the Maldives Ministry
> of Climate Change, Environment and Energy. Citizens file RTI requests; an
> AI drafts a grounded response from the ministry archive; a ministry officer
> reviews, edits, approves, rejects, or asks for clarification.

---

## 1. High-level architecture

```
┌──────────────────────┐        HTTP        ┌─────────────────────────┐
│ Browser (React SPA)  │  ── /api/* ──>     │  Go backend (port 8000) │
│ Vite dev server      │   via Vite proxy   │  chi router + net/http  │
│ port 5173            │                    │                         │
└──────────────────────┘                    │  ┌───────────────────┐  │
                                            │  │ in-memory DB      │  │
                                            │  │  (requests, users)│  │
                                            │  └─────────┬─────────┘  │
                                            │            │            │
                                            │  ┌─────────▼─────────┐  │
                                            │  │  JSON persistence │  │
                                            │  │  + backups        │  │
                                            │  └───────────────────┘  │
                                            │                         │
                                            │  ┌───────────────────┐  │
                                            │  │ RAG (TF-IDF) +    │  │
                                            │  │ graph retrieval   │  │
                                            │  └─────────┬─────────┘  │
                                            │            │            │
                                            │  ┌─────────▼─────────┐  │
                                            │  │ Anthropic Messages│──┼──> api.anthropic.com
                                            │  │ API client        │  │
                                            │  └───────────────────┘  │
                                            └─────────────────────────┘
```

Both containers run side-by-side under one `docker compose up --build`.
`backend/` (Python/FastAPI) is the legacy implementation, retained for
reference. The shipping stack uses `backend-go/`.

---

## 2. Repository layout

```
RTI4All/
├── docker-compose.yml        # backend → backend-go/, frontend → frontend/
├── .env                      # ANTHROPIC_API_KEY, JWT_SECRET_KEY, ADMIN_EMAILS
├── end2end.md                # ← this file
│
├── frontend/                 # React SPA (Vite dev server)
│   ├── Dockerfile            # node:20-alpine → npm run dev
│   ├── vite.config.js        # proxies /api → backend:8000
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       └── App.jsx           # all routes + screens in one file (~2400 lines)
│
├── backend-go/               # Go backend (the one we ship)
│   ├── main.go               # entrypoint: load data, build indexes, start HTTP
│   ├── Dockerfile            # multi-stage build → ~15 MB Alpine image
│   ├── go.mod / go.sum
│   ├── data/sample_data.json # seed corpus (departments, FAQs, prior RTIs)
│   └── internal/
│       ├── models/           # JSON shapes for the wire + on-disk store
│       ├── persistence/      # atomic JSON writes + rotated backups
│       ├── cache/            # in-memory query cache for AI answers
│       ├── rag/              # TF-IDF + cosine retrieval over the archive
│       ├── graph/            # token-cooccurrence graph retrieval
│       ├── ai/               # Anthropic REST client (structuring + drafting)
│       ├── auth/             # JWT, bcrypt, chi middleware
│       └── handlers/         # all /api/* HTTP routes
│
└── backend/                  # Python/FastAPI (legacy reference)
    └── ... (kept untouched)
```

---

## 3. Boot sequence

When `docker compose up --build` runs:

1. **`backend-go` image build** (multi-stage):
   - Stage 1 (`golang:1.22-alpine`): `go mod download`, then
     `CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/rti4all ./`.
   - Stage 2 (`alpine:3.20`): copies the binary in, installs `ca-certificates`
     (needed for HTTPS to Anthropic), creates a non-root `rti4all` user,
     chowns `/app/data/` so backups can be written.
   - Final image: ~15 MB; entrypoint `["/app/rti4all"]`.

2. **`frontend` image build** (`node:20-alpine`): `npm install`,
   `CMD npm run dev` → Vite dev server on `:5173`.

3. **Backend container starts** (`main.go`):
   1. Read env (`PORT`, `DATA_FILE`, `JWT_SECRET_KEY`, `ADMIN_EMAILS`,
      `ANTHROPIC_API_KEY`, `ENABLE_DATA_PERSISTENCE`, `MAX_BACKUPS`).
   2. `persistence.NewStore(...)` → ensure `data/` and `data/backups/` exist.
   3. `store.Load()` → parse `data/sample_data.json` into a `*models.DB`.
   4. Build the auth service, Anthropic client, query cache.
   5. `rag.PopulateFromDB(...)` → TF-IDF index of every *responded* RTI
      request + every FAQ.
   6. `graphState.BuildFromDB(...)` → build a per-document token map +
      cooccurrence matrix for the same documents.
   7. `seedDefaultUsers(...)` → create `officer@gov.mv` (admin, because the
      email is in `ADMIN_EMAILS`) and `citizen@example.mv`.
   8. Build the chi router with the route table (see §5).
   9. Wrap it in CORS (`*`) + request-logging middleware.
   10. `http.ListenAndServe(":8000", ...)` and wait on SIGINT/SIGTERM.

4. **Frontend container starts**: Vite dev server, with HMR, proxying `/api`
   to `http://backend:8000` over the compose network.

A successful boot looks like:

```
rti4all-backend  | [startup] seeded default user officer@gov.mv
rti4all-backend  | [startup] seeded default user citizen@example.mv
rti4all-backend  | [startup] ✓ RTI4All backend (Go) ready
rti4all-backend  | [startup]   requests=20 departments=5 faqs=10
rti4all-backend  | [startup]   RAG items=19  graph docs=19  persistence=true  ai=true
rti4all-backend  | [startup]   listening on :8000
```

---

## 4. State model

There is exactly one source of truth: an in-memory `*models.DB` held by the
HTTP `Server` struct. Every read goes through it. Every write goes through
it. After every write that mutates the DB, a background goroutine snapshots
it to disk.

`models.DB` is a flat aggregate:

```go
type DB struct {
    Departments []Department
    Requests    []*RTIRequest
    FAQs        []FAQ
}
```

A `RTIRequest` carries the full record (citizen profile snapshot, response,
review audit, structured analysis, clarification history, citizen updates).
A `PublicRequest` is the citizen-facing projection that hides the profile
snapshot and the internal `reviewed_by`/`reviewed_at` fields.

Users are kept in a separate in-memory map inside `internal/auth`. They are
**not** persisted — restarting the backend recreates the two default users
and forgets everyone else. This matches the original Python behaviour.

### Persistence

`internal/persistence/persistence.go` is responsible for the on-disk JSON
store at `data/sample_data.json`:

- **Atomic writes**: encode to `sample_data.json.tmp`, then `os.Rename` →
  no half-written files on crash.
- **Backups**: before every save, copy the live file to
  `data/backups/sample_data_YYYYMMDD_HHMMSS.json`. Rotation keeps the most
  recent `MAX_BACKUPS` (default 10).
- **Recovery**: on load, if JSON decode fails on the main file, the loader
  walks backups newest-first and returns the first one that parses.

---

## 5. The HTTP API

All endpoints are versionless and JSON in, JSON out. Auth uses bearer JWTs
issued by `/api/auth/login` and `/api/auth/signup`. Sessions are 24 hours.

```
GET    /api/health                     → 200 {"status":"ok"}            (public)

POST   /api/auth/signup                → 201 {access_token,user}        (public)
POST   /api/auth/login                 → 200 {access_token,user}        (public)
GET    /api/auth/me                    → 200 UserPublic                 (auth)

GET    /api/departments                → 200 [Department]               (public)
GET    /api/departments/{id}           → 200 Department | 404
GET    /api/faqs                       → 200 [FAQ]                      (public)
GET    /api/stats                      → 200 {counts by status, totals} (public)

GET    /api/requests                   → 200 [PublicRequest]            (auth)
POST   /api/requests                   → 201 RTIRequest                 (auth)
GET    /api/requests/{id}              → 200 PublicRequest | 403 | 404  (auth)
PATCH  /api/requests/{id}/clarify      → 200 PublicRequest              (auth, owner-only)

GET    /api/admin/requests/pending     → 200 [RTIRequest]               (admin)
GET    /api/admin/requests/{id}        → 200 RTIRequest                 (admin)
PATCH  /api/admin/requests/{id}        → 200 RTIRequest                 (admin)
```

### Auth model

- Passwords hashed with bcrypt (`golang.org/x/crypto/bcrypt`).
- JWT signed with HS256 using `JWT_SECRET_KEY` (`golang-jwt/jwt/v5`).
- Claims: `sub` (email), `name`, `is_admin`, `iat`, `exp`.
- `ADMIN_EMAILS` (comma-separated) determines who gets `is_admin=true`. This
  is checked at signup time and re-checked at login (so adding a user to the
  list later promotes them on next sign-in).
- Two chi middlewares wrap protected routes:
  - `RequireAuth` → 401 if the bearer is missing/invalid.
  - `RequireAdmin` → 401 then 403 if the bearer is valid but not admin.

### Citizen authorization

`/api/requests` returns only the caller's own requests, *unless* the caller
is admin (then it returns everything). `GET /api/requests/{id}` 403s if the
caller doesn't own the record (admins bypass). `PATCH /api/requests/{id}/clarify`
is owner-only — admins cannot impersonate a citizen here.

---

## 6. The request lifecycle (the interesting part)

This is what happens end-to-end when a citizen files an RTI request and an
officer reviews it.

### Step 1 — Citizen files a request

Frontend `NewRequestPage` POSTs to `/api/requests`:

```json
{ "department_id": "moccee",
  "subject": "How do I file a follow-up RTI?",
  "description": "I would like a brief explanation of the procedure..." }
```

`handlers.createRequest`:

1. Reads the authenticated user from the request context (set by
   `RequireAuth`).
2. Validates inputs and looks up the department name.
3. Generates the next sequential id: `RTI-<year>-NNNN`.
4. **Structures the request** via `ai.ProcessRequestStructure(...)`. This
   calls the Anthropic Messages API with `claude-3-5-sonnet-20241022` and
   asks for a JSON object containing:
   - `request_type` (Data Request, Policy Clarification, ...)
   - `key_questions`, `information_sought`
   - `time_period`, `geographic_scope`, `urgency_indicators`
   - `completeness_score` ∈ [0, 1]
   - `missing_information`, `related_policies`
   - `estimated_complexity`, `suggested_response_approach`,
     `relevant_precedents`

   If the API call fails or the JSON is malformed, a deterministic fallback
   structure is returned so the rest of the flow still works.

5. **Decision: draft now or wait for officer?**
   - If `completeness_score >= 0.7`, call `generateAnswer(...)` to produce a
     citizen-facing draft response and set status `Under Review`.
   - Otherwise, leave `response = ""` and set status `Under Review` so the
     officer can read the structured analysis and ask for clarification.

6. **AI draft (`generateAnswer`)** is itself two-step:
   a. **Cache check** — `cache.MakeKey(department_id, subject, description)`
      normalises the text and looks for a prior identical draft. If hit,
      return the cached answer immediately.
   b. **Retrieve + draft** — the AI client (`ai.AnswerRequest`):
      - Concatenates subject + description into a query string.
      - Asks `rag.Index.Retrieve(query, 4)` for the top-4 cosine-similar
        documents from the TF-IDF index.
      - Asks `graph.State.Retrieve(query, 7)` for the top-7 token-graph-linked
        documents.
      - Dedupes the graph hits against the vector hits by `id` and keeps up
        to 3.
      - Builds a system prompt that interpolates both retrieved blocks,
        and asks `claude-haiku-4-5` (1024 max tokens, no tools) to draft a
        4–8 sentence reply that cites the prior RTI ids it leans on.
      - Returns the text.

7. The new `RTIRequest` is appended to `db.Requests`, persistence kicks off
   in a background goroutine, and the full record is returned to the
   citizen.

### Step 2 — Citizen sees their request

Frontend's `RequestDetailPage` GETs `/api/requests/{id}`. The handler returns
the `PublicRequest` projection. If `status == "Under Review"` and there's a
draft response, the UI shows a purple "Draft Response · Pending Officer
Review" card with a disclaimer.

### Step 3 — Officer reviews

The officer logs in (admin token issued because their email is in
`ADMIN_EMAILS`), opens the admin inbox at `/admin`, which GETs
`/api/admin/requests/pending`. The handler returns every `Under Review`
record sorted oldest-first.

They click into one and see the full record including the `processed_data`
analysis and the AI draft, on `/api/admin/requests/{id}`.

The officer has three actions:

#### a) Approve

Frontend PATCHes `/api/admin/requests/{id}` with
`{ response: "<edited text>", status: "Responded" }`.

The handler:

1. Validates the new status is in `adminEditableStatuses`.
2. Updates the record's response, status, `date_updated`, `reviewed_by`,
   `reviewed_at`.
3. **Feedback loop**: snapshots the request and, outside the lock, calls
   `rag.IndexResponded(...)` and `graph.UpdateForRequest(...)`. The newly
   approved response is now retrievable for future drafts — each approval
   enriches the corpus.
4. Persists to disk in the background.

#### b) Reject

PATCH with `{ status: "Rejected", rejection_reason: "..." }`. Same audit
stamping, no index update.

#### c) Request clarification

PATCH with
`{ request_clarification: { message, missing_fields, questions, suggested_improvements } }`.

The handler takes a dedicated branch:

1. Appends a record to `clarification_history` (with timestamp + officer
   email).
2. Sets `clarification_requested = ...` and `status = "Clarification Needed"`.
3. Persists.

### Step 4 — Citizen answers the clarification

The citizen sees the clarification on the request detail page and can PATCH
`/api/requests/{id}/clarify` with their updated description, additional
info, and answers-to-questions. The handler:

1. 403s unless the caller owns the request.
2. 400s unless the request is currently in `Clarification Needed`.
3. Appends a record to `citizen_updates`, updates the description if a new
   one was supplied, clears `clarification_requested`, flips status back to
   `Under Review`.
4. Re-runs `ai.ProcessRequestStructure(...)` on the updated text so the
   officer sees a refreshed analysis.

The officer can now re-review.

---

## 7. Retrieval internals

### TF-IDF (`internal/rag`)

The "vector search" in this codebase is intentionally lightweight — no
embedding model, no GPU, no network call.

- Each document (a responded RTI request or an FAQ) is tokenised into
  lowercase word tokens (3+ chars, non-stopword).
- Term frequencies are converted to TF-IDF weights with smoothed IDF, then
  L2-normalised.
- Retrieval = dot product (equivalent to cosine since both vectors are
  L2-normalised) against every document, take top-k.

The index is small (tens to low hundreds of items), so the linear scan is
sub-millisecond. `Upsert` recomputes IDF and re-vectorises everything; this
is cheap at our scale and simpler than maintaining incremental statistics.

### Token co-occurrence graph (`internal/graph`)

The original Python implementation used the `graphify` CLI (LLM-based
entity extraction) to build a knowledge graph over the archive. That doesn't
exist for Go and would dominate cold-start cost, so the Go port substitutes
a deterministic alternative:

- **Nodes** are notable tokens (4+ chars, non-stopword) that appear in at
  least one document.
- **Edges** are co-occurrence counts within a document.
- **Retrieve(query, k)** tokenises the query, weighs each query term at 1.0,
  expands by one hop into the top-8 cooccurring terms (each weighted 0.5),
  then scores every document by the sum of weights for terms it contains.

This surfaces documents that share concepts with the query even when no
single keyword matches exactly — the same property graphify was providing.

Both retrieval results are stitched into the AI's system prompt under
"VECTOR MATCHES" and "GRAPH-LINKED PRECEDENT" blocks (see
`ai/ai.go: answerSystemTemplate`).

---

## 8. Where each part of the frontend hits the backend

| UI screen                    | Routes called                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------ |
| `HomePage`                   | `GET /api/stats`                                                               |
| `LoginPage` / `SignupPage`   | `POST /api/auth/login`, `POST /api/auth/signup`                                |
| `RequestsPage`               | `GET /api/requests` (filters applied client-side)                              |
| `RequestDetailPage`          | `GET /api/requests/{id}`                                                       |
| `NewRequestPage`             | `GET /api/departments`, `POST /api/requests`                                   |
| `DepartmentsPage`            | `GET /api/departments`                                                         |
| `FaqsPage`                   | `GET /api/faqs`                                                                |
| `AdminInboxPage`             | `GET /api/admin/requests/pending`                                              |
| `AdminRequestReviewPage`     | `GET /api/admin/requests/{id}`, `PATCH /api/admin/requests/{id}`               |

Auth is stored in `localStorage` under `rti4all-auth`. The custom hook
`useAuthedFetch` injects the bearer header and bounces back to `/login` on
401.

---

## 9. Environment configuration

Pulled from `.env` (loaded by docker compose via `env_file:`). All variables
have safe defaults so the stack boots without an `.env` file too.

| Variable                  | Used by             | Default                       |
| ------------------------- | ------------------- | ----------------------------- |
| `PORT`                    | backend             | `8000`                        |
| `DATA_FILE`               | backend             | `data/sample_data.json`       |
| `JWT_SECRET_KEY`          | backend / auth      | dev fallback (insecure)       |
| `ADMIN_EMAILS`            | backend / auth      | empty                         |
| `ANTHROPIC_API_KEY`       | backend / ai        | empty (stub responses)        |
| `ANTHROPIC_MODEL`         | backend / ai (draft) | `claude-haiku-4-5`           |
| `ANTHROPIC_STRUCTURE_MODEL` | backend / ai (json) | `claude-3-5-sonnet-20241022` |
| `ENABLE_DATA_PERSISTENCE` | backend             | `true`                        |
| `MAX_BACKUPS`             | backend             | `10`                          |

If `ANTHROPIC_API_KEY` is unset, the AI step returns a clearly-labelled
stub response — the rest of the workflow still functions, which is useful
for offline development.

---

## 10. Default accounts

Seeded on every boot (idempotent — re-creating an existing user is a no-op):

| Role     | Email                | Password           | Notes                                |
| -------- | -------------------- | ------------------ | ------------------------------------ |
| Officer  | `officer@gov.mv`     | `super-secret-pass`| Admin (via `ADMIN_EMAILS`)           |
| Citizen  | `citizen@example.mv` | `another-pass`     | Files RTI requests as Aishath Hassan |

---

## 11. Running it

### One-shot

```bash
docker compose up --build
```

- Backend: <http://localhost:8000> (`GET /api/health` → `{"status":"ok"}`)
- Frontend: <http://localhost:5173>
- Frontend's Vite proxy forwards `/api/*` to the backend container.

### Local dev (no Docker)

```bash
cd backend-go
go run .
```

(Backend on `:8000`, reads `./data/sample_data.json`.)

```bash
cd frontend
npm install
npm run dev
```

(Frontend on `:5173`, proxies `/api` to `http://backend:8000` — which only
resolves inside the compose network. For non-Docker dev, edit
`frontend/vite.config.js` to target `http://localhost:8000`.)

### Smoke test

The end-to-end test script exercises every endpoint:

```bash
# After docker compose up:
bash /tmp/smoke.sh
```

Covers: health, auth (signup/login/conflict/bad-credentials), all read
endpoints, citizen authz (own-only), admin authz (full view), filing a new
request (AI structured + drafted), admin approve → `Responded` (with RAG +
graph refresh), admin → request-clarification → `Clarification Needed`, bad
tokens, 404s.

---

## 12. Failure modes and how they're handled

| Failure                         | Behaviour                                                                                |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| Anthropic API down / quota hit  | `AnswerRequest` returns error → request still filed with `status="Pending"`, no draft.   |
| Anthropic returns bad JSON      | `ProcessRequestStructure` falls back to deterministic skeleton; request still created.   |
| `sample_data.json` corrupted    | Loader walks `data/backups/` newest-first and returns the first that parses.             |
| Persistence write fails         | Logged; the in-memory DB still has the change (so the response succeeds).                |
| Token expired / revoked         | Backend returns 401; frontend's `useAuthedFetch` clears local auth and routes to login.  |
| Non-admin hits `/admin/*`       | 403 `Administrator access required.`                                                     |
| Citizen tries to read someone else's request | 403 `You do not have permission to access this request.`                      |
| Citizen tries to clarify a non-clarification-needed request | 400 `No clarification has been requested.`                  |

---

## 13. What was replaced from the Python implementation

The Python backend (`backend/`) is preserved for reference. The Go port
makes the following substitutions:

| Concern             | Python                                          | Go                                                  |
| ------------------- | ----------------------------------------------- | --------------------------------------------------- |
| HTTP framework      | FastAPI + uvicorn                               | chi + net/http                                      |
| Auth                | python-jose + passlib/bcrypt                    | golang-jwt + golang.org/x/crypto/bcrypt             |
| Anthropic client    | `anthropic` SDK + web tools (`web_search`)      | direct REST over net/http, no web tools             |
| Embeddings          | sentence-transformers (`all-MiniLM-L6-v2`)      | TF-IDF + cosine, in-process                         |
| Knowledge graph     | `graphify` CLI subprocess + LLM extraction      | token-cooccurrence graph, in-process                |
| Container size      | ~1 GB (PyTorch + transformers)                  | ~15 MB (static binary on Alpine)                    |
| Cold start          | ~10–15 s (model load)                           | ~50 ms                                              |

The HTTP contract is identical, so the React frontend was not touched.

---

## 14. Mental model — one diagram

```
        File RTI            Officer review            Citizen sees
            │                      │                       │
            ▼                      ▼                       ▼
┌──────────────────┐   ┌────────────────────┐   ┌──────────────────┐
│ POST /api/       │   │ PATCH /api/admin/  │   │ GET  /api/       │
│   requests       │   │   requests/{id}    │   │   requests/{id}  │
└────────┬─────────┘   └─────────┬──────────┘   └──────────────────┘
         │                       │                       ▲
         │  ┌────────────────────┘                       │
         │  │                                            │
         ▼  ▼                                            │
┌──────────────────────────────────────────────┐         │
│  in-memory models.DB  (single source of truth)│────────┘
└────┬──────────────────────────────┬───────────┘
     │                              │
     ▼                              ▼
┌───────────────────┐      ┌──────────────────────┐
│ AI: structure +   │      │ persistence: atomic  │
│ draft (Anthropic) │      │ JSON + backups       │
└────────┬──────────┘      └──────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ retrieval (RAG TF-IDF + token │
│ cooccurrence graph) over the │
│ ministry archive             │
└──────────────────────────────┘
```

That's the whole system.

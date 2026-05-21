# RTI4All — Right to Information portal

A citizen-facing portal and ministry admin panel for filing and reviewing
**Right to Information (RTI)** requests with the Maldives
[Ministry of Climate Change, Environment and Energy](https://environment.gov.mv).

Citizens file requests; an AI assistant drafts a response grounded in the
ministry archive; a ministry officer approves, edits, rejects, or asks for
clarification before the response is published — human-in-the-loop, by
design.

> Built for **Colab26 Hackathon · Team 9**.

---

## Tech stack

| Layer            | Technology                                                                       |
| ---------------- | -------------------------------------------------------------------------------- |
| Frontend         | React 18 + TypeScript + Vite, Tailwind CSS (custom grayscale + blue palette)     |
| Backend          | Go 1.22 (chi router, net/http, golang-jwt, bcrypt)                               |
| AI               | Anthropic Messages API — `claude-haiku-4-5` (drafts), `claude-3-5-sonnet` (JSON) |
| Retrieval        | TF-IDF + cosine (in-process) and a token-cooccurrence graph (in-process)        |
| Auth             | JWT (HS256) + bcrypt password hashing                                            |
| Data             | In-memory state with atomic JSON snapshots + rotated backups                     |
| Container        | Docker + Docker Compose (multi-stage build → ~15 MB backend image)               |
| Legacy           | Python/FastAPI implementation retained under `backend/` for reference            |

---

## Quickstart

```bash
docker compose up --build
```

- Frontend: <http://localhost:5173>
- Backend:  <http://localhost:8000/api/health>

The Vite dev server proxies `/api/*` to the Go backend via the compose
network, so the SPA talks to `http://localhost:5173` for everything.

### Default accounts (seeded on every boot)

Two demo accounts are seeded at startup. They are how the whole flow
gets demonstrated end-to-end.

#### 🟦 Information Officer (admin)

| Field        | Value                       |
| ------------ | --------------------------- |
| Email        | `officer@gov.mv`            |
| Password     | `super-secret-pass`         |
| Full name    | Officer Hassan              |
| Address      | Ministry HQ, Male'          |
| Phone        | +960 3001000                |
| `is_admin`   | **true** (via `ADMIN_EMAILS`) |

After login the navbar shows an **Admin** tab → `/admin` is the
review inbox.

#### 🟩 Citizen

| Field        | Value                                       |
| ------------ | ------------------------------------------- |
| Email        | `citizen@example.mv`                        |
| Password     | `another-pass`                              |
| Full name    | Aishath Hassan                              |
| Address      | H. Sunset, Hithadhoo, Addu City             |
| Phone        | +960 7777777                                |
| ID card      | A099887                                     |
| `is_admin`   | false                                       |

After login the navbar shows **My requests** + **File a request**.

> Tip for the demo: open two browser windows side-by-side (or one
> Chrome + one incognito), sign in as the citizen on one and the
> officer on the other so you can watch the lifecycle in real time.

### Demo script (≈3 minutes)

A repeatable walkthrough that exercises every stage of the agentic
workflow:

1. **Citizen window** (`citizen@example.mv`):
   - Click **File a request**, file something specific so the Structurer
     scores it high:
     - Subject: *"Solar PV capacity installed in Addu City, 2024"*
     - Description: *"Please provide the total solar PV generation
       capacity (in MW) commissioned in Addu City during calendar year
       2024, broken down by island."*
   - Submit. The detail page shows status **Under Review** with a
     purple **Draft Response · Pending Officer Review** card.
2. **Officer window** (`officer@gov.mv`):
   - Click **Admin** → the new request is at the top of the inbox.
   - Open it: left column shows the citizen's request, the AI draft
     (editable), reject reason, and clarification form. Right rail
     shows the AI analysis (type, complexity, completeness %).
   - Click **Approve & publish**.
3. **Citizen window**: refresh — status is now **Responded** with a
   green **Official response** card.
4. Now file a deliberately vague request as the citizen
   (e.g. *"info about energy"*). The Structurer flags low completeness
   → no draft is generated.
5. **Officer window**: open the new request → click **Ask for
   clarification**, type a message like *"Please specify which atoll
   and which year"*, list one or two questions, submit.
6. **Citizen window**: refresh — status is **Clarification Needed**
   with an amber form. Fill the answers in, submit, status flips back
   to **Under Review** with a refreshed AI analysis.

Steps 1–3 demonstrate the happy path (RAG + draft + human approve);
steps 4–6 demonstrate the agent recognising ambiguity and the
back-and-forth loop.

### Local dev without Docker


```bash
# Terminal 1 — backend
cd backend-go
go run .                       # listens on :8000

# Terminal 2 — frontend
cd frontend
npm install
VITE_API_TARGET=http://localhost:8000 npm run dev    # listens on :5173
```

---

## What's in the repo

```
RTI4All/
├── docker-compose.yml          # backend → backend-go/, frontend → frontend/
├── .env                        # ANTHROPIC_API_KEY, JWT_SECRET_KEY, ADMIN_EMAILS
├── README.md                   # ← this file
│
├── frontend/                   # React SPA — TypeScript + Tailwind, Vite
│   ├── Dockerfile              # node:20-alpine → npm run dev
│   ├── vite.config.ts          # proxies /api → backend:8000, @ → src
│   ├── tailwind.config.js      # ink-* grayscale + accent-* blue
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx            # entrypoint
│       ├── App.tsx             # router
│       ├── index.css           # tailwind base + focus/scrollbar polish
│       ├── api/client.ts       # typed fetch wrapper for /api/*
│       ├── components/         # UI kit + Layout + RouteGuards
│       ├── context/AuthContext.tsx
│       ├── lib/                # cn(), useAsync(), formatDate()
│       ├── pages/              # one page per route (citizen + admin/)
│       └── types/api.ts        # wire types mirroring the Go backend
│
├── backend-go/                 # Go backend (the one we ship)
│   ├── main.go                 # startup: load data, build indexes, serve HTTP
│   ├── Dockerfile              # multi-stage → ~15 MB Alpine image
│   ├── go.mod / go.sum
│   ├── data/sample_data.json   # seed corpus (departments, FAQs, prior RTIs)
│   └── internal/
│       ├── models/             # JSON shapes for wire + on-disk store
│       ├── persistence/        # atomic JSON writes + rotated backups
│       ├── cache/              # in-memory query cache for AI answers
│       ├── rag/                # TF-IDF + cosine retrieval
│       ├── graph/              # token-cooccurrence graph retrieval
│       ├── ai/                 # Anthropic REST client (structure + draft)
│       ├── auth/               # JWT, bcrypt, chi middleware
│       └── handlers/           # all /api/* routes
│
└── backend/                    # Python/FastAPI (legacy reference)
    └── ...
```

---

## Architecture

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

Both containers come up under one `docker compose up --build`. The Python
backend is kept under `backend/` purely as a historical reference; the
shipping stack is `backend-go/` + the TypeScript SPA.

---

## The agentic workflow

RTI4All is not just "wrap an LLM around a form" — the AI is one stage in
a structured, agent-style pipeline that takes a free-text citizen request
and turns it into either an officer-ready draft or a structured "needs
clarification" object. Every step is observable, every decision is
auditable, and every approval makes the *next* request a little easier.

Here is the full agentic loop, top to bottom:

```
┌──────────────────────────────────────────────────────────────────────┐
│  ① Structurer agent  (Claude Sonnet, JSON-only)                      │
│     Subject + description  →  JSON analysis                          │
│                                                                       │
│       { request_type, key_questions, information_sought,             │
│         time_period, geographic_scope, urgency_indicators,           │
│         completeness_score ∈ [0,1],                                  │
│         missing_information, related_policies,                       │
│         estimated_complexity, suggested_response_approach,           │
│         relevant_precedents }                                        │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                  completeness_score < 0.7?
                  ┌────────────────┴────────────────┐
              YES │                                 │ NO
                  ▼                                 ▼
     ┌────────────────────────┐         ┌──────────────────────────┐
     │ ② Officer review queue │         │ ② Retriever              │
     │   status="Under Review"│         │   - TF-IDF top-4         │
     │   (no draft yet)       │         │   - Token-graph top-7    │
     │                        │         │   - Dedupe by id         │
     │ Officer reads JSON     │         │                          │
     │ analysis, asks for     │         │     ↓                    │
     │ clarification, or      │         │ ③ Drafter agent          │
     │ writes draft manually  │         │   (Claude Haiku)         │
     └────────────────────────┘         │   System prompt =        │
                                        │     archive context      │
                                        │   "Cite RTI ids, plain   │
                                        │    prose, 4-8 sentences" │
                                        └────────────┬─────────────┘
                                                     │
                                                     ▼
                                        ┌──────────────────────────┐
                                        │ status="Under Review",   │
                                        │ response = draft text    │
                                        │ (still needs human       │
                                        │  approval before publish)│
                                        └────────────┬─────────────┘
                                                     │
                                                     ▼
                                        ┌──────────────────────────┐
                                        │ ④ Officer decision       │
                                        │   • Approve  → Responded │
                                        │   • Reject   → Rejected  │
                                        │   • Clarify  → Clarif.   │
                                        │       Needed             │
                                        └────────────┬─────────────┘
                                                     │
                              Approve path           │
                                                     ▼
                                        ┌──────────────────────────┐
                                        │ ⑤ Feedback loop          │
                                        │   rag.IndexResponded(req)│
                                        │   graph.UpdateForRequest │
                                        │   → next draft can cite  │
                                        │     THIS one             │
                                        └──────────────────────────┘
```

### Why this is "agentic", not just RAG

A pure RAG system is one-shot: retrieve → answer. We have **two LLM
agents with different jobs**, a deterministic retrieval layer between
them, **explicit gating** on the model's own confidence
(`completeness_score`), an **officer in the loop** with three meaningful
actions, and a **feedback loop** that re-indexes every approved response.

| Stage | Decides | Why it matters |
| ----- | ------- | -------------- |
| ① Structurer | Should we draft now, or is the request ambiguous? | Cheap upstream gate avoids wasted draft cycles + lets the officer triage faster. |
| ② Retriever  | What past records are relevant? | The Drafter sees only ministry-authoritative context. |
| ③ Drafter    | What is the citizen-facing wording? | Constrained by the retrieval block; instructed to cite prior RTI ids. |
| ④ Human gate | Publish, reject, or send back to citizen? | Legal accountability stays with the officer, not the model. |
| ⑤ Feedback  | Promote approved responses into the corpus. | Each approval improves future drafts (a tiny RLHF loop, but offline and free). |

### How `completeness_score` gates the workflow

The Structurer is asked to rate `completeness_score` ∈ [0, 1] for how
self-contained the citizen's request is. The handler then branches:

- `score ≥ 0.7` → retrieve + draft immediately. The officer sees an
  AI-drafted reply they can approve, edit, or reject.
- `score < 0.7` → no draft. The officer sees the structured JSON
  (`missing_information`, `suggested_response_approach`) and typically
  fires off a clarification request. The citizen replies; we re-run the
  Structurer, and the request loops back into the queue.

This is why the agent feels useful instead of noisy: ambiguous requests
are recognised as ambiguous *before* the Drafter ever runs.

---

## How we use RAG and graphify

The Drafter is grounded in **two parallel retrieval layers** over the
ministry archive (responded RTI requests + FAQs). Both are populated at
startup and refreshed on every officer approval.

### Layer 1 — RAG (TF-IDF cosine)

This is the "vector" layer. We index every responded RTI + every FAQ at
startup and re-rank on each query.

- Each document is tokenised: lowercase, 3+ chars, stopwords removed.
- Term frequencies → smoothed TF-IDF weights → L2-normalised vectors.
- `Retrieve(query, k)` = dot product against every document (cosine
  similarity since both vectors are unit-length); take top-k.

Why TF-IDF and not sentence-transformers? Two reasons:

1. **Zero dependencies, zero cold start.** No model download, no GPU,
   no Python. The retriever boots in microseconds.
2. **Government RTI text is keyword-heavy.** Words like "coral bleaching
   2023" or "Baa Atoll EIA" tend to be the actual signal. Embedding
   models add semantic recall but also add "noise neighbours" — for our
   corpus size and domain, TF-IDF is competitive and explainable.

The retrieval is good enough that the Drafter often cites the exact
prior `RTI-2024-XXXX` id its answer came from.

### Layer 2 — graphify (token-cooccurrence graph)

A pure cosine retriever misses "concept-adjacent" precedent: requests
that talk about the *same topic* with *different keywords*. The Python
implementation used the [`graphify`](https://github.com/safishamsi/graphify)
CLI to build an LLM-extracted entity/relation graph for exactly this
reason. The Go port keeps the same idea but does it deterministically
in-process so we don't need a subprocess, an LLM call, or the
graphify install.

The graph is built once at startup:

- **Nodes** are notable tokens (4+ chars, non-stopword) appearing in at
  least one document.
- **Edges** carry the co-occurrence count between two tokens within a
  document.

`Retrieve(query, k)` then does:

1. Tokenise the query → query terms get weight 1.0.
2. For each query term, take its top-8 most-cooccurring neighbours from
   the graph and give them weight 0.5.
3. Score every document by the sum of weights for the terms it contains.
4. Return the top-k documents.

This surfaces precedent the cosine retriever misses. A query about
"reef monitoring data" can match a stored RTI about "coral bleaching
surveys" because *reef* and *coral*, or *monitoring* and *survey*,
co-occur in the same document elsewhere in the archive.

> Why is this "agentic"? The graph is treated as a **second tool** the
> system uses to assemble context, complementary to TF-IDF. The Drafter
> sees both blocks side-by-side in its system prompt and is told to
> prefer them over its own world knowledge.

### How both layers feed the Drafter

`internal/ai/ai.go: answerSystemTemplate` interpolates the two retrieval
blocks directly into the system prompt:

```
MINISTRY ARCHIVE — VECTOR MATCHES:
[1] Past responded RTI · RTI-2024-0001 (filed 2024-01-20)
    Subject: Coral reef bleaching monitoring data 2023
    Description: ...
    Official response: ...

MINISTRY ARCHIVE — GRAPH-LINKED PRECEDENT:
[G1] Graph-linked RTI · RTI-2024-0005 (filed 2024-02-10)
    Subject: Environmental Impact Assessment reports ...

RULES:
- Every factual claim must come from the archive shown above.
- Cite the relevant prior RTI id (e.g. RTI-2024-0001) when you draw on it.
- 4–8 sentences, plain prose, no markdown headings.
```

The model's behaviour collapses to: "read the cited evidence, answer in
the citizen's voice, link back to the records." That's the entire AI
contract.

### The feedback loop

When the officer approves a response, the handler calls both
`rag.IndexResponded(...)` and `graph.UpdateForRequest(...)` outside the
DB lock. The new response is now retrievable for the **next** request —
the archive grows with every approval and the agent gets steadily
better at the ministry's specific style.

---

## Models we use (and why)

Two different Anthropic Claude models, picked for two different jobs.
Both are configurable via env vars
(`ANTHROPIC_MODEL`, `ANTHROPIC_STRUCTURE_MODEL`).

| Stage | Model | Used for | Why this model |
| ----- | ----- | -------- | --------------- |
| ① Structurer | **`claude-3-5-sonnet-20241022`** | Parsing the citizen's free text into a strict JSON object (`request_type`, `key_questions`, `completeness_score`, etc.) | Sonnet 3.5 is reliable at *structured* output — it returns clean JSON with the schema we specified, with very low malformed-output rate. The Structurer's job is essentially an information-extraction task; we want correctness over style, and Sonnet's JSON mode is well-suited. |
| ③ Drafter | **`claude-haiku-4-5`** | Writing the citizen-facing reply, grounded in the retrieved archive blocks | Haiku 4.5 is fast, cheap, and excellent at *grounded summarisation* — the exact shape of this task. The Drafter is constrained heavily by the system prompt ("only cite what's in the retrieval block, plain prose, 4–8 sentences"), so a smaller faster model gives the same quality at a fraction of the latency and cost. |

### Why two models and not one

A common shortcut would be to use one model for both jobs. We split for
three reasons:

1. **Different output formats.** Structurer must emit strict JSON;
   Drafter must emit prose. Mixing modes in one prompt makes both jobs
   worse.
2. **Different cost/latency profiles.** The Structurer runs on *every*
   filing (including clarification updates). The Drafter only runs when
   `completeness_score ≥ 0.7`. Splitting lets us put the cheaper, faster
   model on the hot path.
3. **Cleaner failure modes.** If the Structurer returns bad JSON, we
   fall back to a deterministic skeleton and skip drafting — the
   request still gets created. If the Drafter call fails, the request
   is filed as Pending and the officer can write a reply by hand.

### Why Anthropic Claude (and not GPT / Gemini / open-weights)?

- **Long, structured context handling.** Our system prompt for the
  Drafter includes both retrieval blocks verbatim — Claude is robust to
  long, structured prompts and follows the "only cite what's in the
  block" instruction reliably.
- **Safety posture.** Government Right to Information replies must not
  hallucinate facts. Claude's training emphasises refusing rather than
  making things up; combined with our retrieval-only grounding rule, we
  get conservative drafts.
- **No vendor lock-in.** The whole AI layer is one small Go package
  (`internal/ai/`) that talks to the Anthropic Messages REST API
  directly. Swapping to OpenAI or a local model would mean changing one
  file.

### Why we *don't* use an embedding model

Our retrieval (RAG + graphify) is implemented with TF-IDF and a
token-cooccurrence graph — both deterministic, both in-process, both
zero-dependency. We deliberately *don't* use sentence-transformers or
OpenAI embeddings here. Reasons:

- **Cold start.** No 300 MB model download, no PyTorch, no GPU. The
  retriever boots in microseconds.
- **Explainability.** When the Drafter cites `RTI-2024-0001`, we can
  show the officer exactly which keywords or co-occurring concepts
  caused it to surface — important for an audit-friendly government
  system.
- **Domain fit.** Government RTI text is keyword-heavy (place names,
  programme names, statute numbers). TF-IDF is competitive with
  embedding models in this regime and ~1000× faster.

---

## Boot sequence



When `docker compose up --build` runs:

1. **`backend-go` image** is built in two stages (golang:1.22-alpine →
   alpine:3.20). Final image is a ~15 MB static binary plus
   ca-certificates.

2. **Backend container starts** (`main.go`):
   1. Reads env (`PORT`, `DATA_FILE`, `JWT_SECRET_KEY`, `ADMIN_EMAILS`,
      `ANTHROPIC_API_KEY`, `ENABLE_DATA_PERSISTENCE`, `MAX_BACKUPS`).
   2. Ensures `data/` and `data/backups/` exist; loads
      `data/sample_data.json` into an in-memory `*models.DB`.
   3. Builds the auth service, Anthropic client, query cache.
   4. Indexes every responded RTI request + every FAQ into the TF-IDF
      `rag.Index` and the token-cooccurrence `graph.State`.
   5. Seeds the two default users (idempotently — re-creating an existing
      user is a no-op).
   6. Installs the chi router, CORS, and request-logging middleware.
   7. `http.ListenAndServe(":8000")` and waits on SIGINT/SIGTERM.

3. **Frontend container** runs the Vite dev server with HMR, proxying
   `/api` to `http://backend:8000` over the compose network.

Successful boot logs look like:

```
rti4all-backend  | [startup] seeded default user officer@gov.mv
rti4all-backend  | [startup] seeded default user citizen@example.mv
rti4all-backend  | [startup] ✓ RTI4All backend (Go) ready
rti4all-backend  | [startup]   requests=20 departments=5 faqs=10
rti4all-backend  | [startup]   RAG items=19  graph docs=19  persistence=true  ai=true
rti4all-backend  | [startup]   listening on :8000
```

---

## State model

There is exactly one source of truth: an in-memory `*models.DB` owned by
the HTTP `Server` struct. Every read goes through it; every write goes
through it. After every mutation a background goroutine snapshots it to
disk.

```go
type DB struct {
    Departments []Department
    Requests    []*RTIRequest
    FAQs        []FAQ
}
```

`RTIRequest` carries the full record (citizen profile snapshot, response,
review audit, structured analysis, clarification history, citizen
updates). `PublicRequest` is the citizen-facing projection that hides the
profile snapshot and the internal `reviewed_by` / `reviewed_at`.

Users live in a separate in-memory map inside `internal/auth`. They are
**not** persisted — restarting recreates the two default users and forgets
everyone else. (This matches the original Python implementation.)

### Persistence

`internal/persistence/persistence.go` owns the on-disk JSON store:

- **Atomic writes** — encode to `sample_data.json.tmp`, then `os.Rename`.
- **Backups** — before each save, copy the live file to
  `data/backups/sample_data_YYYYMMDD_HHMMSS.json`. Rotation keeps the most
  recent `MAX_BACKUPS` (default 10).
- **Recovery** — if JSON decode fails on the main file, the loader walks
  backups newest-first and returns the first one that parses.

---

## HTTP API

All endpoints are versionless and JSON in / JSON out. Auth is bearer JWT
issued by `/api/auth/login` or `/api/auth/signup`. Sessions are 24 hours.

```
GET    /api/health                     → 200 {"status":"ok"}            (public)

POST   /api/auth/signup                → 201 {access_token,user}        (public)
POST   /api/auth/login                 → 200 {access_token,user}        (public)
GET    /api/auth/me                    → 200 UserPublic                 (auth)

GET    /api/departments                → 200 [Department]               (public)
GET    /api/departments/{id}           → 200 Department | 404
GET    /api/faqs                       → 200 [FAQ]                      (public)
GET    /api/stats                      → 200 status counts + totals     (public)

GET    /api/requests                   → 200 [PublicRequest]            (auth)
POST   /api/requests                   → 201 RTIRequest                 (auth)
GET    /api/requests/{id}              → 200 PublicRequest | 403 | 404  (auth)
PATCH  /api/requests/{id}/clarify      → 200 PublicRequest              (auth, owner-only)

GET    /api/admin/requests/pending     → 200 [RTIRequest]               (admin)
GET    /api/admin/requests/{id}        → 200 RTIRequest                 (admin)
PATCH  /api/admin/requests/{id}        → 200 RTIRequest                 (admin)
```

### Auth model

- bcrypt password hashes (`golang.org/x/crypto/bcrypt`).
- HS256 JWT with `JWT_SECRET_KEY` (`golang-jwt/jwt/v5`).
- Claims: `sub` (email), `name`, `is_admin`, `iat`, `exp`.
- `ADMIN_EMAILS` (comma-separated) decides who gets `is_admin=true`.
  Checked at signup and re-checked at login (adding a user to the list
  later promotes them on next sign-in).
- Two chi middlewares wrap protected routes:
  - `RequireAuth` → 401 if the bearer is missing / invalid.
  - `RequireAdmin` → 401, then 403 if the bearer is valid but not admin.

### Citizen authorisation

`/api/requests` returns only the caller's own requests, unless the caller
is admin (then it returns everything). `GET /api/requests/{id}` 403s if
the caller doesn't own the record (admins bypass).
`PATCH /api/requests/{id}/clarify` is owner-only — admins can't
impersonate a citizen on the clarification reply.

---

## Request lifecycle

### 1. Citizen files a request

Frontend `NewRequestPage` POSTs to `/api/requests`:

```json
{ "department_id": "moccee",
  "subject": "How do I file a follow-up RTI?",
  "description": "I would like a brief explanation of the procedure..." }
```

`handlers.createRequest`:

1. Reads the authenticated user from the request context.
2. Validates inputs and resolves the department name.
3. Generates the next sequential id: `RTI-<year>-NNNN`.
4. **Structures the request** via `ai.ProcessRequestStructure`, which asks
   Claude Sonnet for a JSON object with `request_type`, `key_questions`,
   `information_sought`, `time_period`, `geographic_scope`,
   `urgency_indicators`, `completeness_score`, `missing_information`,
   `related_policies`, `estimated_complexity`,
   `suggested_response_approach`, `relevant_precedents`. If the call
   fails, a deterministic fallback is returned so the rest of the flow
   still works.
5. **Decides whether to draft now**:
   - `completeness_score >= 0.7` → call `generateAnswer` to produce a
     citizen-facing draft; status `Under Review`.
   - Otherwise → leave `response = ""`, status `Under Review`. The
     officer reads the analysis and asks for clarification.
6. **Drafting** is two-step:
   1. **Cache** — `cache.MakeKey(department_id, subject, description)`
      normalises the text and looks for a prior identical draft.
   2. **Retrieve + draft** —
      - `rag.Index.Retrieve(query, 4)` for top-4 TF-IDF matches.
      - `graph.State.Retrieve(query, 7)` for top-7 graph-linked items.
      - Dedupe graph hits against vector hits by `id`, keep 3.
      - Build a system prompt with both blocks; ask Claude Haiku for a
        4–8 sentence reply citing prior RTI ids.
7. Append to `db.Requests`, persist in the background, return to the
   citizen.

### 2. Citizen sees their request

`RequestDetailPage` GETs `/api/requests/{id}` and renders the
`PublicRequest`. If status is `Under Review` and a draft exists, a
purple "Draft Response · Pending Officer Review" card is shown with a
disclaimer.

### 3. Officer reviews

The officer logs in (admin token issued because their email is in
`ADMIN_EMAILS`), opens the admin inbox at `/admin`, which GETs
`/api/admin/requests/pending`. They click into a row and see the full
record on `/api/admin/requests/{id}` — citizen profile, AI analysis, AI
draft.

Three actions:

#### a) Approve

PATCH `{ response, status: "Responded" }`. The handler updates the
record, stamps `reviewed_by` / `reviewed_at`, **and** snapshots the
request to update the RAG index + token-cooccurrence graph. Every
approval enriches the corpus available to future drafts.

#### b) Reject

PATCH `{ status: "Rejected", rejection_reason }`. Same audit stamping, no
index update.

#### c) Request clarification

PATCH `{ request_clarification: { message, missing_fields, questions,
suggested_improvements } }`. Appends to `clarification_history`, sets
`clarification_requested`, status flips to `Clarification Needed`.

### 4. Citizen answers clarification

`PATCH /api/requests/{id}/clarify` with updated description, additional
info, and answers-to-questions. The handler:

1. 403s unless the caller owns the request.
2. 400s unless current status is `Clarification Needed`.
3. Appends to `citizen_updates`, updates the description if a new one was
   supplied, clears `clarification_requested`, flips status back to
   `Under Review`.
4. Re-runs `ProcessRequestStructure` so the officer sees a refreshed
   analysis.

---

## Frontend ↔ backend mapping


| Page                       | Endpoints                                                                |
| -------------------------- | ------------------------------------------------------------------------- |
| `HomePage`                 | `GET /api/stats`                                                          |
| `LoginPage` / `SignupPage` | `POST /api/auth/login`, `POST /api/auth/signup`                           |
| `RequestsPage`             | `GET /api/requests`                                                       |
| `RequestDetailPage`        | `GET /api/requests/{id}`, `PATCH /api/requests/{id}/clarify`              |
| `NewRequestPage`           | `GET /api/departments`, `POST /api/requests`                              |
| `DepartmentsPage`          | `GET /api/departments`                                                    |
| `FaqsPage`                 | `GET /api/faqs`                                                           |
| `AdminInboxPage`           | `GET /api/admin/requests/pending`                                         |
| `AdminReviewPage`          | `GET /api/admin/requests/{id}`, `PATCH /api/admin/requests/{id}`          |

Auth is stored in `localStorage` under `rti4all-auth`. The api client
fires a `rti4all:unauthorized` event on any 401, which `AuthProvider`
listens for and uses to clear the token + redirect to login.

---

## Design system

The SPA leans into a **minimalist, mostly-monochrome** aesthetic — the
intent is for the page to read as a calm grayscale by default, with a
single blue accent reserved for primary CTAs, focus rings, and the brand
mark.

- **Palette**:
  - `ink-50…950` — neutral grayscale for backgrounds, borders, text
    (zinc-ish).
  - `accent-50…900` — saturated blue, used sparingly.
  - Status pills (`StatusBadge`) carry small coloured dots
    (emerald / violet / amber / red / blue) inside a neutral chip so
    statuses read at a glance without breaking the monochrome page.
- **Typography**: Inter from `rsms.me`, system fallback. Tight tracking
  on headings (`tracking-tight`).
- **Elevation**: a single soft `shadow-card`. No drop-shadow drama.
- **Focus**: 3px blue glow, no outline. Subtle and accessible.

The UI kit (`frontend/src/components/ui.tsx`) is tiny on purpose: `Card`,
`Button`, `LinkButton`, `Input`, `Select`, `Textarea`, `Field`,
`StatusBadge`, `Spinner`, `EmptyState`, `ErrorBanner`, `PageHeader`,
`Container`. No radix, no shadcn — the surface area is small enough that
hand-rolled primitives are simpler to maintain.

---

## Environment configuration

`.env` is loaded by docker compose via `env_file:`. All variables have
safe defaults so the stack boots without one.

| Variable                    | Used by                | Default                       |
| --------------------------- | ---------------------- | ----------------------------- |
| `PORT`                      | backend                | `8000`                        |
| `DATA_FILE`                 | backend                | `data/sample_data.json`       |
| `JWT_SECRET_KEY`            | backend / auth         | dev fallback (insecure)       |
| `ADMIN_EMAILS`              | backend / auth         | empty                         |
| `ANTHROPIC_API_KEY`         | backend / ai           | empty (stub responses)        |
| `ANTHROPIC_MODEL`           | backend / ai (draft)   | `claude-haiku-4-5`            |
| `ANTHROPIC_STRUCTURE_MODEL` | backend / ai (JSON)    | `claude-3-5-sonnet-20241022`  |
| `ENABLE_DATA_PERSISTENCE`   | backend                | `true`                        |
| `MAX_BACKUPS`               | backend                | `10`                          |
| `VITE_API_TARGET`           | frontend (local dev)   | `http://backend:8000`         |

If `ANTHROPIC_API_KEY` is unset, the AI step returns a clearly-labelled
stub response — the rest of the workflow still functions, useful for
offline development.

---

## Failure modes and how they're handled

| Failure                                       | Behaviour                                                                                |
| --------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Anthropic API down / quota hit                | `AnswerRequest` returns an error → request still filed with `status="Pending"`, no draft. |
| Anthropic returns bad JSON                    | `ProcessRequestStructure` falls back to a deterministic skeleton; request still created. |
| `sample_data.json` corrupted                  | Loader walks `data/backups/` newest-first and returns the first that parses.             |
| Persistence write fails                       | Logged; the in-memory DB still has the change (so the response succeeds).                |
| Token expired / revoked                       | Backend returns 401; api client fires `rti4all:unauthorized` → AuthProvider clears local state. |
| Non-admin hits `/admin/*`                     | 403 `Administrator access required.`                                                     |
| Citizen tries to read someone else's request  | 403 `You do not have permission to access this request.`                                 |
| Citizen tries to clarify outside the workflow | 400 `No clarification has been requested for this request.`                              |

---

## What was replaced from the Python implementation

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

The HTTP contract is identical, so the React frontend was rewritten in
TypeScript + Tailwind without any API-shape changes.

---

## Mental model — one diagram

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
│ retrieval (TF-IDF + token    │
│ cooccurrence graph) over the │
│ ministry archive             │
└──────────────────────────────┘
```

That's the whole system.

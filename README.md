# RTI4All — Ministry of Climate Change, Environment and Energy

**Colab26 Hackathon — Team 9**

A citizen-facing portal + ministry admin panel for filing and reviewing **Right to Information (RTI)** requests with the Maldives [Ministry of Climate Change, Environment and Energy](https://environment.gov.mv). Citizens file requests; an AI assistant drafts a response from official sources; a ministry officer approves, edits, or rejects the draft before it becomes the official record (human-in-the-loop).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite (JavaScript) |
| Backend | Python 3.11 + FastAPI |
| AI | Anthropic Claude Haiku 4.5 with server-side `web_search` + `web_fetch` |
| RAG | Two-layer: vector (`sentence-transformers` + numpy cosine) + knowledge graph ([graphify](https://github.com/safishamsi/graphify)) |
| Auth | JWT (HS256) via `python-jose`, bcrypt password hashing via `passlib` |
| Data | In-memory sample JSON + in-memory user store (no database) |
| Container | Docker + Docker Compose |
| Tests | pytest + FastAPI `TestClient` |

---

## How It Works

### The citizen flow

1. **Sign up** at `/signup` with name, email, phone, present address, and an optional national ID card number. Password is bcrypt-hashed server-side. Email is the unique account identifier (case-insensitive).
2. **Sign in** and visit **File RTI** at `/requests/new`. The form pre-selects the only available department (the ministry); the citizen's identity is shown as a read-only "Filing as ..." header.
3. **Submit a request** (subject + description). The backend kicks off the AI step and returns a record in status `Under Review`.
4. **Track it** at `/requests/{id}`. While `Under Review`, the citizen sees the AI draft inside a purple **"Pending Officer Review"** card. Once an officer acts, the same page shows either a green **"Official Response"** card or a red **"Request Rejected"** card with the officer's reason.

### The AI drafting step

When a citizen submits a request via `POST /api/requests`:

1. **Cache lookup.** A normalized key is built from the request text (lowercased, punctuation stripped, whitespace collapsed). If a previous request produced a draft for the same normalized text, that draft is reused — no LLM call. Cache hit: ~15 ms.
2. **RAG retrieval.** The query (subject + description) is embedded and the top-k items are pulled from the in-memory vector index over the ministry's local archive — past responded RTIs (precedent) + standing FAQs (process knowledge). See "The RAG pipeline" below.
3. **LLM call.** Claude Haiku 4.5 is invoked with the retrieved archive items injected into the system prompt **and** server-side `web_search` + `web_fetch` tools restricted via `allowed_domains` to two sources, queried in strict priority order:
   1. **`rtidhonbe.com`** — the RTI vault (preferred).
   2. **`environment.gov.mv`** — the ministry's official site (fallback, only if the vault doesn't have it).
4. **Drafting.** Claude prefers archive precedent when it directly answers the question, otherwise grounds the response in web-retrieved content. Cites the source(s) it used (a prior RTI id, a FAQ id, or the domain it fetched). Cache miss: typically 15–30 s end-to-end.
5. **Storage.** The request is saved with `status: "Under Review"`, the draft in the `response` field, and the citizen's profile snapshotted onto the record (`citizen_phone`, `citizen_address`, `citizen_id_card`).
6. **AI failure fallback.** If the LLM call errors out (network, quota), the request is filed as `Pending` with no draft — the officer can author a response by hand from the admin panel.

The AI is instructed never to invent figures, names, dates, or document references. If neither source has the answer, it says so plainly and directs the citizen to file a formal RTI application.

### The RAG pipeline

Two complementary retrieval layers feed the system prompt. Both ground drafts in the ministry's own archive before the LLM looks at any live web source.

**Layer 1 — Vector RAG (semantic similarity)**

- **Corpus**: built at startup from `data/sample_data.json`. Each **responded** RTI request becomes one chunk (`subject + description + official response`); each FAQ becomes one chunk (`question + answer`). Pending / Under Review / Rejected requests are excluded — only items that survived officer approval are treated as precedent.
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (≈90 MB, CPU-only), pre-downloaded into the Docker image. No external embedding API used.
- **Index**: single in-memory `numpy.float32` matrix of L2-normalized vectors. Plain dot-product cosine retrieval over the whole matrix.
- **Retrieval**: top-4 hits formatted as `MINISTRY ARCHIVE — VECTOR MATCHES:` in the system prompt.
- **Feedback loop**: when an officer **approves** a request, `index_responded_request(...)` adds the (possibly edited) final response to the index for future retrievals.

Swapping the embedder is a one-line change — `RAGIndex` takes any object that implements `embed(texts: list[str]) -> np.ndarray` (L2-normalized). Tests use a deterministic `BagOfWordsEmbedder` so they don't load PyTorch.

**Layer 2 — Knowledge graph via graphify**

A graph-augmented layer that finds precedent through *shared entities* — useful when a new request mentions the same project, atoll, or programme as a past one, even if the vector embeddings don't quite line up.

- **Builder**: [`graphify`](https://github.com/safishamsi/graphify) (PyPI `graphifyy`). Each chunk is exported as a markdown file; `graphify extract --backend claude` runs an LLM-driven entity-and-relationship extraction over the corpus and produces `graph.json` (nodes = entities, edges = relations like `references`, `located_in`, `mentions`).
- **Persistence — the compute-savings story**: `graph.json` is written to `backend/.rag_cache/corpus/graphify-out/` and reused on restart. The LLM extraction cost is paid **once per piece of content**, never per query and never per restart. A typical seed corpus (≈10 chunks) costs ≈ \$0.15 to extract initially; subsequent cache hits are free. Per-file extraction cache (`graphify-out/cache/`) means re-running `graphify extract` on the same corpus skips unchanged files.
- **Retriever**: `GraphRetriever` loads `graph.json` in-process. For a query, it tokenises against node `label`s, takes top label-matched seed nodes, does 1-hop edge traversal, then groups reached nodes by `source_file` to rank chunks. **No subprocess at query time**.
- **Retrieval**: top-3 hits (deduped against the vector hits by id) formatted as `MINISTRY ARCHIVE — GRAPH-LINKED PRECEDENT:` in the system prompt.
- **Feedback loop**: when an officer approves a request, the new markdown file is written to the corpus dir and `graphify extract` is invoked again. Graphify's per-file cache means only the new file pays the LLM cost — typically a single chunk, ≈ \$0.01.
- **First-run cost** on the seed corpus: ≈ \$0.15 in Anthropic tokens, observed in CI; subsequent container starts are free thanks to the cache.

Tests stub the `graphify extract` subprocess so the suite runs fast (≈8 s for 46 tests) and never burns LLM tokens. The `GraphRetriever` itself is unit-tested against fixture `graph.json` files.

### The admin (human-in-the-loop) review

Officers are bootstrapped via the `ADMIN_EMAILS` env var (comma-separated). When a user with a matching email signs up or logs in, their JWT carries `is_admin: true` and the navbar exposes a purple **Admin** link.

- **`/admin`** — Inbox of all `Under Review` requests, oldest first.
- **`/admin/requests/{id}`** — Full review view:
  - **Citizen profile card** — snapshot of name, email, phone, present address, ID card at filing time.
  - **Filing card** — department, dates, and the review audit trail (`reviewed_by`, `reviewed_at`).
  - **Original RTI** — the subject + description as written.
  - **AI Draft Response (editable)** — a textarea pre-filled with the AI's draft.
  - **Rejection Reason** — used by the Reject action.
  - **Three actions:** **Save Draft** (keep `Under Review`), **Reject** (status → `Rejected`, requires a non-empty reason), **Approve & Publish** (status → `Responded`, uses the edited draft text). Any action stamps `reviewed_by` (the officer's email) and `reviewed_at`.

### Example AI draft

A real request for *"current installed renewable energy capacity and national targets"* returned:

> Based on the Ministry's published Energy Policy and Strategy 2024–2029, the Maldives has an installed electricity capacity of 600 MW, of which 68.5 MW comes from solar PV (~6% of national consumption). At COP28 the government committed to sourcing 33% of national electricity from renewables by 2028. The RTI vault did not have this information; it was retrieved from environment.gov.mv.

---

## Auth & Privacy Model

- **Citizen-facing endpoints** (signup, login, public GETs) are open to anyone. Filing a request requires a bearer token.
- **Admin endpoints** (`/api/admin/*`) require the JWT to carry `is_admin: true` — otherwise 403.
- **JWT identity override** — `POST /api/requests` ignores any `citizen_name` / `email` an attacker tries to slip into the body. Both are taken from the authenticated user. Profile snapshot fields (phone, address, ID card) are also pulled from the user record, not the payload.
- **Privacy-scoped public projection** — `GET /api/requests` and `GET /api/requests/{id}` return `PublicRTIRequest`, which omits the profile snapshot (`citizen_phone`, `citizen_address`, `citizen_id_card`) and the review audit fields (`reviewed_by`, `reviewed_at`). The full record is only exposed through admin endpoints.
- **Token expiry** — 24 hours, HS256. Secret is `JWT_SECRET_KEY`; missing → an insecure dev fallback is used (with a startup warning).

### Signup profile

| Field | Required | Notes |
|---|---|---|
| Name (`full_name`) | ✅ | Used as the citizen name on filed RTI requests |
| Email | ✅ | Unique account identifier; normalized to lowercase |
| Phone number | ✅ | Free-form string (e.g. `+960 7771234`) |
| Present address | ✅ | Free-form string |
| ID card | — | Optional national ID number |
| Password | ✅ | Minimum 8 characters; bcrypt-hashed |

Whitespace-only values are rejected by the server. The full profile is returned on `/api/auth/me`.

---

## Project Structure

```
RTI4All/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI app: routes, citizen + admin endpoints
│   ├── ai.py                 # Claude call: RAG retrieval + web_search/web_fetch
│   ├── auth.py               # JWT + bcrypt + admin bootstrap + user store
│   ├── cache.py              # In-memory normalized-text query cache
│   ├── rag.py                # Vector index — embedder + numpy cosine + DB helpers
│   ├── graph.py              # graphify integration — corpus export, subprocess, GraphRetriever
│   ├── data/
│   │   └── sample_data.json  # The ministry + seed requests + FAQs
│   └── tests/
│       ├── conftest.py       # Shared fixture: stubbed AI, BagOfWords embedder, stubbed graphify
│       ├── test_auth.py      # Auth flow coverage (15 tests)
│       ├── test_admin.py     # Admin workflow coverage (12 tests)
│       ├── test_rag.py       # Vector RAG coverage (10 tests)
│       └── test_graph.py     # graphify retriever coverage (9 tests)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx           # All pages, routing, AuthProvider, Require* gates
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- (Optional but recommended) An Anthropic API key with web-tools access. Without one, the AI step returns a clearly-labelled stub message.

### Configure environment

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and configure the following variables:

```bash
ANTHROPIC_API_KEY=sk-ant-...                         # Your Anthropic API key
JWT_SECRET_KEY=$(openssl rand -hex 32)               # Any high-entropy secret
ADMIN_EMAILS=officer@gov.mv,supervisor@gov.mv        # Ministry officers
```

**Important notes:**

- `ANTHROPIC_API_KEY` unset → AI step returns a stub; everything else still works.
- `JWT_SECRET_KEY` unset → backend logs a warning and uses an insecure dev fallback. **Never run that in production.**
- `ADMIN_EMAILS` unset → no admins exist, so the admin panel is inaccessible. Matching is case-insensitive against the email used at signup, and is re-checked at login so adding emails after a user signed up retrofits them on next login.

**Admin Setup:**
When a user signs up with an email listed in `ADMIN_EMAILS` (e.g., `officer@gov.mv`), they will automatically:
- Receive admin privileges (`is_admin: true`)
- Be redirected to the admin panel (`/admin`) instead of the citizen request form
- Have access to review, approve, edit, and reject RTI requests

### Run

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

Stop with `docker compose down`.

### Run the test suite

```bash
docker exec rti4all-backend python -m pytest tests/ -v
```

**46 tests, all external work stubbed** (no Anthropic quota burned, no model load, no graphify subprocess):

- **`test_auth.py` — 15 tests.** Signup success / duplicate-email / invalid-email / missing required profile field / optional `id_card` omitted / whitespace-only rejected; login with valid / wrong-password / unknown-email; `POST /api/requests` protection (no token / malformed / valid); JWT identity override (server discards attacker-supplied `citizen_name` / `email`); `/auth/me` returns full profile; public reads remain open.
- **`test_admin.py` — 12 tests.** `ADMIN_EMAILS` bootstraps `is_admin` at signup, non-admin emails aren't promoted, flag surfaces on `/auth/me`; admin endpoints reject unauthenticated and non-admin tokens; new requests land in `Under Review` with profile snapshotted; inbox lists pending; admin can edit + approve (stamps reviewer + timestamp); admin can reject with reason; empty PATCH and invalid status rejected; PATCH on unknown ID → 404.
- **`test_rag.py` — 10 tests.** Stubbed `BagOfWordsEmbedder` is deterministic, normalized, and ranks similar texts higher than unrelated ones; `RAGIndex.upsert` / `retrieve` returns top-k by cosine; upsert replaces by id; empty / blank queries are handled; `populate_from_db` loads only responded requests + all FAQs; startup seeds the index; admin **approval** adds the request (and a marker phrase becomes retrievable); admin **rejection** does not add to the index.
- **`test_graph.py` — 9 tests.** `export_corpus` writes one markdown per responded RTI and per FAQ; `export_single_request` rejects non-responded items; `GraphRetriever` finds documents by label match, traverses 1-hop edges to neighbour-linked source files, returns empty when no labels match, and handles a missing `graph.json` gracefully; startup creates the graph state via the stubbed subprocess; admin **approval** invokes `run_graphify_extract` and writes a new corpus file; admin **rejection** does **not** invoke it.

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | — | Health check |
| POST | `/api/auth/signup` | — | Create an account; returns `{access_token, user}` |
| POST | `/api/auth/login` | — | Authenticate; returns `{access_token, user}` |
| GET | `/api/auth/me` | **Bearer** | Return the currently signed-in user (incl. `is_admin`) |
| GET | `/api/requests` | — | List all RTI requests (filter by `status`, `department_id`). Privacy-scoped projection |
| GET | `/api/requests/{id}` | — | Get a single RTI request. Privacy-scoped projection |
| POST | `/api/requests` | **Bearer** | File a new RTI request. Triggers cache lookup or live AI retrieval. Citizen identity + profile snapshot come from the JWT, not the body |
| GET | `/api/admin/requests/pending` | **Admin** | Inbox of `Under Review` requests, oldest first. Full record |
| GET | `/api/admin/requests/{id}` | **Admin** | Single request, full record (profile snapshot + audit fields) |
| PATCH | `/api/admin/requests/{id}` | **Admin** | Edit response, change status, set rejection reason. Stamps `reviewed_by` + `reviewed_at` |
| GET | `/api/departments` | — | List departments (a single entry: the ministry) |
| GET | `/api/departments/{id}` | — | Get a single department |
| GET | `/api/faqs` | — | List all FAQs |
| GET | `/api/stats` | — | Summary stats: `total_requests`, `pending`, `in_progress`, `under_review`, `responded`, `rejected`, `total_departments` |

Send tokens as `Authorization: Bearer <token>`. **Admin** rows additionally require `is_admin: true` in the JWT — non-admin tokens get 403.

### Status values

| Status | When |
|---|---|
| `Pending` | AI step failed; awaits human authoring |
| `In Progress` | Legacy / seeded only — never set by the live flow |
| `Under Review` | AI draft prepared; awaiting officer approval |
| `Responded` | Officer approved (possibly after editing the draft) |
| `Rejected` | Officer rejected — `rejection_reason` is populated |

---

## Implementation Notes

- **Single-ministry mode.** Only one department exists (`moccee`). The File RTI form auto-fills the department and shows it as a read-only chip instead of a dropdown.
- **Caching.** Exact normalized match (lowercase, stripped punctuation, collapsed whitespace) keyed on `(department_id, subject + description)`. Identical re-submissions reuse the prior draft instantly. Paraphrases are treated as new and incur a fresh AI call.
- **Why `allowed_callers=["direct"]` on the web tools.** Haiku 4.5 doesn't support the dynamic-filtering / programmatic-tool-calling mode that the `_20260209` web tools default to — `direct` puts them in the classic tool-use loop that Haiku supports.
- **Final-block extraction.** Only the text Claude emits *after* the last tool-use block in the response is returned to the citizen. Intermediate "I'll search..." narration emitted between tool rounds is filtered out so it doesn't leak into the citizen-facing response.
- **Vite proxy.** The dev server proxies all `/api/*` to the backend container, so the browser never makes cross-origin requests.

---

## Limitations

- **Cache is exact-match.** Paraphrased queries don't dedupe — *"plastic ban enforcement 2024"* and *"single-use plastic enforcement actions in 2024"* will each call the AI. (The RAG layer **does** match paraphrases, but only for retrieving precedent; it doesn't short-circuit the LLM call.)
- **RAG corpus is small.** With one ministry's mock data, the archive starts at 10 chunks (3 responded RTIs + 7 FAQs) and grows by one per officer approval. Retrieval quality scales with the corpus — for production, seed both layers with real ministry RTI history and longer policy documents.
- **graphify first-build cost.** The first container start with an empty `.rag_cache/` runs `graphify extract` on the seed corpus — ≈ \$0.15 in Anthropic tokens and ≈ 20–30 s of wall time. Every subsequent start (or container restart with the cache volume preserved) is free. Per-approval updates pay for ≈ 1 file each (~\$0.01).
- **Two sources only.** The model is hard-walled to `rtidhonbe.com` and `environment.gov.mv`. If neither has the information, the response directs the citizen to file a formal RTI application.
- **Latency on cache miss** is dominated by real web round-trips (15–30 s typical, longer for complex queries).
- **Restart wipes state.** Users, filed requests, and the query cache all live in process memory — no database, no disk persistence. Re-bootstrap by signing up again.
- **Web tools billed separately.** `web_search` and `web_fetch` are server-side Anthropic tools and count against your Anthropic web-tool quota independently from input/output tokens.

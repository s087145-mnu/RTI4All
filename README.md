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
2. **Live retrieval (cache miss).** Claude Haiku 4.5 is invoked with `web_search` + `web_fetch` restricted via `allowed_domains` to two sources, queried in strict priority order:
   1. **`rtidhonbe.com`** — the RTI vault (preferred).
   2. **`environment.gov.mv`** — the ministry's official site (fallback, only if the vault doesn't have it).
3. **Drafting.** Claude composes a response grounded in retrieved content, cites which source it used, and tells the citizen the next step if neither source has the answer. Cache miss: typically 15–30 s end-to-end.
4. **Storage.** The request is saved with `status: "Under Review"`, the draft in the `response` field, and the citizen's profile snapshotted onto the record (`citizen_phone`, `citizen_address`, `citizen_id_card`).
5. **AI failure fallback.** If the LLM call errors out (network, quota), the request is filed as `Pending` with no draft — the officer can author a response by hand from the admin panel.

The AI is instructed never to invent figures, names, dates, or document references. If neither source has the answer, it says so plainly and directs the citizen to file a formal RTI application.

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
│   ├── ai.py                 # Claude call with web_search / web_fetch
│   ├── auth.py               # JWT + bcrypt + admin bootstrap + user store
│   ├── cache.py              # In-memory normalized-text query cache
│   ├── data/
│   │   └── sample_data.json  # The ministry + seed requests + FAQs
│   └── tests/
│       ├── conftest.py       # Shared TestClient fixture (stubbed AI)
│       ├── test_auth.py      # Auth flow coverage (15 tests)
│       └── test_admin.py     # Admin workflow coverage (12 tests)
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

Export these in your shell before `docker compose up`. Compose forwards them into the backend container automatically.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JWT_SECRET_KEY=$(openssl rand -hex 32)        # any high-entropy secret
export ADMIN_EMAILS=officer@gov.mv,supervisor@gov.mv # ministry officers
```

- `ANTHROPIC_API_KEY` unset → AI step returns a stub; everything else still works.
- `JWT_SECRET_KEY` unset → backend logs a warning and uses an insecure dev fallback. **Never run that in production.**
- `ADMIN_EMAILS` unset → no admins exist, so the admin panel is inaccessible. Matching is case-insensitive against the email used at signup, and is re-checked at login so adding emails after a user signed up retrofits them on next login.

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

**27 tests, AI step stubbed** (no Anthropic quota burned):

- **`test_auth.py` — 15 tests.** Signup success / duplicate-email / invalid-email / missing required profile field / optional `id_card` omitted / whitespace-only rejected; login with valid / wrong-password / unknown-email; `POST /api/requests` protection (no token / malformed / valid); JWT identity override (server discards attacker-supplied `citizen_name` / `email`); `/auth/me` returns full profile; public reads remain open.
- **`test_admin.py` — 12 tests.** `ADMIN_EMAILS` bootstraps `is_admin` at signup, non-admin emails aren't promoted, flag surfaces on `/auth/me`; admin endpoints reject unauthenticated and non-admin tokens; new requests land in `Under Review` with profile snapshotted; inbox lists pending; admin can edit + approve (stamps reviewer + timestamp); admin can reject with reason; empty PATCH and invalid status rejected; PATCH on unknown ID → 404.

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

- **Cache is exact-match.** Paraphrased queries don't dedupe — *"plastic ban enforcement 2024"* and *"single-use plastic enforcement actions in 2024"* will each call the AI.
- **Two sources only.** The model is hard-walled to `rtidhonbe.com` and `environment.gov.mv`. If neither has the information, the response directs the citizen to file a formal RTI application.
- **Latency on cache miss** is dominated by real web round-trips (15–30 s typical, longer for complex queries).
- **Restart wipes state.** Users, filed requests, and the query cache all live in process memory — no database, no disk persistence. Re-bootstrap by signing up again.
- **Web tools billed separately.** `web_search` and `web_fetch` are server-side Anthropic tools and count against your Anthropic web-tool quota independently from input/output tokens.

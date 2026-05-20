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

## How a Request Is Answered

When a citizen submits a request via `POST /api/requests`, the backend runs the following flow:

1. **Cache lookup.** A normalized key is built from the request text (`subject + description`, lowercased, punctuation stripped). If a previous request produced a draft for the same normalized text, that draft is reused — no LLM call.
2. **Live retrieval (cache miss).** The AI step calls Claude Haiku 4.5 with web tools restricted to two domains, in strict priority order:
   1. **`rtidhonbe.com`** — the RTI vault (preferred source).
   2. **`environment.gov.mv`** — the ministry's official site (fallback, only used if the vault doesn't have the requested information).
3. **Drafting.** Claude composes a response grounded in the content it retrieved, cites which source it used, and tells the citizen the next step if neither source has the answer.
4. **Human review.** The request is saved with `status: "Under Review"` and the AI-generated draft in the `response` field. It now sits in the **admin inbox** awaiting a ministry officer's decision: approve as-is, edit-and-approve, or reject with a reason.
5. **Officer action.** When the officer approves, status flips to `Responded` and the (possibly edited) text becomes the official response. Rejection sets status to `Rejected` and records the reason. Either action stamps `reviewed_by` + `reviewed_at` on the record.

If the AI step fails (network, API error, etc.), the request is filed as `Pending` (no draft, no review state) so the citizen can still track it; the officer can then author a response by hand from the admin panel.

**Authentication.** Filing an RTI request requires being signed in. The portal exposes a small JWT auth flow: sign up with a profile (see below), receive a bearer token, attach it to the `POST /api/requests` call. The citizen's name and email on the created record are taken from the JWT identity — they're not in the request payload, so a logged-in user can't file under someone else's name. Public reads (`GET /api/requests`, departments, FAQs, stats) remain open so anonymous browsing still works.

**Signup profile.** The signup form collects:

| Field | Required | Notes |
|---|---|---|
| Name (`full_name`) | ✅ | Used as the citizen name on filed RTI requests |
| Email | ✅ | Used as the unique account identifier; normalized to lowercase |
| Phone number | ✅ | Free-form string (e.g. `+960 7771234`) |
| Present address | ✅ | Free-form string |
| ID card | — | Optional national ID number |
| Password | ✅ | Minimum 8 characters; bcrypt-hashed on the server |

Whitespace-only values are rejected by the server. The full profile is returned on `/api/auth/me`.

**Admin panel.** A user becomes a ministry officer (admin) when their email is listed in the `ADMIN_EMAILS` env var (comma-separated). Matching users get `is_admin: true` on signup or login, the JWT carries the admin claim, and the navbar exposes an **Admin** link.

The admin UI lives at `/admin`:

- **`/admin`** — Inbox of requests in `Under Review`, oldest first.
- **`/admin/requests/{id}`** — Full review view: citizen profile snapshot (name, email, phone, address, ID card), the original RTI question, an editable AI draft, a rejection-reason field, and three actions: **Save Draft** (keep status as Under Review), **Reject** (status → Rejected, requires a reason), **Approve & Publish** (status → Responded, uses the edited draft).

Non-admin tokens are rejected from all `/api/admin/*` endpoints with a 403. The full record (including the citizen profile snapshot and the review audit fields `reviewed_by` / `reviewed_at`) is exposed **only** on admin endpoints; the public GET endpoints return a privacy-scoped projection (`PublicRTIRequest`) that omits the profile snapshot and audit fields.

**Expected latency.** A cache miss takes roughly **15–30 seconds** end-to-end — the model runs several rounds of `web_search` and `web_fetch` against the two domains before drafting. A cache hit returns in **~15 ms**.

### Example response shape

A real request for *"current installed renewable energy capacity and national targets"* returns content like:

> Based on the Ministry's published Energy Policy and Strategy 2024–2029, the Maldives has an installed electricity capacity of 600 MW, of which 68.5 MW comes from solar PV (~6% of national consumption). At COP28 the government committed to sourcing 33% of national electricity from renewables by 2028. The RTI vault did not have this information; it was retrieved from environment.gov.mv.

Where neither source has the answer, the model says so plainly and directs the citizen to file a formal RTI application with the ministry's Information Officer.

---

## Project Structure

```
RTI4All/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI application + routes
│   ├── ai.py                 # Claude call with web_search / web_fetch
│   ├── auth.py               # JWT + bcrypt + in-memory user store
│   ├── cache.py              # In-memory normalized-text query cache
│   ├── data/
│   │   └── sample_data.json  # One ministry + sample requests + FAQs
│   └── tests/
│       ├── conftest.py       # Shared TestClient fixture (stubbed AI, no admins)
│       ├── test_auth.py      # Pytest coverage of the auth flow (15 tests)
│       └── test_admin.py     # Pytest coverage of the admin workflow (12 tests)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx           # Pages + routing + AuthProvider / RequireAuth
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- (Optional but recommended) An Anthropic API key with web-tools access — without one, the AI step falls back to a stub message

### Configure the AI key, JWT secret, and admin emails

Export these before `docker compose up`. Compose passes them through to the backend container automatically.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JWT_SECRET_KEY=$(openssl rand -hex 32)   # or any high-entropy secret
export ADMIN_EMAILS=officer@gov.mv,supervisor@gov.mv  # ministry officers
```

`JWT_SECRET_KEY` unset → the backend logs a warning and uses an insecure dev fallback (never run that in production). `ADMIN_EMAILS` unset → no admins exist, so the admin panel is inaccessible until you set it. Emails are matched case-insensitively against the email used at signup.

### Run with Docker Compose

```bash
# From the project root
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

### Stop

```bash
docker compose down
```

### Run the test suite

The backend test suite covers the JWT auth flow end-to-end. Run it inside the backend container:

```bash
docker exec rti4all-backend python -m pytest tests/ -v
```

The 27 tests cover:

- **Auth (`test_auth.py`):** signup success, duplicate-email rejection, invalid-email rejection, missing required profile fields rejected, optional `id_card` omitted accepted, whitespace-only required fields rejected; login with valid credentials / wrong password / unknown user; `POST /api/requests` protection (no token, malformed token, valid token); JWT identity override (server overwrites any `citizen_name`/`email` attacker tries to slip in); `/auth/me` returns the full profile; public reads remain open.
- **Admin (`test_admin.py`):** `ADMIN_EMAILS` bootstraps `is_admin` at signup, non-admin emails aren't promoted, the flag surfaces on `/auth/me`; admin endpoints reject unauthenticated and non-admin tokens; new requests land in `Under Review` with profile snapshotted; admin inbox lists pending requests; admin can edit + approve (stamps `reviewed_by`/`reviewed_at`); admin can reject with reason; empty PATCH bodies and invalid status values are rejected; PATCH on unknown ID returns 404.

The AI step is stubbed in the tests, so they don't burn an Anthropic API quota.

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | — | Health check |
| POST | `/api/auth/signup` | — | Create an account; returns `{access_token, user}` |
| POST | `/api/auth/login` | — | Authenticate; returns `{access_token, user}` |
| GET | `/api/auth/me` | **Bearer** | Return the currently signed-in user |
| GET | `/api/requests` | — | List all RTI requests (filter by `status`, `department_id`); returns the privacy-scoped projection |
| GET | `/api/requests/{id}` | — | Get a single RTI request (privacy-scoped projection) |
| POST | `/api/requests` | **Bearer** | File a new RTI request — triggers cache lookup or live AI retrieval. Citizen name + email are pulled from the JWT identity; profile snapshot (phone, address, ID card) is also copied from the JWT user onto the record |
| GET | `/api/admin/requests/pending` | **Admin** | Inbox of `Under Review` requests, oldest first; full record |
| GET | `/api/admin/requests/{id}` | **Admin** | Full record (includes profile snapshot + audit fields) |
| PATCH | `/api/admin/requests/{id}` | **Admin** | Edit response, change status (`Under Review` → `Responded` or `Rejected`), and/or set rejection reason; stamps `reviewed_by` + `reviewed_at` |
| GET | `/api/departments` | — | List departments (a single entry: the ministry) |
| GET | `/api/departments/{id}` | — | Get a single department |
| GET | `/api/faqs` | — | List all FAQs |
| GET | `/api/stats` | — | Summary stats (totals by status) |

Tokens are 24-hour HS256 JWTs. Send them as `Authorization: Bearer <token>` on the protected endpoints. Admin endpoints additionally require the JWT to carry `is_admin: true` — non-admin tokens get 403.

---

## Notes

- All state is **in-memory** — restarting the backend resets any newly filed requests *and* the query cache to the seed data.
- The AI is strictly instructed to **try rtidhonbe.com first** and only fall back to `environment.gov.mv` if the vault doesn't contain the requested information. It is told not to invent figures, names, dates, or document references — if neither source has the answer, it says so and points the citizen at the next step.
- Web search and web fetch are server-side Anthropic tools and are billed separately from input/output tokens. Both are restricted to the two configured sites via `allowed_domains`. On Haiku 4.5 they run in `allowed_callers=["direct"]` mode (the model doesn't support the dynamic-filtering / programmatic-tool-calling default).
- Only the text emitted **after the last tool-use block** is returned to the citizen — intermediate planning text the model produces between search rounds is filtered out.
- The Vite dev server proxies all `/api/*` requests to the backend container, so no CORS issues in the browser.

### Limitations

- **Cache is exact-match.** Lowercase + punctuation-stripped + whitespace-collapsed on `(department_id, subject + description)`. Paraphrases (*"plastic ban enforcement 2024"* vs *"single-use plastic enforcement actions in 2024"*) don't dedupe — each will hit the AI fresh.
- **Two sources only.** The model cannot reach anything outside `rtidhonbe.com` and `environment.gov.mv`. If neither has the information, the citizen is directed to the formal RTI application process.
- **Latency on cache miss** is dominated by web round-trips (15–30 s typical, longer for complex queries).
- **Restart wipes state.** Newly filed requests and the query cache live in process memory — no database, no disk persistence.

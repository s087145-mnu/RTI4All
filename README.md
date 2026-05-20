# RTI4All — Ministry of Climate Change, Environment and Energy

**Colab26 Hackathon — Team 9**

A citizen-facing portal to file and track **Right to Information (RTI)** requests with the Maldives [Ministry of Climate Change, Environment and Energy](https://environment.gov.mv). Filed requests are answered immediately by an AI assistant that retrieves information live from the official sources.

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

1. **Cache lookup.** A normalized key is built from the request text (`subject + description`, lowercased, punctuation stripped). If a previous request produced an answer for the same normalized text, that answer is reused — no LLM call.
2. **Live retrieval (cache miss).** The AI step calls Claude Haiku 4.5 with web tools restricted to two domains, in strict priority order:
   1. **`rtidhonbe.com`** — the RTI vault (preferred source).
   2. **`environment.gov.mv`** — the ministry's official site (fallback, only used if the vault doesn't have the requested information).
3. **Drafting.** Claude composes a response grounded in the content it retrieved, cites which source it used, and tells the citizen the next step if neither source has the answer.
4. **Storage.** The request is saved with `status: "Responded"` and the AI-generated answer in the `response` field. The (query → answer) pair is stored in the cache for future lookups with the same text.

If the AI step fails (network, API error, etc.), the request is filed as `Pending` so the citizen can still track it. If `ANTHROPIC_API_KEY` is unset, the AI step returns a clearly-labelled stub.

**Authentication.** Filing an RTI request requires being signed in. The portal exposes a small JWT auth flow: sign up with email + password, receive a bearer token, attach it to the `POST /api/requests` call. The citizen's name and email on the created record are taken from the JWT identity — they're not in the request payload, so a logged-in user can't file under someone else's name. Public reads (`GET /api/requests`, departments, FAQs, stats) remain open so anonymous browsing still works.

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
│       └── test_auth.py      # Pytest coverage of the auth flow
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

### Configure the AI key and JWT secret

Export both before `docker compose up`. Compose passes them through to the backend container automatically.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export JWT_SECRET_KEY=$(openssl rand -hex 32)   # or any high-entropy secret
```

If `JWT_SECRET_KEY` is unset, the backend logs a warning and falls back to an insecure dev-only value. Never run that fallback in production.

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

The 12 tests cover: signup (success, duplicate-email rejection, invalid-email rejection), login (valid credentials, wrong password, unknown user), `POST /api/requests` protection (no token, malformed token, valid token), JWT identity override (the server overwrites any `citizen_name`/`email` an attacker tries to slip into the body), `GET /api/auth/me`, and that public reads remain open. The AI step is stubbed in the tests, so they don't burn an Anthropic API quota.

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | — | Health check |
| POST | `/api/auth/signup` | — | Create an account; returns `{access_token, user}` |
| POST | `/api/auth/login` | — | Authenticate; returns `{access_token, user}` |
| GET | `/api/auth/me` | **Bearer** | Return the currently signed-in user |
| GET | `/api/requests` | — | List all RTI requests (filter by `status`, `department_id`) |
| GET | `/api/requests/{id}` | — | Get a single RTI request |
| POST | `/api/requests` | **Bearer** | File a new RTI request — triggers cache lookup or live AI retrieval. Citizen name and email are pulled from the JWT identity, not the request body |
| GET | `/api/departments` | — | List departments (a single entry: the ministry) |
| GET | `/api/departments/{id}` | — | Get a single department |
| GET | `/api/faqs` | — | List all FAQs |
| GET | `/api/stats` | — | Summary stats (totals by status) |

Tokens are 24-hour HS256 JWTs. Send them as `Authorization: Bearer <token>` on the protected endpoints.

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

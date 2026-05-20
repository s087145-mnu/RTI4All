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
| Data | In-memory sample JSON (no database) |
| Container | Docker + Docker Compose |

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
│   ├── cache.py              # In-memory normalized-text query cache
│   └── data/
│       └── sample_data.json  # One ministry + sample requests + FAQs
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx           # All pages, components, routing
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- (Optional but recommended) An Anthropic API key with web-tools access — without one, the AI step falls back to a stub message

### Configure the AI key

Export the key in the shell before `docker compose up`. Compose passes it through to the backend container automatically.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

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

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/requests` | List all RTI requests (filter by `status`, `department_id`) |
| GET | `/api/requests/{id}` | Get a single RTI request |
| POST | `/api/requests` | File a new RTI request — triggers cache lookup or live AI retrieval, returns the created record (typically `status: "Responded"`) |
| GET | `/api/departments` | List departments (a single entry: the ministry) |
| GET | `/api/departments/{id}` | Get a single department |
| GET | `/api/faqs` | List all FAQs |
| GET | `/api/stats` | Summary stats (totals by status) |

---

## Notes

- All state is **in-memory** — restarting the backend resets any newly filed requests *and* the query cache to the seed data.
- The query cache uses **exact normalized match** (lowercase, stripped punctuation, collapsed whitespace) on the request text. Identical re-submissions reuse the prior answer instantly; paraphrased queries are treated as new and incur a fresh AI lookup.
- The AI is strictly instructed to **try rtidhonbe.com first** and only fall back to `environment.gov.mv` if the vault doesn't contain the requested information. It is told not to invent figures, names, dates, or document references — if neither source has the answer, it says so and points the citizen at the next step.
- Web search and web fetch are server-side Anthropic tools and are billed separately from input/output tokens. Both are restricted via `allowed_domains` to the two configured sites.
- The Vite dev server proxies all `/api/*` requests to the backend container, so no CORS issues in the browser.

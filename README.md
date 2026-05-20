# RTI4All

**Colab26 Hackathon — Team 9**

A citizen-facing portal to file and track **Right to Information (RTI)** requests across government departments. Filed requests are answered immediately by an AI assistant grounded in source materials (prior responded requests, FAQs).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite (JavaScript) |
| Backend | Python 3.11 + FastAPI |
| AI | Anthropic Claude Haiku 4.5 via the `anthropic` SDK |
| Data | In-memory sample JSON (no database) |
| Container | Docker + Docker Compose |

---

## How a Request Is Answered

When a citizen submits a new RTI request via `POST /api/requests`:

1. The department is validated and the request is assigned an ID.
2. A normalized cache key is built from `(department_id, subject + description)`.
3. **Cache hit** — the previously generated answer is reused; no LLM call.
4. **Cache miss** — the configured `DataSource` retrieves relevant source materials (FAQs + prior `Responded` requests in the same department), the AI step calls Claude Haiku 4.5 with those materials as grounding, and the answer is stored in the cache.
5. The request is recorded with `status: "Responded"` and the AI-generated text in the `response` field.

If `ANTHROPIC_API_KEY` is not set, the AI step returns a clearly-labelled stub so the app still runs offline; the request is filed as `Pending`.

The `DataSource` is a `Protocol` in `backend/data_source.py` — the current `SampleDataSource` reads from the in-memory JSON; a future implementation can hit real government APIs without changing any caller.

---

## Project Structure

```
RTI4All/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI application + routes
│   ├── ai.py                 # Anthropic SDK call, grounded prompt
│   ├── cache.py              # In-memory normalized-text query cache
│   ├── data_source.py        # DataSource Protocol + SampleDataSource
│   └── data/
│       └── sample_data.json  # Seed data (departments, requests, FAQs)
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
- (Optional) An Anthropic API key — without one, the AI step falls back to a stub message

### Configure the AI key

Export the key in the shell before `docker compose up`. Compose passes it through to the backend container automatically.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Run with Docker Compose

```bash
# From the project root (RTI4All/)
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
| POST | `/api/requests` | File a new RTI request — triggers cache lookup or AI answer, returns the created record (typically `status: "Responded"`) |
| GET | `/api/departments` | List all departments |
| GET | `/api/departments/{id}` | Get a single department |
| GET | `/api/faqs` | List all FAQs |
| GET | `/api/stats` | Summary stats (totals by status) |

---

## Notes

- All data is **in-memory** — restarting the backend resets any newly filed requests *and* the query cache to the seed data.
- The query cache uses **exact normalized match** (lowercase, stripped punctuation, collapsed whitespace) on `(department_id, subject + description)`. Paraphrased queries are treated as distinct.
- The AI is instructed to **stay grounded in the provided source materials** and to say so when the requested information is not in the sources, rather than inventing figures or document references.
- The Vite dev server proxies all `/api/*` requests to the backend container, so no CORS issues in the browser.
- To swap to a real government API later: implement the `DataSource` protocol in `backend/data_source.py` and wire it up at startup in `backend/main.py`.

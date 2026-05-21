# RTI4All — Go backend

Go port of the original FastAPI backend. Exposes the same HTTP API on
`:8000`, so the existing React frontend (`/frontend`) and any scripts
that hit `/api/*` continue to work unchanged.

## Why a port

The Python backend pulled in PyTorch + sentence-transformers + the
`graphify` CLI, which made the container ~1 GB and slow to cold-start.
The Go port keeps the same product behaviour but ships as a single
~15 MB static binary by replacing two heavy components with pure-Go
equivalents:

| Layer                | Python                                         | Go                                                    |
| -------------------- | ---------------------------------------------- | ----------------------------------------------------- |
| HTTP framework       | FastAPI + uvicorn                              | chi + net/http                                        |
| Auth                 | python-jose + passlib/bcrypt                   | golang-jwt + golang.org/x/crypto/bcrypt               |
| Anthropic client     | `anthropic` SDK                                | direct REST calls over net/http                       |
| RAG embeddings       | sentence-transformers (all-MiniLM-L6-v2)       | TF-IDF + cosine similarity (in-process)               |
| Graph retrieval      | `graphify` CLI subprocess + LLM-extracted KG   | token co-occurrence graph (in-process, no LLM cost)   |
| Persistence          | JSON file with atomic write + backups          | identical, in `internal/persistence`                  |

The product surface is identical: same endpoints, same JSON shapes,
same admin/citizen workflow, same seed data.

## Layout

```
backend-go/
├── main.go                     # entrypoint: load data, start server
├── data/
│   └── sample_data.json        # seed corpus (copied from Python backend)
├── internal/
│   ├── models/                 # JSON-serialisable RTI / user shapes
│   ├── persistence/            # atomic JSON store + backups
│   ├── cache/                  # in-memory query cache for AI answers
│   ├── rag/                    # TF-IDF retrieval over responded requests + FAQs
│   ├── graph/                  # token-cooccurrence graph retrieval
│   ├── ai/                     # Anthropic Messages API client
│   ├── auth/                   # JWT + bcrypt + chi middleware
│   └── handlers/               # HTTP routes (signup/login/requests/admin/…)
└── Dockerfile                  # multi-stage build → ~15 MB image
```

## Running locally

```bash
cd backend-go
go run .
```

Useful env vars (all optional):

| Variable                  | Default                       | Notes                                                       |
| ------------------------- | ----------------------------- | ----------------------------------------------------------- |
| `PORT`                    | `8000`                        | HTTP listen port                                            |
| `DATA_FILE`               | `data/sample_data.json`       | Path to the JSON-backed store                               |
| `JWT_SECRET_KEY`          | dev fallback (insecure)       | HS256 signing key — set in production                       |
| `ADMIN_EMAILS`            | `""`                          | Comma-separated list that get `is_admin=true` at signup     |
| `ANTHROPIC_API_KEY`       | `""`                          | If unset, AI step returns a stub response                   |
| `ANTHROPIC_MODEL`         | `claude-haiku-4-5`            | Used for citizen-facing draft answers                       |
| `ANTHROPIC_STRUCTURE_MODEL` | `claude-3-5-sonnet-20241022` | Used for the JSON-structuring step                          |
| `ENABLE_DATA_PERSISTENCE` | `true`                        | Set `false` to run read-only (no writes to disk)            |
| `MAX_BACKUPS`             | `10`                          | Rotated backup count under `data/backups/`                  |

## Running with Docker Compose

The repository's top-level `docker-compose.yml` now points at
`./backend-go`:

```bash
docker compose up --build
```

Backend listens on `:8000`, frontend on `:5173`, with the same
Vite proxy from `/api → backend:8000`.

## Smoke testing

A `/tmp/smoke.sh` script (kept out of the tree) exercises the full
contract: signup, login, citizen + admin views, filing a request, the
clarification flow, and the rejection/responded path. Run the
backend, then:

```bash
bash scripts/smoke.sh    # if you check it in; sample lives in PR notes
```

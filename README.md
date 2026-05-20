# RTI4All

**Colab26 Hackathon — Team 9**

A citizen-facing portal to file and track **Right to Information (RTI)** requests across government departments.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite (JavaScript) |
| Backend | Python 3.11 + FastAPI |
| Data | In-memory sample JSON (no database) |
| Container | Docker + Docker Compose |

---

## Project Structure

```
RTI4All/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py               # FastAPI application
│   └── data/
│       └── sample_data.json  # Seed data (departments, requests, FAQs)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        └── App.jsx
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

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
| POST | `/api/requests` | File a new RTI request |
| GET | `/api/departments` | List all departments |
| GET | `/api/departments/{id}` | Get a single department |
| GET | `/api/faqs` | List all FAQs |
| GET | `/api/stats` | Summary stats (totals by status) |

---

## Notes

- All data is **in-memory** — restarting the backend resets any newly filed requests to the sample data.
- The Vite dev server proxies all `/api/*` requests to the backend container, so no CORS issues in the browser.

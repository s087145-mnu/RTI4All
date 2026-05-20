"""
RTI4All – FastAPI backend
Right to Information for All: helps citizens file and track RTI requests.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RTI4All API",
    description="Backend API for the RTI4All citizen portal – file and track Right to Information requests.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory data store – loaded once at startup
# ---------------------------------------------------------------------------

DATA_FILE = Path(__file__).parent / "data" / "sample_data.json"

_db: dict = {}


@app.on_event("startup")
def load_data() -> None:
    """Load all seed data from the JSON file into memory."""
    with open(DATA_FILE, encoding="utf-8") as fh:
        _db.update(json.load(fh))
    print(
        f"[startup] Loaded {len(_db['requests'])} requests, "
        f"{len(_db['departments'])} departments, "
        f"{len(_db['faqs'])} FAQs."
    )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Department(BaseModel):
    id: str
    name: str
    description: str
    contact_email: str


class RTIRequest(BaseModel):
    id: str
    citizen_name: str
    email: str
    department_id: str
    department: str
    subject: str
    description: str
    status: str
    date_filed: str
    date_updated: str
    response: Optional[str] = None


class CreateRTIRequest(BaseModel):
    """Payload accepted by POST /api/requests."""

    citizen_name: str
    email: EmailStr
    department_id: str
    subject: str
    description: str


class FAQ(BaseModel):
    id: str
    question: str
    answer: str


class StatsResponse(BaseModel):
    total_requests: int
    pending: int
    in_progress: int
    responded: int
    rejected: int
    total_departments: int


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_department_name(department_id: str) -> str:
    """Return the department name for a given id, or raise 404."""
    for dept in _db["departments"]:
        if dept["id"] == department_id:
            return dept["name"]
    raise HTTPException(
        status_code=404,
        detail=f"Department with id '{department_id}' not found.",
    )


def _next_request_id() -> str:
    """Generate the next sequential RTI request id."""
    existing_ids = [r["id"] for r in _db["requests"]]
    max_seq = 0
    for rid in existing_ids:
        try:
            seq = int(rid.split("-")[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            pass
    year = date.today().year
    return f"RTI-{year}-{max_seq + 1:04d}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["Meta"])
def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


# ── Requests ────────────────────────────────────────────────────────────────


@app.get("/api/requests", response_model=list[RTIRequest], tags=["RTI Requests"])
def list_requests(
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: Pending | In Progress | Responded | Rejected",
    ),
    department_id: Optional[str] = Query(
        default=None,
        description="Filter by department id (e.g. dept-001)",
    ),
):
    """
    Return all RTI requests.
    Optionally filter by **status** and/or **department_id**.
    """
    results = list(_db["requests"])

    if status:
        normalised = status.strip().lower()
        results = [r for r in results if r["status"].lower() == normalised]

    if department_id:
        results = [r for r in results if r["department_id"] == department_id]

    return results


@app.get("/api/requests/{request_id}", response_model=RTIRequest, tags=["RTI Requests"])
def get_request(request_id: str):
    """Return a single RTI request by its id."""
    for req in _db["requests"]:
        if req["id"] == request_id:
            return req
    raise HTTPException(
        status_code=404,
        detail=f"RTI request '{request_id}' not found.",
    )


@app.post(
    "/api/requests", response_model=RTIRequest, status_code=201, tags=["RTI Requests"]
)
def create_request(payload: CreateRTIRequest):
    """
    Submit a new RTI request.

    The **department_id** must correspond to a known department.
    The new request is automatically assigned:
    - a sequential id
    - status `"Pending"`
    - `date_filed` and `date_updated` set to today
    - `response` set to `null`
    """
    department_name = _get_department_name(payload.department_id)

    today = date.today().isoformat()
    new_request: dict = {
        "id": _next_request_id(),
        "citizen_name": payload.citizen_name,
        "email": payload.email,
        "department_id": payload.department_id,
        "department": department_name,
        "subject": payload.subject,
        "description": payload.description,
        "status": "Pending",
        "date_filed": today,
        "date_updated": today,
        "response": None,
    }

    _db["requests"].append(new_request)
    return new_request


# ── Departments ──────────────────────────────────────────────────────────────


@app.get("/api/departments", response_model=list[Department], tags=["Departments"])
def list_departments():
    """Return all departments."""
    return _db["departments"]


@app.get(
    "/api/departments/{department_id}", response_model=Department, tags=["Departments"]
)
def get_department(department_id: str):
    """Return a single department by its id."""
    for dept in _db["departments"]:
        if dept["id"] == department_id:
            return dept
    raise HTTPException(
        status_code=404,
        detail=f"Department '{department_id}' not found.",
    )


# ── FAQs ─────────────────────────────────────────────────────────────────────


@app.get("/api/faqs", response_model=list[FAQ], tags=["FAQs"])
def list_faqs():
    """Return all frequently asked questions about the RTI process."""
    return _db["faqs"]


# ── Stats ─────────────────────────────────────────────────────────────────────


@app.get("/api/stats", response_model=StatsResponse, tags=["Meta"])
def get_stats():
    """
    Return a summary of RTI request statistics:
    total counts broken down by status, and number of registered departments.
    """
    requests = _db["requests"]
    status_counts: dict[str, int] = {
        "Pending": 0,
        "In Progress": 0,
        "Responded": 0,
        "Rejected": 0,
    }
    for req in requests:
        s = req.get("status", "")
        if s in status_counts:
            status_counts[s] += 1

    return StatsResponse(
        total_requests=len(requests),
        pending=status_counts["Pending"],
        in_progress=status_counts["In Progress"],
        responded=status_counts["Responded"],
        rejected=status_counts["Rejected"],
        total_departments=len(_db["departments"]),
    )

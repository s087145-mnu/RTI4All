"""
RTI4All – FastAPI backend
Right to Information for All: helps citizens file and track RTI requests.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ai import answer_request
from auth import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    UserPublic,
    authenticate_user,
    create_access_token,
    create_user,
    get_current_admin,
    get_current_user,
)
from cache import QueryCache
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from graph import GraphState
from persistence import PersistenceError, get_data_store
from pydantic import BaseModel
from rag import (
    RAGIndex,
    SentenceTransformersEmbedder,
    index_responded_request,
    populate_from_db,
)

log = logging.getLogger(__name__)

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
_data_store = None  # Initialized in startup
_query_cache = QueryCache()
_rag_index = RAGIndex(SentenceTransformersEmbedder())
_graph_state = GraphState()


@app.on_event("startup")
def load_data() -> None:
    """Load seed data, build the vector index, and build/load the graph."""
    global _data_store

    try:
        # Initialize persistence layer
        _data_store = get_data_store(DATA_FILE, enable_persistence=True)

        # Load data from file
        if _data_store:
            try:
                _db.update(_data_store.load())
                log.info("Data loaded via persistence layer")
            except PersistenceError as e:
                log.error(f"Failed to load from persistence layer: {e}")
                # Fall back to direct file read
                with open(DATA_FILE, encoding="utf-8") as fh:
                    _db.update(json.load(fh))
                log.warning("Loaded data directly from file (persistence disabled)")
        else:
            # Persistence disabled, load directly
            with open(DATA_FILE, encoding="utf-8") as fh:
                _db.update(json.load(fh))
            log.info("Persistence disabled, loaded data directly from file")

        # Build RAG index from responded requests
        populate_from_db(_rag_index, _db)
        log.info(f"RAG index populated with {len(_rag_index)} items")

        # Build graph on cache miss; reuse persisted graph.json otherwise.
        try:
            _graph_state.build_or_load(_db)
            log.info(f"Graph loaded with {len(_graph_state.retriever)} nodes")
        except Exception as e:
            log.error(f"Failed to build/load graph: {e}", exc_info=True)
            log.warning("Continuing without graph-based retrieval")

        # Create default users if they don't exist
        try:
            _create_default_users()
        except Exception as e:
            log.error(f"Failed to create default users: {e}", exc_info=True)

        print(
            f"[startup] ✓ Loaded {len(_db['requests'])} requests, "
            f"{len(_db['departments'])} departments, "
            f"{len(_db['faqs'])} FAQs. "
            f"RAG index: {len(_rag_index)} items. "
            f"Graph: {len(_graph_state.retriever)} nodes. "
            f"Persistence: {'enabled' if _data_store else 'disabled'}"
        )
    except Exception as e:
        log.critical(f"Startup failed: {e}", exc_info=True)
        raise


def _create_default_users() -> None:
    """Create default admin and citizen users for testing/demo purposes."""
    from auth import create_user

    # Default admin user
    admin_email = "officer@gov.mv"
    try:
        create_user(
            email=admin_email,
            password="super-secret-pass",
            full_name="Officer Hassan",
            present_address="Ministry HQ, Male'",
            phone_number="+960 3001000",
            id_card=None,
        )
        print(f"[startup] Created default admin user: {admin_email}")
    except Exception:
        # User already exists
        pass

    # Default citizen user
    citizen_email = "citizen@example.mv"
    try:
        create_user(
            email=citizen_email,
            password="another-pass",
            full_name="Aishath Hassan",
            present_address="H. Sunset, Hithadhoo, Addu City",
            phone_number="+960 7777777",
            id_card="A099887",
        )
        print(f"[startup] Created default citizen user: {citizen_email}")
    except Exception:
        # User already exists
        pass


def _persist_data() -> None:
    """Persist current data to disk if persistence is enabled."""
    if _data_store:
        try:
            _data_store.save(_db)
            log.debug("Data persisted to disk")
        except PersistenceError as e:
            log.error(f"Failed to persist data: {e}")
            # Don't fail the request if persistence fails
        except Exception as e:
            log.error(f"Unexpected error persisting data: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Department(BaseModel):
    id: str
    name: str
    description: str
    contact_email: str


class RTIRequest(BaseModel):
    """Full record, returned only by admin endpoints."""

    id: str
    citizen_name: str
    email: str
    # Snapshotted from the citizen's profile at filing time so the ministry has
    # full contact context without a second lookup, and so later profile edits
    # don't retroactively alter the record.
    citizen_phone: Optional[str] = None
    citizen_address: Optional[str] = None
    citizen_id_card: Optional[str] = None
    department_id: str
    department: str
    subject: str
    description: str
    status: str
    date_filed: str
    date_updated: str
    response: Optional[str] = None
    # Set when an admin approves / rejects / edits the response.
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class PublicRTIRequest(BaseModel):
    """Subset returned on public (citizen-facing) GETs. Excludes sensitive
    profile snapshot fields (phone, address, ID card) and the internal review
    audit (reviewed_by, reviewed_at)."""

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
    rejection_reason: Optional[str] = None


class CreateRTIRequest(BaseModel):
    """Payload accepted by POST /api/requests.

    citizen_name and email are NOT in this payload — they come from the
    authenticated user's JWT identity, so a logged-in user cannot file under
    someone else's name.
    """

    department_id: str
    subject: str
    description: str


class AdminUpdateRTIRequest(BaseModel):
    """Payload accepted by PATCH /api/admin/requests/{id}.

    All fields optional — the admin sends only what they want to change.
    Setting status to "Rejected" should be paired with a rejection_reason.
    """

    response: Optional[str] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None


class FAQ(BaseModel):
    id: str
    question: str
    answer: str


class StatsResponse(BaseModel):
    total_requests: int
    pending: int
    in_progress: int
    under_review: int
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


# ── Authentication ──────────────────────────────────────────────────────────


@app.post(
    "/api/auth/signup",
    response_model=AuthResponse,
    status_code=201,
    tags=["Auth"],
)
def signup(payload: SignupRequest):
    """Create a new user account and return an access token."""
    user = create_user(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        present_address=payload.present_address,
        phone_number=payload.phone_number,
        id_card=payload.id_card,
    )
    token = create_access_token(user)
    return AuthResponse(access_token=token, user=user)


@app.post("/api/auth/login", response_model=AuthResponse, tags=["Auth"])
def login(payload: LoginRequest):
    """Authenticate an existing user and return an access token."""
    user = authenticate_user(email=payload.email, password=payload.password)
    token = create_access_token(user)
    return AuthResponse(access_token=token, user=user)


@app.get("/api/auth/me", response_model=UserPublic, tags=["Auth"])
def me(current_user: UserPublic = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


# ── Requests ────────────────────────────────────────────────────────────────


@app.get("/api/requests", response_model=list[PublicRTIRequest], tags=["RTI Requests"])
def list_requests(
    current_user: UserPublic = Depends(get_current_user),
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
    Return RTI requests for the authenticated user.
    Admins can see all requests; regular users only see their own.
    Optionally filter by **status** and/or **department_id**.
    """
    results = list(_db["requests"])

    # Non-admin users can only see their own requests
    if not current_user.is_admin:
        results = [r for r in results if r["email"] == current_user.email]

    if status:
        normalised = status.strip().lower()
        results = [r for r in results if r["status"].lower() == normalised]

    if department_id:
        results = [r for r in results if r["department_id"] == department_id]

    return results


@app.get(
    "/api/requests/{request_id}", response_model=PublicRTIRequest, tags=["RTI Requests"]
)
def get_request(
    request_id: str,
    current_user: UserPublic = Depends(get_current_user),
):
    """
    Return a single RTI request by its id.
    Users can only access their own requests; admins can access all.
    """
    for req in _db["requests"]:
        if req["id"] == request_id:
            # Check authorization: admins can see all, users only their own
            if not current_user.is_admin and req["email"] != current_user.email:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to access this request.",
                )
            return req
    raise HTTPException(
        status_code=404,
        detail=f"RTI request '{request_id}' not found.",
    )


@app.post(
    "/api/requests", response_model=RTIRequest, status_code=201, tags=["RTI Requests"]
)
def create_request(
    payload: CreateRTIRequest,
    current_user: UserPublic = Depends(get_current_user),
):
    """
    Submit a new RTI request. Requires a valid bearer token.

    The citizen's name and email are taken from the authenticated user — the
    payload only carries the actual RTI content (department, subject, description).
    """
    department_name = _get_department_name(payload.department_id)

    today = date.today().isoformat()

    answer, request_status = _generate_answer(
        department_id=payload.department_id,
        subject=payload.subject,
        description=payload.description,
    )

    new_request: dict = {
        "id": _next_request_id(),
        "citizen_name": current_user.full_name,
        "email": current_user.email,
        "citizen_phone": current_user.phone_number,
        "citizen_address": current_user.present_address,
        "citizen_id_card": current_user.id_card,
        "department_id": payload.department_id,
        "department": department_name,
        "subject": payload.subject,
        "description": payload.description,
        "status": request_status,
        "date_filed": today,
        "date_updated": today,
        "response": answer,
        "reviewed_by": None,
        "reviewed_at": None,
        "rejection_reason": None,
    }

    _db["requests"].append(new_request)

    # Persist to disk
    try:
        _persist_data()
    except Exception as e:
        log.error(f"Failed to persist after creating request: {e}")
        # Continue - request is in memory even if persistence fails

    return new_request


def _generate_answer(
    *,
    department_id: str,
    subject: str,
    description: str,
) -> tuple[Optional[str], str]:
    """
    Return (draft_response_text, status) for a new RTI request.

    Checks the in-memory cache first (exact normalized match — same query
    text reuses the prior draft). On a miss, calls the AI step which looks
    up information live from rtidhonbe.com (preferred) and falls back to
    environment.gov.mv.

    The successful status is "Under Review" — the AI's output is a draft that
    a ministry officer must approve via the admin panel before becoming the
    official response. If the AI call fails, the request is filed as Pending
    so the citizen can still track it; the officer can author a response by
    hand from the admin panel.
    """
    # Validate inputs
    if not subject or not subject.strip():
        log.warning("Empty subject provided to _generate_answer")
        return None, "Pending"

    if not description or not description.strip():
        log.warning("Empty description provided to _generate_answer")
        return None, "Pending"

    # Check cache first
    cache_key = None
    try:
        cache_key = QueryCache.make_key(department_id, subject, description)
        cached = _query_cache.get(cache_key)
        if cached is not None:
            log.info(f"Cache hit for request about '{subject[:50]}...'")
            return cached, "Under Review"
    except Exception as e:
        log.warning(f"Cache lookup failed: {e}")
        # Continue without cache

    # Try AI generation
    try:
        log.info(f"Generating AI response for request about '{subject[:50]}...'")
        answer = answer_request(
            subject=subject,
            description=description,
            rag_index=_rag_index,
            graph_retriever=_graph_state.retriever,
        )

        if not answer or not answer.strip():
            log.warning("AI returned empty answer")
            return None, "Pending"

        # Cache the result if we have a valid cache key
        if cache_key:
            try:
                _query_cache.put(cache_key, answer)
            except Exception as e:
                log.warning(f"Failed to cache answer: {e}")
                # Continue - we have the answer even if caching fails

        log.info(f"AI answer generated successfully ({len(answer)} chars)")
        return answer, "Under Review"

    except Exception as e:
        log.error(f"AI answer step failed: {e}", exc_info=True)
        return None, "Pending"


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
        "Under Review": 0,
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
        under_review=status_counts["Under Review"],
        responded=status_counts["Responded"],
        rejected=status_counts["Rejected"],
        total_departments=len(_db["departments"]),
    )


# ── Admin ────────────────────────────────────────────────────────────────────

_ADMIN_EDITABLE_STATUSES = {"Under Review", "Responded", "Rejected", "Pending"}


@app.get(
    "/api/admin/requests/pending",
    response_model=list[RTIRequest],
    tags=["Admin"],
)
def admin_list_pending(_: UserPublic = Depends(get_current_admin)):
    """Admin inbox: requests awaiting human review, oldest first."""
    pending = [r for r in _db["requests"] if r.get("status") == "Under Review"]
    pending.sort(key=lambda r: (r.get("date_filed", ""), r.get("id", "")))
    return pending


@app.get(
    "/api/admin/requests/{request_id}",
    response_model=RTIRequest,
    tags=["Admin"],
)
def admin_get_request(
    request_id: str,
    _: UserPublic = Depends(get_current_admin),
):
    """Admin-only full record (includes citizen profile snapshot + audit fields)."""
    for req in _db["requests"]:
        if req["id"] == request_id:
            return req
    raise HTTPException(
        status_code=404,
        detail=f"RTI request '{request_id}' not found.",
    )


@app.patch(
    "/api/admin/requests/{request_id}",
    response_model=RTIRequest,
    tags=["Admin"],
)
def admin_update_request(
    request_id: str,
    payload: AdminUpdateRTIRequest,
    admin: UserPublic = Depends(get_current_admin),
):
    """
    Update a request's draft response, status, or both. Stamps reviewed_by /
    reviewed_at on any change. Used by the admin panel to approve, edit, or
    reject AI-drafted responses.
    """
    target = None
    for req in _db["requests"]:
        if req["id"] == request_id:
            target = req
            break
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"RTI request '{request_id}' not found.",
        )

    if (
        payload.response is None
        and payload.status is None
        and payload.rejection_reason is None
    ):
        raise HTTPException(
            status_code=400,
            detail="At least one of response, status, or rejection_reason must be provided.",
        )

    if payload.status is not None:
        if payload.status not in _ADMIN_EDITABLE_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid status '{payload.status}'. Allowed: "
                    + ", ".join(sorted(_ADMIN_EDITABLE_STATUSES))
                ),
            )
        target["status"] = payload.status

    if payload.response is not None:
        target["response"] = payload.response

    if payload.rejection_reason is not None:
        target["rejection_reason"] = payload.rejection_reason or None

    today = date.today().isoformat()
    target["date_updated"] = today
    target["reviewed_by"] = admin.email
    target["reviewed_at"] = today

    # Feedback loop: approved responses become precedent for both retrievers.
    if target.get("status") == "Responded":
        try:
            index_responded_request(_rag_index, target)
            log.debug(f"Indexed responded request {request_id} in RAG")
        except Exception as e:
            log.error(f"Failed to index request in RAG: {e}", exc_info=True)

        # graphify caches per-file extractions, so only the new markdown file
        # pays an LLM call here.
        try:
            _graph_state.update_for_request(target)
            log.debug(f"Updated graph for request {request_id}")
        except Exception as e:
            log.error(f"Graph update_for_request failed: {e}", exc_info=True)

    # Persist to disk
    try:
        _persist_data()
    except Exception as e:
        log.error(f"Failed to persist after updating request: {e}")
        # Continue - update is in memory even if persistence fails

    return target

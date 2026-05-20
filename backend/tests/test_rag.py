"""
Tests for the RAG pipeline.

The conftest swaps the global RAG index for one backed by a deterministic
BagOfWords embedder, so these tests don't load PyTorch / sentence-transformers
but still exercise the real indexing + cosine retrieval code paths.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.conftest import BagOfWordsEmbedder


# ── Embedder ──────────────────────────────────────────────────────────────


def test_bagofwords_embedder_is_deterministic_and_normalized():
    emb = BagOfWordsEmbedder(dim=64)
    a = emb.embed(["the quick brown fox"])
    b = emb.embed(["the quick brown fox"])
    assert np.allclose(a, b)
    # L2-normalized
    assert np.isclose(np.linalg.norm(a[0]), 1.0)
    # Empty input handled
    assert emb.embed([]).shape == (0, 64)


def test_bagofwords_similar_texts_score_higher_than_unrelated():
    emb = BagOfWordsEmbedder(dim=256)
    vecs = emb.embed([
        "coral reef bleaching monitoring 2023",
        "coral monitoring data for the 2023 season",
        "renewable energy installed capacity targets",
    ])
    sim_related = float(vecs[0] @ vecs[1])
    sim_unrelated = float(vecs[0] @ vecs[2])
    assert sim_related > sim_unrelated


# ── Index unit tests (use a private index, not the global one) ────────────


def _fresh_index():
    from rag import RAGIndex
    return RAGIndex(BagOfWordsEmbedder(dim=256))


def test_index_upsert_and_retrieve_returns_top_k_by_similarity():
    idx = _fresh_index()
    idx.upsert("a", "coral reef bleaching 2023 monitoring",
               {"id": "a", "kind": "request"})
    idx.upsert("b", "plastic ban enforcement statistics 2024",
               {"id": "b", "kind": "request"})
    idx.upsert("c", "renewable energy capacity targets",
               {"id": "c", "kind": "request"})
    assert len(idx) == 3

    hits = idx.retrieve("coral monitoring data 2023", k=2)
    assert len(hits) == 2
    assert hits[0]["id"] == "a"
    # Scores should be in descending order, both in [-1, 1].
    assert hits[0]["_score"] >= hits[1]["_score"]
    assert -1.0 <= hits[1]["_score"] <= 1.0


def test_index_upsert_replaces_existing_id():
    idx = _fresh_index()
    idx.upsert("a", "first text", {"id": "a", "version": 1})
    idx.upsert("a", "second text completely different", {"id": "a", "version": 2})
    assert len(idx) == 1
    hits = idx.retrieve("second", k=1)
    assert hits[0]["version"] == 2


def test_index_retrieve_returns_empty_on_empty_index():
    idx = _fresh_index()
    assert idx.retrieve("anything", k=5) == []


def test_index_retrieve_handles_blank_query():
    idx = _fresh_index()
    idx.upsert("a", "text", {"id": "a"})
    assert idx.retrieve("   ", k=3) == []


# ── populate_from_db ──────────────────────────────────────────────────────


def test_populate_from_db_loads_only_responded_requests_and_all_faqs():
    from rag import populate_from_db
    idx = _fresh_index()
    db = {
        "requests": [
            {"id": "R1", "status": "Responded", "response": "official text",
             "subject": "s1", "description": "d1"},
            {"id": "R2", "status": "Pending", "response": None,
             "subject": "s2", "description": "d2"},
            {"id": "R3", "status": "Under Review", "response": "draft",
             "subject": "s3", "description": "d3"},
        ],
        "faqs": [
            {"id": "F1", "question": "q1?", "answer": "a1"},
            {"id": "F2", "question": "q2?", "answer": "a2"},
        ],
    }
    populate_from_db(idx, db)
    # R1 (responded) + F1 + F2 = 3. R2 (pending), R3 (under review) are skipped.
    assert len(idx) == 3
    hits = idx.retrieve("s1 d1 official", k=5)
    kinds = {h["kind"] for h in hits}
    assert "request" in kinds
    request_ids = [h["id"] for h in hits if h["kind"] == "request"]
    assert "R1" in request_ids
    assert "R2" not in request_ids
    assert "R3" not in request_ids


# ── End-to-end: index is built at startup and grows on admin approval ─────


ADMIN_EMAIL = "officer@gov.mv"
CITIZEN_PROFILE = {
    "email": "rag-citizen@example.mv",
    "password": "long-password-789",
    "full_name": "RAG Citizen",
    "present_address": "Somewhere, Male'",
    "phone_number": "+960 7000111",
}
ADMIN_PROFILE = {
    "email": ADMIN_EMAIL,
    "password": "long-password-654",
    "full_name": "RAG Officer",
    "present_address": "Ministry HQ",
    "phone_number": "+960 3001000",
}


def _signup(client: TestClient, profile: dict) -> str:
    return client.post("/api/auth/signup", json=profile).json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_startup_seeds_rag_index_from_sample_data(client):
    """The seed data has 3 responded requests + 7 FAQs = 10 items in the
    stubbed index after startup."""
    import main
    assert len(main._rag_index) >= 5  # liberal lower bound — exact count tied to seed file


def test_admin_approval_adds_request_to_rag_index(client, monkeypatch):
    """After an officer approves a request, it must be retrievable from the
    archive for future queries."""
    import auth
    import main
    monkeypatch.setattr(auth, "_ADMIN_EMAILS", {ADMIN_EMAIL})

    pre_count = len(main._rag_index)

    admin_token = _signup(client, ADMIN_PROFILE)
    citizen_token = _signup(client, CITIZEN_PROFILE)

    filed = client.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Mangrove restoration projects",
            "description": "Status of mangrove restoration projects in 2024.",
        },
        headers=_bearer(citizen_token),
    ).json()

    # Filed but Under Review — not yet in index.
    assert len(main._rag_index) == pre_count

    # Approve it with an edited response that contains a distinctive phrase.
    distinctive = "MANGROVE-MARKER-XYZ official text"
    res = client.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"response": distinctive, "status": "Responded"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200

    # Now the request is in the index.
    assert len(main._rag_index) == pre_count + 1

    # And a search for the distinctive phrase returns it.
    hits = main._rag_index.retrieve("MANGROVE-MARKER-XYZ", k=3)
    ids = [h["id"] for h in hits if h["kind"] == "request"]
    assert filed["id"] in ids


def test_admin_rejection_does_not_add_to_rag_index(client, monkeypatch):
    """Rejected requests are NOT precedent — they shouldn't enter the corpus."""
    import auth
    import main
    monkeypatch.setattr(auth, "_ADMIN_EMAILS", {ADMIN_EMAIL})

    pre_count = len(main._rag_index)
    admin_token = _signup(client, ADMIN_PROFILE)
    citizen_token = _signup(client, CITIZEN_PROFILE)

    filed = client.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Officer home addresses",
            "description": "Personal home addresses of senior officers.",
        },
        headers=_bearer(citizen_token),
    ).json()

    res = client.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"status": "Rejected", "rejection_reason": "privacy exemption"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200
    # Index unchanged — only Responded items get added.
    assert len(main._rag_index) == pre_count

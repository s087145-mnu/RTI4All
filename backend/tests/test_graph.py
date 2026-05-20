"""
Tests for the graphify-backed graph retrieval layer.

The conftest stubs the `graphify extract` subprocess so tests don't shell out
or burn an LLM quota. These tests exercise:

  - Corpus export: responded RTIs + FAQs become one markdown file each.
  - GraphRetriever: given a fixture graph.json, it correctly walks edges from
    label-matching seed nodes and maps source_file back to payloads.
  - End-to-end: admin approval triggers update_for_request, which calls the
    (stubbed) subprocess and writes a new markdown file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Corpus export ─────────────────────────────────────────────────────────


def test_export_corpus_writes_one_md_per_responded_request_and_per_faq(tmp_path):
    from graph import export_corpus
    db = {
        "requests": [
            {"id": "RTI-A", "status": "Responded", "subject": "Subject A",
             "description": "Description A", "response": "Official A",
             "date_filed": "2024-01-01", "department": "MoCCEE"},
            {"id": "RTI-B", "status": "Pending", "subject": "Pending one",
             "description": "...", "response": None},
            {"id": "RTI-C", "status": "Under Review", "subject": "Draft one",
             "description": "...", "response": "AI draft"},
        ],
        "faqs": [
            {"id": "faq-1", "question": "Q1?", "answer": "A1."},
        ],
    }
    payloads = export_corpus(db, tmp_path)
    # Only Responded RTI + FAQ → 2 files.
    files = sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".md")
    assert files == ["faq-faq-1.md", "req-rti-a.md"]
    # Pending and Under Review are excluded.
    assert "req-rti-b.md" not in files
    assert "req-rti-c.md" not in files

    # Payload metadata threaded through.
    assert payloads["req-rti-a.md"]["kind"] == "request"
    assert payloads["req-rti-a.md"]["id"] == "RTI-A"
    assert payloads["faq-faq-1.md"]["kind"] == "faq"

    # Markdown content actually contains the fields.
    md = (tmp_path / "req-rti-a.md").read_text()
    assert "Subject A" in md
    assert "Official A" in md


def test_export_single_request_skips_non_responded(tmp_path):
    from graph import export_single_request
    assert export_single_request(
        {"id": "X", "status": "Pending", "subject": "s", "description": "d",
         "response": None},
        tmp_path,
    ) is None
    assert export_single_request(
        {"id": "Y", "status": "Responded", "subject": "subj", "description": "d",
         "response": "answer"},
        tmp_path,
    ) == "req-y.md"


# ── GraphRetriever ────────────────────────────────────────────────────────


def _fixture_graph(tmp_path: Path) -> Path:
    """Write a small fixture graph.json with two source files."""
    graph = {
        "nodes": [
            {"id": "n_coral_monitoring", "label": "Coral Monitoring",
             "source_file": "req-rti-a.md", "file_type": "document"},
            {"id": "n_baa_atoll", "label": "Baa Atoll",
             "source_file": "req-rti-a.md", "file_type": "document"},
            {"id": "n_plastic_phaseout", "label": "Plastic Phase Out",
             "source_file": "req-rti-b.md", "file_type": "document"},
            {"id": "n_rti_act", "label": "Right to Information Act",
             "source_file": "faq-faq-1.md", "file_type": "document"},
            {"id": "n_orphan", "label": "Unrelated",
             "source_file": "faq-faq-1.md", "file_type": "document"},
        ],
        "edges": [
            {"source": "n_coral_monitoring", "target": "n_baa_atoll",
             "relation": "located_in", "weight": 1.0},
            {"source": "n_baa_atoll", "target": "n_rti_act",
             "relation": "references", "weight": 1.0},
        ],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph))
    return path


def test_graph_retriever_finds_documents_by_label_match(tmp_path):
    from graph import GraphRetriever
    graph_path = _fixture_graph(tmp_path)
    payloads = {
        "req-rti-a.md": {"kind": "request", "id": "RTI-A", "subject": "Coral 2023"},
        "req-rti-b.md": {"kind": "request", "id": "RTI-B", "subject": "Plastic"},
        "faq-faq-1.md": {"kind": "faq", "id": "faq-1", "question": "What is RTI?"},
    }
    r = GraphRetriever(graph_path, payloads)
    assert len(r) == 5

    hits = r.retrieve("Coral monitoring data", k=3, hops=1)
    ids = [h["id"] for h in hits]
    assert "RTI-A" in ids  # direct label match
    # Each hit has a score and source_file annotation.
    for h in hits:
        assert "_score" in h
        assert "_source_file" in h


def test_graph_retriever_traverses_edges_to_neighbours(tmp_path):
    from graph import GraphRetriever
    graph_path = _fixture_graph(tmp_path)
    payloads = {
        "req-rti-a.md": {"kind": "request", "id": "RTI-A", "subject": "Coral"},
        "faq-faq-1.md": {"kind": "faq", "id": "faq-1", "question": "RTI?"},
    }
    r = GraphRetriever(graph_path, payloads)
    # Query mentions only Baa Atoll; one hop reaches the FAQ source via the
    # baa_atoll → rti_act edge.
    hits = r.retrieve("Baa Atoll", k=5, hops=1)
    files = {h["_source_file"] for h in hits}
    assert "req-rti-a.md" in files  # direct match (baa atoll is in this file)
    assert "faq-faq-1.md" in files  # reached via 1-hop neighbour rti_act


def test_graph_retriever_returns_empty_when_no_label_matches(tmp_path):
    from graph import GraphRetriever
    graph_path = _fixture_graph(tmp_path)
    payloads = {
        "req-rti-a.md": {"kind": "request", "id": "RTI-A"},
        "faq-faq-1.md": {"kind": "faq", "id": "faq-1"},
    }
    r = GraphRetriever(graph_path, payloads)
    # Tokens chosen to have zero overlap with any node label in the fixture.
    assert r.retrieve("mongoose elephant zebra giraffe rhinoceros", k=4) == []


def test_graph_retriever_handles_missing_graph_file(tmp_path):
    from graph import GraphRetriever
    r = GraphRetriever(tmp_path / "does-not-exist.json", {})
    assert len(r) == 0
    assert r.retrieve("anything", k=3) == []


# ── End-to-end: graph layer is plumbed through main.py ────────────────────


ADMIN_EMAIL = "officer@gov.mv"
ADMIN_PROFILE = {
    "email": ADMIN_EMAIL,
    "password": "long-password-654",
    "full_name": "Graph Officer",
    "present_address": "Ministry HQ",
    "phone_number": "+960 3001000",
}
CITIZEN_PROFILE = {
    "email": "graph-citizen@example.mv",
    "password": "long-password-789",
    "full_name": "Graph Citizen",
    "present_address": "Somewhere",
    "phone_number": "+960 7000111",
}


def _signup(client: TestClient, profile: dict) -> str:
    return client.post("/api/auth/signup", json=profile).json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_startup_creates_graph_state_with_stubbed_extract(client):
    """Startup should run build_or_load → stubbed run_graphify_extract → empty
    graph.json → empty retriever. No subprocess, no errors."""
    import main
    assert main._graph_state.graph_path.exists()
    assert len(main._graph_state.retriever) == 0  # stubbed graph has no nodes


def test_admin_approval_runs_update_for_request(client, monkeypatch):
    """Approving a request must (a) write a new markdown file into the corpus
    dir, and (b) re-invoke (stubbed) graphify extract."""
    import auth
    import graph as graph_mod
    import main

    monkeypatch.setattr(auth, "_ADMIN_EMAILS", {ADMIN_EMAIL})

    # Count how many times the stubbed extract is invoked.
    call_count = {"n": 0}
    original = graph_mod.run_graphify_extract

    def counting_stub(corpus_dir, **kwargs):
        call_count["n"] += 1
        return original(corpus_dir, **kwargs)

    monkeypatch.setattr(graph_mod, "run_graphify_extract", counting_stub)

    admin_token = _signup(client, ADMIN_PROFILE)
    citizen_token = _signup(client, CITIZEN_PROFILE)

    filed = client.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Mangrove restoration",
            "description": "Status of mangrove restoration projects in 2024.",
        },
        headers=_bearer(citizen_token),
    ).json()

    pre_files = set(main._graph_state.corpus_dir.iterdir())
    pre_calls = call_count["n"]

    res = client.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"response": "OFFICIAL: mangrove update.", "status": "Responded"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200

    # graphify extract was re-run.
    assert call_count["n"] == pre_calls + 1

    # A new markdown file was added to the corpus dir.
    post_files = set(main._graph_state.corpus_dir.iterdir())
    added = post_files - pre_files
    assert any(p.name.startswith("req-") and p.suffix == ".md" for p in added)


def test_admin_rejection_does_not_run_update_for_request(client, monkeypatch):
    import auth
    import graph as graph_mod
    import main

    monkeypatch.setattr(auth, "_ADMIN_EMAILS", {ADMIN_EMAIL})

    call_count = {"n": 0}
    original = graph_mod.run_graphify_extract

    def counting_stub(corpus_dir, **kwargs):
        call_count["n"] += 1
        return original(corpus_dir, **kwargs)

    monkeypatch.setattr(graph_mod, "run_graphify_extract", counting_stub)

    admin_token = _signup(client, ADMIN_PROFILE)
    citizen_token = _signup(client, CITIZEN_PROFILE)

    filed = client.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Personal phone numbers",
            "description": "Private contact details of officers.",
        },
        headers=_bearer(citizen_token),
    ).json()

    pre_calls = call_count["n"]
    res = client.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"status": "Rejected", "rejection_reason": "privacy exemption"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200
    # Rejection must NOT trigger a graph update.
    assert call_count["n"] == pre_calls

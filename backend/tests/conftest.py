"""
Shared pytest fixtures.

The `client` fixture gives every test a fresh in-memory store, an empty query
cache, an AI step that's stubbed (so tests don't burn an Anthropic quota), a
RAG index backed by a deterministic bag-of-words embedder (so tests don't load
sentence-transformers / torch), and NO admin emails configured by default.
Admin tests override _ADMIN_EMAILS explicitly.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient


def _stable_hash(s: str) -> int:
    return int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big")


class BagOfWordsEmbedder:
    """Deterministic, dependency-free embedder used in tests.

    Tokenizes on whitespace, hashes each token into a fixed-size vector
    dimension, accumulates counts, then L2-normalizes. Cosine similarity
    between vectors approximates token overlap — fine for proving the
    retrieval plumbing works without loading a real model.
    """

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def embed(self, texts):
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                w = w.strip(".,;:!?'\"()-")
                if not w:
                    continue
                out[i, _stable_hash(w) % self._dim] += 1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


@pytest.fixture
def client(monkeypatch, tmp_path):
    import main
    import auth
    import rag
    import graph

    # Replace the global RAG index with a stub-embedded one. Done BEFORE the
    # TestClient context manager so startup populates the stub index.
    stub_index = rag.RAGIndex(BagOfWordsEmbedder())
    monkeypatch.setattr(main, "_rag_index", stub_index)

    # Replace the graphify subprocess invocation with a no-op stub that writes
    # an empty graph.json. Tests can override the contents via fixtures that
    # set a richer graph in tmp_path/rag_cache/corpus/graphify-out/graph.json.
    def stub_extract(corpus_dir, *, backend="claude", timeout=300):
        gout = corpus_dir / "graphify-out"
        gout.mkdir(parents=True, exist_ok=True)
        graph_path = gout / "graph.json"
        if not graph_path.exists():
            graph_path.write_text('{"nodes": [], "edges": []}')
        return graph_path

    monkeypatch.setattr(graph, "run_graphify_extract", stub_extract)
    # Per-test graph state pointed at a tmp dir — tests stay isolated.
    monkeypatch.setattr(main, "_graph_state", graph.GraphState(cache_dir=tmp_path / "rag_cache"))

    auth.reset_users()
    main._query_cache._store.clear()
    monkeypatch.setattr(main, "answer_request", lambda **kwargs: "stub AI draft")
    monkeypatch.setattr(auth, "_ADMIN_EMAILS", set())

    with TestClient(main.app) as test_client:
        yield test_client

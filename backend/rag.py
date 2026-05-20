"""
Retrieval-Augmented Generation pipeline for the RTI portal.

Indexes the ministry's mock data — past responded RTI requests (precedent) and
FAQs (process knowledge) — so the AI step can ground its drafts in concrete
prior work, alongside the live web sources.

Architecture:
- `Embedder` is a Protocol — production uses `SentenceTransformersEmbedder`
  with `all-MiniLM-L6-v2`; tests use a deterministic stub.
- `RAGIndex` holds the embedding matrix in memory (numpy). Cosine similarity
  is fine at our scale (≤ a few hundred items).
- Newly approved requests get added to the index via `add_request_to_index`
  so each officer approval enriches the retrievable corpus.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Protocol

import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an array of shape (len(texts), dim) of L2-normalized vectors."""
        ...


class SentenceTransformersEmbedder:
    """Lazy-loaded singleton wrapper around sentence-transformers."""

    _MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # local import keeps tests fast
                log.info("Loading sentence-transformers model %s ...", self._MODEL_NAME)
                self._model = SentenceTransformer(self._MODEL_NAME)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        model = self._load()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


def _request_text(req: dict) -> str:
    """Searchable text for an RTI request: subject + description (+ response if responded)."""
    parts = [
        req.get("subject", ""),
        req.get("description", ""),
    ]
    response = req.get("response")
    if response and req.get("status") in {"Responded", "Under Review"}:
        parts.append(response)
    return "\n".join(p for p in parts if p)


def _faq_text(faq: dict) -> str:
    return f"{faq.get('question', '')}\n{faq.get('answer', '')}"


class RAGIndex:
    """
    Single in-memory index keyed by string id. Embedding matrix is a numpy
    float32 array of shape (N, dim); ids and payloads are parallel lists.
    Cosine similarity is dot product because all vectors are L2-normalized.
    """

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._ids: list[str] = []
        self._payloads: list[dict] = []
        self._matrix: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._ids)

    # --- write path -------------------------------------------------------

    def reset(self) -> None:
        with self._lock:
            self._ids.clear()
            self._payloads.clear()
            self._matrix = None

    def upsert(self, item_id: str, text: str, payload: dict) -> None:
        """Add or replace an item by id."""
        vec = self._embedder.embed([text])  # (1, dim)
        with self._lock:
            if item_id in self._ids:
                idx = self._ids.index(item_id)
                self._payloads[idx] = payload
                if self._matrix is not None:
                    self._matrix[idx] = vec[0]
                return
            self._ids.append(item_id)
            self._payloads.append(payload)
            if self._matrix is None:
                self._matrix = vec
            else:
                self._matrix = np.vstack([self._matrix, vec])

    def bulk_load(self, items: list[tuple[str, str, dict]]) -> None:
        """Replace the index with a batch of (id, text, payload) tuples."""
        if not items:
            self.reset()
            return
        texts = [t for _, t, _ in items]
        vecs = self._embedder.embed(texts)
        with self._lock:
            self._ids = [i for i, _, _ in items]
            self._payloads = [p for _, _, p in items]
            self._matrix = vecs

    # --- read path --------------------------------------------------------

    def retrieve(self, query: str, k: int = 4) -> list[dict]:
        """
        Return up to k payloads ranked by cosine similarity to the query.
        Each returned dict includes the original payload fields plus a
        `_score` float in [-1, 1].
        """
        if self._matrix is None or len(self._ids) == 0 or not query.strip():
            return []
        qvec = self._embedder.embed([query])[0]  # (dim,)
        scores = self._matrix @ qvec  # cosine, since both are L2-normalized
        top_k = min(k, len(self._ids))
        # argsort ascending → take last `top_k`, reverse for descending.
        top_idx = np.argsort(scores)[-top_k:][::-1]
        out: list[dict] = []
        for i in top_idx:
            entry = dict(self._payloads[int(i)])
            entry["_score"] = float(scores[int(i)])
            out.append(entry)
        return out


# ---------------------------------------------------------------------------
# Population helpers (seed + per-request)
# ---------------------------------------------------------------------------


def populate_from_db(index: RAGIndex, db: dict) -> None:
    """Seed the index from sample_data.json contents."""
    items: list[tuple[str, str, dict]] = []
    for req in db.get("requests", []):
        # Only past *responded* requests have value as precedent.
        if req.get("status") != "Responded" or not req.get("response"):
            continue
        text = _request_text(req)
        items.append(
            (
                f"req:{req['id']}",
                text,
                {
                    "kind": "request",
                    "id": req["id"],
                    "subject": req.get("subject"),
                    "description": req.get("description"),
                    "response": req.get("response"),
                    "status": req.get("status"),
                    "date_filed": req.get("date_filed"),
                },
            )
        )
    for faq in db.get("faqs", []):
        items.append(
            (
                f"faq:{faq['id']}",
                _faq_text(faq),
                {
                    "kind": "faq",
                    "id": faq["id"],
                    "question": faq.get("question"),
                    "answer": faq.get("answer"),
                },
            )
        )
    index.bulk_load(items)
    log.info("RAG index populated with %d items.", len(index))


def index_responded_request(index: RAGIndex, req: dict) -> None:
    """
    Add (or refresh) a responded request in the index. Called when an officer
    approves a request via the admin panel — so each approval grows the corpus
    available to future drafts.
    """
    if req.get("status") != "Responded" or not req.get("response"):
        return
    index.upsert(
        f"req:{req['id']}",
        _request_text(req),
        {
            "kind": "request",
            "id": req["id"],
            "subject": req.get("subject"),
            "description": req.get("description"),
            "response": req.get("response"),
            "status": req.get("status"),
            "date_filed": req.get("date_filed"),
        },
    )


def format_retrieved_for_prompt(hits: list[dict]) -> str:
    """Render retrieved items as a compact, citation-ready block for the LLM prompt."""
    if not hits:
        return "(no related ministry records found in the local archive)"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        if h["kind"] == "request":
            lines.append(
                f"[{i}] Past responded RTI · {h['id']} (filed {h.get('date_filed', '?')})\n"
                f"    Subject: {h.get('subject')}\n"
                f"    Description: {h.get('description')}\n"
                f"    Official response: {h.get('response')}"
            )
        elif h["kind"] == "faq":
            lines.append(
                f"[{i}] FAQ · {h['id']}\n"
                f"    Q: {h.get('question')}\n"
                f"    A: {h.get('answer')}"
            )
    return "\n\n".join(lines)

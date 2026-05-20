"""
Graph-augmented retrieval layer over the ministry archive, powered by
graphify (https://github.com/safishamsi/graphify).

Flow:
  1. Export each responded RTI request and each FAQ as a markdown file under
     a working corpus directory. One file per chunk.
  2. Invoke `graphify extract` (subprocess) on the corpus directory. Graphify
     writes `graphify-out/graph.json` — nodes (entities) and edges
     (relationships) extracted by an LLM, plus a per-file extraction cache so
     re-runs only pay for changed files.
  3. Load `graph.json` once at startup. `GraphRetriever.retrieve(query)`
     matches the query against node labels, traverses edges to neighbouring
     nodes, maps everything back to source files, and returns the underlying
     chunk payloads. No subprocess at query time.
  4. When an officer approves a new request, append a markdown file and run
     `graphify extract` again; cached files are skipped, so only the new
     file pays the LLM cost.

This is the persistence + structural-retrieval layer that "saves compute over
time" — the LLM extraction cost is paid once per piece of content.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

_DEFAULT_CACHE_DIR = Path("/app/.rag_cache")  # in-container path; gitignored
_CORPUS_SUBDIR = "corpus"
_GRAPHIFY_OUT = "graphify-out"
_GRAPH_FILE = "graph.json"


# ---------------------------------------------------------------------------
# Corpus export
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _SLUG_RE.sub("-", s.lower()).strip("-") or "item"


def _request_markdown(req: dict) -> str:
    return (
        f"# {req['subject']}\n\n"
        f"**RTI Reference:** {req['id']}\n"
        f"**Department:** {req.get('department', 'Ministry of Climate Change, Environment and Energy')}\n"
        f"**Date filed:** {req.get('date_filed', 'unknown')}\n\n"
        f"## Request\n\n{req.get('description', '').strip()}\n\n"
        f"## Official response\n\n{(req.get('response') or '').strip()}\n"
    )


def _faq_markdown(faq: dict) -> str:
    return (
        f"# FAQ: {faq['question']}\n\n"
        f"**Reference:** {faq['id']}\n\n"
        f"{faq.get('answer', '').strip()}\n"
    )


def export_corpus(db: dict, corpus_dir: Path) -> dict[str, dict]:
    """
    Write each responded RTI request and each FAQ as a markdown file.
    Returns a mapping of filename → original payload for later lookup.
    """
    corpus_dir.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, dict] = {}

    for req in db.get("requests", []):
        if req.get("status") != "Responded" or not req.get("response"):
            continue
        filename = f"req-{_slug(req['id'])}.md"
        (corpus_dir / filename).write_text(_request_markdown(req), encoding="utf-8")
        payloads[filename] = {
            "kind": "request",
            "id": req["id"],
            "subject": req.get("subject"),
            "description": req.get("description"),
            "response": req.get("response"),
            "date_filed": req.get("date_filed"),
        }

    for faq in db.get("faqs", []):
        filename = f"faq-{_slug(faq['id'])}.md"
        (corpus_dir / filename).write_text(_faq_markdown(faq), encoding="utf-8")
        payloads[filename] = {
            "kind": "faq",
            "id": faq["id"],
            "question": faq.get("question"),
            "answer": faq.get("answer"),
        }

    return payloads


def export_single_request(req: dict, corpus_dir: Path) -> Optional[str]:
    """Write one responded request to the corpus dir; return the filename, or
    None if the request isn't eligible (not Responded / no response)."""
    if req.get("status") != "Responded" or not req.get("response"):
        return None
    corpus_dir.mkdir(parents=True, exist_ok=True)
    filename = f"req-{_slug(req['id'])}.md"
    (corpus_dir / filename).write_text(_request_markdown(req), encoding="utf-8")
    return filename


# ---------------------------------------------------------------------------
# graphify CLI invocation
# ---------------------------------------------------------------------------


class GraphifyError(RuntimeError):
    pass


def run_graphify_extract(
    corpus_dir: Path,
    *,
    backend: str = "claude",
    timeout: int = 300,
) -> Path:
    """
    Run `graphify extract` on the corpus directory. Graphify caches per-file
    extractions under graphify-out/cache/, so repeated runs only pay the LLM
    cost for new or changed files.

    Returns the absolute path to graph.json.
    """
    if shutil.which("graphify") is None:
        raise GraphifyError("graphify CLI is not on PATH. Install with `pip install graphifyy`.")

    cmd = [
        "graphify",
        "extract",
        str(corpus_dir),
        "--backend",
        backend,
        "--no-cluster",  # we don't render the HTML viz / clusters; skip the work
    ]
    log.info("Running %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise GraphifyError(
            f"graphify extract failed (exit {proc.returncode}).\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    log.info("graphify extract output: %s", proc.stdout.strip().splitlines()[-1] if proc.stdout else "(no output)")

    graph_path = corpus_dir / _GRAPHIFY_OUT / _GRAPH_FILE
    if not graph_path.exists():
        raise GraphifyError(f"graphify extract completed but {graph_path} was not produced.")
    return graph_path


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2}


class GraphRetriever:
    """
    Retrieves chunks linked through the entity graph that graphify built.

    The lookup is:
        query tokens → matching node labels → 1-hop neighbours via edges
                     → source_file of each hit → mapped chunk payload
    """

    def __init__(
        self,
        graph_path: Optional[Path],
        payloads: dict[str, dict],
    ) -> None:
        self._payloads = payloads
        self._nodes: list[dict] = []
        self._adj: dict[str, list[str]] = defaultdict(list)
        self._node_by_id: dict[str, dict] = {}
        if graph_path is not None and graph_path.exists():
            self._load(graph_path)

    def _load(self, graph_path: Path) -> None:
        with open(graph_path, encoding="utf-8") as fh:
            data = json.load(fh)
        self._nodes = data.get("nodes", []) or []
        self._node_by_id = {n["id"]: n for n in self._nodes if "id" in n}
        self._adj = defaultdict(list)
        for edge in data.get("edges", []) or []:
            s, t = edge.get("source"), edge.get("target")
            if s and t:
                # Undirected for traversal — symmetric in either direction.
                self._adj[s].append(t)
                self._adj[t].append(s)
        log.info(
            "GraphRetriever loaded %d nodes, %d edge-pairs from %s",
            len(self._nodes),
            sum(len(v) for v in self._adj.values()) // 2,
            graph_path,
        )

    def __len__(self) -> int:
        return len(self._nodes)

    def retrieve(self, query: str, *, k: int = 4, hops: int = 1) -> list[dict]:
        if not self._nodes or not query.strip():
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        # Score each node by token overlap with the query.
        node_scores: dict[str, float] = {}
        for n in self._nodes:
            label = (n.get("label") or "").lower()
            label_tokens = _tokenize(label)
            if not label_tokens:
                continue
            overlap = len(label_tokens & q_tokens)
            if overlap:
                node_scores[n["id"]] = overlap / max(1, len(label_tokens))

        if not node_scores:
            return []

        # Seed: top-scoring nodes by label match.
        seeds = sorted(node_scores.items(), key=lambda kv: kv[1], reverse=True)
        seed_ids = [nid for nid, _ in seeds[: max(4, k)]]

        # Expand by `hops` of edge traversal (typically 1 hop is enough).
        reached: dict[str, float] = {nid: node_scores[nid] for nid in seed_ids}
        frontier = list(seed_ids)
        for _ in range(max(0, hops)):
            next_frontier: list[str] = []
            for nid in frontier:
                for neighbour in self._adj.get(nid, []):
                    if neighbour not in reached:
                        # Decayed score from the seed; encourages variety.
                        reached[neighbour] = node_scores.get(nid, 0.5) * 0.5
                        next_frontier.append(neighbour)
            frontier = next_frontier

        # Group reached nodes by source_file and aggregate scores.
        file_scores: dict[str, float] = defaultdict(float)
        for nid, score in reached.items():
            node = self._node_by_id.get(nid)
            if not node:
                continue
            sf = node.get("source_file")
            if not sf:
                continue
            file_scores[sf] += score

        ranked = sorted(file_scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[dict] = []
        for source_file, score in ranked[:k]:
            payload = self._payloads.get(source_file)
            if not payload:
                continue
            entry = dict(payload)
            entry["_score"] = float(score)
            entry["_source_file"] = source_file
            out.append(entry)
        return out


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


class GraphState:
    """Holds the persisted-on-disk graph + its in-memory retriever."""

    def __init__(self, cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        self.corpus_dir = cache_dir / _CORPUS_SUBDIR
        self.graph_path = self.corpus_dir / _GRAPHIFY_OUT / _GRAPH_FILE
        self.payloads: dict[str, dict] = {}
        self.retriever: GraphRetriever = GraphRetriever(None, {})
        self._lock = threading.Lock()

    def build_or_load(self, db: dict, *, backend: str = "claude") -> None:
        """
        Materialize the graph for the given db. If a cached graph.json exists
        and the corpus hasn't grown, reuse it. Otherwise, run graphify extract.
        """
        with self._lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.payloads = export_corpus(db, self.corpus_dir)

            need_build = not self.graph_path.exists()
            if need_build:
                log.info("graph cache miss — running graphify extract")
                try:
                    run_graphify_extract(self.corpus_dir, backend=backend)
                except GraphifyError:
                    log.exception("graphify extract failed; continuing without graph layer.")
            else:
                log.info("graph cache hit — reusing %s", self.graph_path)

            self.retriever = GraphRetriever(self.graph_path, self.payloads)

    def update_for_request(self, req: dict, *, backend: str = "claude") -> None:
        """
        Called when an officer approves a request. Writes the new markdown
        file and re-runs `graphify extract` — graphify's per-file cache means
        only the new file pays the LLM cost.
        """
        with self._lock:
            filename = export_single_request(req, self.corpus_dir)
            if filename is None:
                return
            self.payloads[filename] = {
                "kind": "request",
                "id": req["id"],
                "subject": req.get("subject"),
                "description": req.get("description"),
                "response": req.get("response"),
                "date_filed": req.get("date_filed"),
            }
            try:
                run_graphify_extract(self.corpus_dir, backend=backend)
            except GraphifyError:
                log.exception("graphify extract failed during update_for_request.")
                return
            self.retriever = GraphRetriever(self.graph_path, self.payloads)


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


def format_graph_hits_for_prompt(hits: Iterable[dict]) -> str:
    items = list(hits)
    if not items:
        return "(no graph-linked precedent found)"
    lines: list[str] = []
    for i, h in enumerate(items, start=1):
        if h["kind"] == "request":
            lines.append(
                f"[G{i}] Graph-linked RTI · {h['id']} (filed {h.get('date_filed', '?')})\n"
                f"    Subject: {h.get('subject')}\n"
                f"    Description: {h.get('description')}\n"
                f"    Official response: {h.get('response')}"
            )
        elif h["kind"] == "faq":
            lines.append(
                f"[G{i}] Graph-linked FAQ · {h['id']}\n"
                f"    Q: {h.get('question')}\n"
                f"    A: {h.get('answer')}"
            )
    return "\n\n".join(lines)

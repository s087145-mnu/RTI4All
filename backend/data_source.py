"""
Pluggable retrieval layer for the AI answer step.

`DataSource.fetch(...)` returns a list of context snippets relevant to an RTI
query. `SampleDataSource` reads from the in-memory sample JSON; swap in a
`GovApiDataSource` later by implementing the same Protocol.
"""

from __future__ import annotations

from typing import Protocol


class DataSource(Protocol):
    def fetch(self, department_id: str, query: str, limit: int = 8) -> list[dict]:
        ...


class SampleDataSource:
    """Retrieves FAQs + prior responded requests in the same department."""

    def __init__(self, db: dict) -> None:
        self._db = db

    def fetch(self, department_id: str, query: str, limit: int = 8) -> list[dict]:
        items: list[dict] = []

        for req in self._db.get("requests", []):
            if req.get("department_id") != department_id:
                continue
            if req.get("status") != "Responded" or not req.get("response"):
                continue
            items.append(
                {
                    "kind": "prior_request",
                    "subject": req["subject"],
                    "description": req["description"],
                    "response": req["response"],
                }
            )

        for faq in self._db.get("faqs", []):
            items.append(
                {
                    "kind": "faq",
                    "question": faq["question"],
                    "answer": faq["answer"],
                }
            )

        return items[:limit]

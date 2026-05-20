"""
In-memory query cache keyed on (department_id, normalized text).

Lets similar future requests reuse a previously generated AI answer without
calling the LLM again.
"""

from __future__ import annotations

import re
import string


_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


class QueryCache:
    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    @staticmethod
    def make_key(department_id: str, subject: str, description: str) -> tuple[str, str]:
        return department_id, _normalize(f"{subject} {description}")

    def get(self, key: tuple[str, str]) -> str | None:
        return self._store.get(key)

    def put(self, key: tuple[str, str], answer: str) -> None:
        self._store[key] = answer

    def __len__(self) -> int:
        return len(self._store)

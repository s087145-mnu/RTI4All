"""
Shared pytest fixtures.

The `client` fixture gives every test a fresh in-memory store, an empty query
cache, an AI step that's stubbed (so tests don't burn an Anthropic quota), and
NO admin emails configured by default. Admin tests override _ADMIN_EMAILS
explicitly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import main
    import auth

    auth.reset_users()
    main._query_cache._store.clear()
    monkeypatch.setattr(main, "answer_request", lambda **kwargs: "stub AI draft")
    monkeypatch.setattr(auth, "_ADMIN_EMAILS", set())

    with TestClient(main.app) as test_client:
        yield test_client

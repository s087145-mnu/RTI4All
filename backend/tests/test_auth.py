"""
Tests for the JWT-based authentication flow and the protection of
POST /api/requests. The AI answer step is monkey-patched to a stub so these
tests don't actually call Anthropic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


SIGNUP_PAYLOAD = {
    "email": "Alice@Example.MV",
    "password": "correct horse battery staple",
    "full_name": "Alice Tester",
    "present_address": "M. Test House, Male'",
    "phone_number": "+960 7771234",
    "id_card": "A123456",
}

VALID_RTI_PAYLOAD = {
    "department_id": "moccee",
    "subject": "Test query",
    "description": "Test description for the RTI request.",
}


@pytest.fixture
def client(monkeypatch):
    """Fresh TestClient with users reset, cache cleared, AI step stubbed."""
    import main
    from auth import reset_users

    reset_users()
    main._query_cache._store.clear()
    monkeypatch.setattr(main, "answer_request", lambda **kwargs: "stub AI answer")

    with TestClient(main.app) as test_client:
        yield test_client


def _signup(client: TestClient, **overrides) -> dict:
    payload = {**SIGNUP_PAYLOAD, **overrides}
    return client.post("/api/auth/signup", json=payload).json()


def _login(client: TestClient, **overrides) -> dict:
    payload = {
        "email": overrides.get("email", SIGNUP_PAYLOAD["email"]),
        "password": overrides.get("password", SIGNUP_PAYLOAD["password"]),
    }
    return client.post("/api/auth/login", json=payload).json()


# ── Signup ────────────────────────────────────────────────────────────────


def test_signup_returns_token_and_normalized_user(client):
    response = client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20
    # Emails are lowercased on storage; the rest of the profile is echoed back.
    user = body["user"]
    assert user["email"] == "alice@example.mv"
    assert user["full_name"] == "Alice Tester"
    assert user["present_address"] == "M. Test House, Male'"
    assert user["phone_number"] == "+960 7771234"
    assert user["id_card"] == "A123456"


def test_signup_rejects_missing_required_profile_field(client):
    """present_address and phone_number are required."""
    for missing in ("full_name", "present_address", "phone_number"):
        payload = {k: v for k, v in SIGNUP_PAYLOAD.items() if k != missing}
        # Re-key the email per attempt so duplicate-email rejection doesn't mask the test.
        payload["email"] = f"missing-{missing}@example.mv"
        response = client.post("/api/auth/signup", json=payload)
        assert response.status_code == 422, f"missing {missing} should be rejected"


def test_signup_accepts_missing_id_card(client):
    """id_card is optional — omitting it must succeed."""
    payload = {k: v for k, v in SIGNUP_PAYLOAD.items() if k != "id_card"}
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 201
    assert response.json()["user"]["id_card"] is None


def test_signup_rejects_whitespace_only_required_fields(client):
    payload = {**SIGNUP_PAYLOAD, "present_address": "   "}
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 422


def test_signup_duplicate_email_is_rejected(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD).raise_for_status()
    # Different casing on the email should still collide (normalized).
    dup = {**SIGNUP_PAYLOAD, "email": "ALICE@example.mv"}
    response = client.post("/api/auth/signup", json=dup)
    assert response.status_code == 409


def test_signup_rejects_invalid_email(client):
    response = client.post(
        "/api/auth/signup",
        json={**SIGNUP_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────


def test_login_with_valid_credentials_returns_token(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD).raise_for_status()
    response = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["access_token"], str)


def test_login_with_wrong_password_is_rejected(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD).raise_for_status()
    response = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "nope"},
    )
    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.mv", "password": "whatever"},
    )
    assert response.status_code == 401


# ── Protected endpoint: POST /api/requests ────────────────────────────────


def test_post_request_without_token_returns_401(client):
    response = client.post("/api/requests", json=VALID_RTI_PAYLOAD)
    assert response.status_code == 401


def test_post_request_with_malformed_token_returns_401(client):
    response = client.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert response.status_code == 401


def test_post_request_with_valid_token_succeeds(client):
    signup_body = _signup(client)
    token = signup_body["access_token"]

    response = client.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "Responded"
    assert created["response"] == "stub AI answer"


def test_post_request_uses_authenticated_user_identity(client):
    """Server must override citizen_name and email from the JWT, ignoring
    anything an attacker might try to slip into the body."""
    signup_body = _signup(client)
    token = signup_body["access_token"]

    impersonation_attempt = {
        **VALID_RTI_PAYLOAD,
        "citizen_name": "Mallory Attacker",
        "email": "mallory@evil.example",
    }
    response = client.post(
        "/api/requests",
        json=impersonation_attempt,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    created = response.json()
    assert created["citizen_name"] == "Alice Tester"
    assert created["email"] == "alice@example.mv"


def test_me_endpoint_returns_authenticated_user(client):
    signup_body = _signup(client)
    token = signup_body["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "email": "alice@example.mv",
        "full_name": "Alice Tester",
        "present_address": "M. Test House, Male'",
        "phone_number": "+960 7771234",
        "id_card": "A123456",
    }


def test_public_endpoints_remain_open(client):
    """GETs should not require auth — only POST /api/requests does."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/requests").status_code == 200
    assert client.get("/api/departments").status_code == 200
    assert client.get("/api/faqs").status_code == 200
    assert client.get("/api/stats").status_code == 200

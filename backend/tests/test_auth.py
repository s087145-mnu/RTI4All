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
    # New AI-drafted requests await admin approval before reaching "Responded".
    assert created["status"] == "Under Review"
    assert created["response"] == "stub AI draft"


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
        "is_admin": False,
    }


def test_public_endpoints_remain_open(client):
    """Public endpoints should not require auth."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/departments").status_code == 200
    assert client.get("/api/faqs").status_code == 200
    assert client.get("/api/stats").status_code == 200


def test_protected_endpoints_require_auth(client):
    """GET /api/requests and GET /api/requests/:id now require authentication."""
    assert client.get("/api/requests").status_code == 401
    # Create a request first with auth to test detail endpoint
    token = _signup_and_get_token(client, AISHATH_PROFILE)
    resp = client.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    request_id = resp.json()["id"]
    # Now test without auth
    assert client.get(f"/api/requests/{request_id}").status_code == 401


def test_users_can_only_see_their_own_requests(client):
    """Users should only see their own requests, not other users' requests."""
    # Create two users
    token1 = _signup_and_get_token(client, AISHATH_PROFILE)
    token2_profile = {
        "email": "mohamed@example.mv",
        "password": "another-password",
        "full_name": "Mohamed Ali",
        "present_address": "G. Morning Star, Male'",
        "phone_number": "+960 9998888",
    }
    token2 = _signup_and_get_token(client, token2_profile)

    # User 1 creates a request
    resp1 = client.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers={"Authorization": f"Bearer {token1}"},
    )
    request1_id = resp1.json()["id"]

    # User 2 creates a request
    resp2 = client.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Climate adaptation programs",
            "description": "Information about climate adaptation programs.",
        },
        headers={"Authorization": f"Bearer {token2}"},
    )
    request2_id = resp2.json()["id"]

    # User 1 should only see their own request
    user1_requests = client.get(
        "/api/requests",
        headers={"Authorization": f"Bearer {token1}"},
    ).json()
    assert len(user1_requests) == 1
    assert user1_requests[0]["id"] == request1_id
    assert user1_requests[0]["email"] == AISHATH_PROFILE["email"].lower()

    # User 2 should only see their own request
    user2_requests = client.get(
        "/api/requests",
        headers={"Authorization": f"Bearer {token2}"},
    ).json()
    assert len(user2_requests) == 1
    assert user2_requests[0]["id"] == request2_id
    assert user2_requests[0]["email"] == token2_profile["email"].lower()

    # User 1 should not be able to access User 2's request
    resp = client.get(
        f"/api/requests/{request2_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()

    # User 2 should not be able to access User 1's request
    resp = client.get(
        f"/api/requests/{request1_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()

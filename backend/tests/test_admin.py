"""
Tests for the admin (human-in-the-loop) workflow:

  - ADMIN_EMAILS bootstrap promotes matching users to is_admin
  - Non-admin tokens are rejected (403) from admin endpoints
  - The admin can list the Under-Review queue
  - The admin can approve / edit / reject; reviewed_by + reviewed_at are stamped
  - The citizen's profile is snapshotted onto requests at filing time
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN_EMAIL = "officer@gov.mv"
ADMIN_PASSWORD = "super-secret-pass"
ADMIN_PROFILE = {
    "email": ADMIN_EMAIL,
    "password": ADMIN_PASSWORD,
    "full_name": "Officer Hassan",
    "present_address": "Ministry HQ, Male'",
    "phone_number": "+960 3001000",
}

CITIZEN_EMAIL = "citizen@example.mv"
CITIZEN_PASSWORD = "another-pass"
CITIZEN_PROFILE = {
    "email": CITIZEN_EMAIL,
    "password": CITIZEN_PASSWORD,
    "full_name": "Aishath Hassan",
    "present_address": "H. Sunset, Hithadhoo, Addu City",
    "phone_number": "+960 7777777",
    "id_card": "A099887",
}

VALID_RTI_PAYLOAD = {
    "department_id": "moccee",
    "subject": "Coral monitoring 2024",
    "description": "Please share the 2024 coral reef monitoring summary.",
}


@pytest.fixture
def admin_setup(client, monkeypatch):
    """Configure ADMIN_EMAILS so ADMIN_EMAIL is recognised at signup."""
    import auth

    monkeypatch.setattr(auth, "_ADMIN_EMAILS", {ADMIN_EMAIL})
    return client


def _signup(client: TestClient, profile: dict) -> str:
    body = client.post("/api/auth/signup", json=profile).json()
    return body["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Bootstrap ────────────────────────────────────────────────────────────


def test_admin_email_bootstraps_is_admin_at_signup(admin_setup):
    body = admin_setup.post("/api/auth/signup", json=ADMIN_PROFILE).json()
    assert body["user"]["is_admin"] is True


def test_non_admin_email_is_not_promoted(admin_setup):
    body = admin_setup.post("/api/auth/signup", json=CITIZEN_PROFILE).json()
    assert body["user"]["is_admin"] is False


def test_admin_flag_appears_on_me_endpoint(admin_setup):
    token = _signup(admin_setup, ADMIN_PROFILE)
    me = admin_setup.get("/api/auth/me", headers=_bearer(token)).json()
    assert me["is_admin"] is True


# ── Authorization gating ─────────────────────────────────────────────────


def test_admin_endpoints_reject_unauthenticated(client):
    assert client.get("/api/admin/requests/pending").status_code == 401
    assert client.patch("/api/admin/requests/RTI-2024-0001", json={}).status_code == 401


def test_admin_endpoints_reject_non_admin_token(admin_setup):
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)
    assert (
        admin_setup.get(
            "/api/admin/requests/pending", headers=_bearer(citizen_token)
        ).status_code
        == 403
    )
    assert (
        admin_setup.patch(
            "/api/admin/requests/RTI-2024-0001",
            json={"response": "x"},
            headers=_bearer(citizen_token),
        ).status_code
        == 403
    )


# ── Lifecycle: filing → Under Review → admin action ──────────────────────


def test_filing_a_request_lands_in_under_review_and_snapshots_profile(admin_setup):
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)
    created = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()
    assert created["status"] == "Under Review"
    # Profile fields snapshotted from the user record.
    assert created["citizen_name"] == CITIZEN_PROFILE["full_name"]
    assert created["citizen_phone"] == CITIZEN_PROFILE["phone_number"]
    assert created["citizen_address"] == CITIZEN_PROFILE["present_address"]
    assert created["citizen_id_card"] == CITIZEN_PROFILE["id_card"]


def test_admin_pending_inbox_contains_under_review_requests(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)

    filed = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()

    pending = admin_setup.get(
        "/api/admin/requests/pending", headers=_bearer(admin_token)
    )
    assert pending.status_code == 200
    ids = [r["id"] for r in pending.json()]
    assert filed["id"] in ids
    for r in pending.json():
        assert r["status"] == "Under Review"


def test_admin_can_edit_and_approve_a_request(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)
    filed = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()

    edited = "Officer-edited final response."
    res = admin_setup.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"response": edited, "status": "Responded"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "Responded"
    assert updated["response"] == edited
    assert updated["reviewed_by"] == ADMIN_EMAIL
    assert updated["reviewed_at"]
    assert updated["date_updated"] == updated["reviewed_at"]


def test_admin_can_reject_with_reason(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)
    filed = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()

    reason = "Exempt under section 8(1)(j)."
    res = admin_setup.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"status": "Rejected", "rejection_reason": reason},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "Rejected"
    assert updated["rejection_reason"] == reason
    assert updated["reviewed_by"] == ADMIN_EMAIL


def test_admin_patch_with_empty_body_is_rejected(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)
    filed = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()

    res = admin_setup.patch(
        f"/api/admin/requests/{filed['id']}",
        json={},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 400


def test_admin_patch_rejects_invalid_status_value(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen_token = _signup(admin_setup, CITIZEN_PROFILE)

    filed = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen_token),
    ).json()

    response = admin_setup.patch(
        f"/api/admin/requests/{filed['id']}",
        json={"status": "Junk Status Value"},
        headers=_bearer(admin_token),
    )
    assert response.status_code == 422


def test_admin_can_see_all_requests_but_citizens_only_their_own(admin_setup):
    """Admins can see all requests; regular users only their own."""
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    citizen1_token = _signup(admin_setup, CITIZEN_PROFILE)
    citizen2_profile = {
        "email": "another-citizen@example.mv",
        "password": "pass123",
        "full_name": "Mohamed Ali",
        "present_address": "G. Morning Star, Male'",
        "phone_number": "+960 9998888",
    }
    citizen2_token = _signup(admin_setup, citizen2_profile)

    # Citizen 1 creates a request
    req1 = admin_setup.post(
        "/api/requests",
        json=VALID_RTI_PAYLOAD,
        headers=_bearer(citizen1_token),
    ).json()

    # Citizen 2 creates a request
    req2 = admin_setup.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Climate data",
            "description": "Climate change data for 2024.",
        },
        headers=_bearer(citizen2_token),
    ).json()

    # Admin creates a request
    req3 = admin_setup.post(
        "/api/requests",
        json={
            "department_id": "moccee",
            "subject": "Admin test request",
            "description": "Testing admin access.",
        },
        headers=_bearer(admin_token),
    ).json()

    # Admin should see all 3 requests
    admin_requests = admin_setup.get(
        "/api/requests",
        headers=_bearer(admin_token),
    ).json()
    assert len(admin_requests) == 3
    request_ids = {r["id"] for r in admin_requests}
    assert req1["id"] in request_ids
    assert req2["id"] in request_ids
    assert req3["id"] in request_ids

    # Citizen 1 should only see their own request
    citizen1_requests = admin_setup.get(
        "/api/requests",
        headers=_bearer(citizen1_token),
    ).json()
    assert len(citizen1_requests) == 1
    assert citizen1_requests[0]["id"] == req1["id"]

    # Citizen 2 should only see their own request
    citizen2_requests = admin_setup.get(
        "/api/requests",
        headers=_bearer(citizen2_token),
    ).json()
    assert len(citizen2_requests) == 1
    assert citizen2_requests[0]["id"] == req2["id"]

    # Admin can access any specific request
    assert (
        admin_setup.get(
            f"/api/requests/{req1['id']}", headers=_bearer(admin_token)
        ).status_code
        == 200
    )
    assert (
        admin_setup.get(
            f"/api/requests/{req2['id']}", headers=_bearer(admin_token)
        ).status_code
        == 200
    )
    assert (
        admin_setup.get(
            f"/api/requests/{req3['id']}", headers=_bearer(admin_token)
        ).status_code
        == 200
    )

    # Citizen 1 cannot access Citizen 2's request
    resp = admin_setup.get(
        f"/api/requests/{req2['id']}", headers=_bearer(citizen1_token)
    )
    assert resp.status_code == 403

    # Citizen 2 cannot access Citizen 1's request
    resp = admin_setup.get(
        f"/api/requests/{req1['id']}", headers=_bearer(citizen2_token)
    )
    assert resp.status_code == 403


def test_admin_patch_on_unknown_request_returns_404(admin_setup):
    admin_token = _signup(admin_setup, ADMIN_PROFILE)
    res = admin_setup.patch(
        "/api/admin/requests/RTI-DOES-NOT-EXIST",
        json={"response": "x"},
        headers=_bearer(admin_token),
    )
    assert res.status_code == 404

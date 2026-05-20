"""
Authentication for the RTI4All backend.

Standard JWT (HS256) over an in-memory user store. Users sign up with email +
password; bcrypt hashes are stored, never the plaintext. Successful signup or
login returns a bearer token that callers attach to subsequent requests.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY = timedelta(hours=24)

_DEV_FALLBACK_SECRET = "dev-only-insecure-secret-do-not-use-in-production"


def _load_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        log.warning(
            "JWT_SECRET_KEY not set; using insecure dev fallback. "
            "Set JWT_SECRET_KEY in production."
        )
        return _DEV_FALLBACK_SECRET
    return secret


_SECRET_KEY = _load_secret()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    present_address: str
    phone_number: str
    id_card: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    email: EmailStr
    full_name: str
    present_address: str
    phone_number: str
    id_card: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


# ---------------------------------------------------------------------------
# In-memory user store
# ---------------------------------------------------------------------------


class _UserRecord(BaseModel):
    email: EmailStr
    full_name: str
    present_address: str
    phone_number: str
    id_card: Optional[str] = None
    password_hash: str


_users: dict[str, _UserRecord] = {}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def reset_users() -> None:
    """Clear the user store. Used by tests."""
    _users.clear()


def _to_public(record: _UserRecord) -> UserPublic:
    return UserPublic(
        email=record.email,
        full_name=record.full_name,
        present_address=record.present_address,
        phone_number=record.phone_number,
        id_card=record.id_card,
    )


def create_user(
    *,
    email: str,
    password: str,
    full_name: str,
    present_address: str,
    phone_number: str,
    id_card: Optional[str] = None,
) -> UserPublic:
    key = _normalize_email(email)
    if key in _users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    # Trim whitespace so empty fields ("   ") don't sneak past required validation.
    full_name = full_name.strip()
    present_address = present_address.strip()
    phone_number = phone_number.strip()
    id_card_clean = id_card.strip() if id_card else None
    if not full_name or not present_address or not phone_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name, present address, and phone number must not be empty.",
        )
    record = _UserRecord(
        email=key,
        full_name=full_name,
        present_address=present_address,
        phone_number=phone_number,
        id_card=id_card_clean or None,
        password_hash=_pwd_context.hash(password),
    )
    _users[key] = record
    return _to_public(record)


def authenticate_user(*, email: str, password: str) -> UserPublic:
    record = _users.get(_normalize_email(email))
    # Run the verify even when the user doesn't exist to keep timing similar.
    expected_hash = record.password_hash if record else _pwd_context.hash(secrets.token_urlsafe(16))
    ok = _pwd_context.verify(password, expected_hash)
    if not record or not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return _to_public(record)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(user: UserPublic) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.email,
        "name": user.full_name,
        "iat": int(now.timestamp()),
        "exp": int((now + _JWT_EXPIRY).timestamp()),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(_oauth2_scheme)) -> UserPublic:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        raise _CREDENTIALS_EXC from None
    email: Optional[str] = payload.get("sub")
    name: Optional[str] = payload.get("name")
    if not email or not name:
        raise _CREDENTIALS_EXC
    record = _users.get(_normalize_email(email))
    if not record:
        # Token references a user that no longer exists (e.g. after a restart
        # with the in-memory store). Reject the token rather than silently
        # accept stale identities.
        raise _CREDENTIALS_EXC
    return _to_public(record)

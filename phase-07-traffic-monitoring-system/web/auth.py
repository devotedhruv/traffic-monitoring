"""Password authentication and revocable cookie sessions for TrafficOps."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from config.settings import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_SESSION_HOURS
from src.database import (
    create_auth_session,
    create_user,
    delete_auth_session,
    get_user_by_session,
    get_user_credentials,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


class SignUpRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Name must contain at least 2 characters")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(cleaned):
            raise ValueError("Enter a valid email address")
        return cleaned


class SignInRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthResponse(BaseModel):
    user: dict[str, Any]


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        parameters = (int(n), int(r), int(p))
        if algorithm != "scrypt" or parameters != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_decode(salt), n=parameters[0], r=parameters[1], p=parameters[2], dklen=32
        )
        return hmac.compare_digest(actual, _decode(expected))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _set_session(response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=AUTH_SESSION_HOURS)
    create_auth_session(user_id, _token_hash(token), expires_at.isoformat().replace("+00:00", "Z"))
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def current_user_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    return get_user_by_session(_token_hash(token))


def require_user(
    session_token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    user = current_user_from_token(session_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(require_user)]


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, response: Response):
    user = create_user(payload.name, payload.email, hash_password(payload.password))
    if user is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    _set_session(response, user["id"])
    return {"user": user}


@router.post("/signin", response_model=AuthResponse)
def signin(payload: SignInRequest, response: Response):
    credentials = get_user_credentials(payload.email)
    if credentials is None or not verify_password(payload.password, credentials["passwordHash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")
    user = {key: value for key, value in credentials.items() if key != "passwordHash"}
    _set_session(response, user["id"])
    return {"user": user}


@router.get("/me", response_model=AuthResponse)
def me(user: CurrentUser):
    return {"user": user}


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
def signout(request: Request, response: Response):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        delete_auth_session(_token_hash(token))
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", secure=AUTH_COOKIE_SECURE, httponly=True, samesite="lax")

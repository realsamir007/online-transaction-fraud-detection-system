from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hmac
import os
from typing import Any

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

API_KEY_HEADER_NAME = "X-API-Key"
AUTHORIZATION_HEADER_NAME = "Authorization"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
_bearer_header = HTTPBearer(auto_error=False)


class AuthMode(str, Enum):
    API_KEY = "api_key"
    JWT = "jwt"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class AuthSettings:
    mode: AuthMode
    api_keys: tuple[str, ...]

    @property
    def allow_api_key(self) -> bool:
        return self.mode in (AuthMode.API_KEY, AuthMode.HYBRID)

    @property
    def allow_jwt(self) -> bool:
        return self.mode in (AuthMode.JWT, AuthMode.HYBRID)


@dataclass(frozen=True)
class AuthContext:
    auth_method: str
    principal: str


class SupabaseUserTokenVerifier:
    def __init__(self, client: Client) -> None:
        self._client = client

    def verify_access_token(self, access_token: str) -> dict[str, Any]:
        try:
            response = self._client.auth.get_user(access_token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.") from exc

        user = getattr(response, "user", None)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.")

        if hasattr(user, "model_dump"):
            user_payload = user.model_dump()
        elif isinstance(user, dict):
            user_payload = user
        else:
            user_payload = {"id": getattr(user, "id", None)}

        if not user_payload.get("id"):
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.")

        return user_payload


def _parse_api_keys(raw_api_keys: str) -> tuple[str, ...]:
    if not raw_api_keys:
        return tuple()
    return tuple(dict.fromkeys(key.strip() for key in raw_api_keys.split(",") if key.strip()))


def _parse_auth_mode(raw_mode: str) -> AuthMode:
    normalized = raw_mode.strip().lower()
    try:
        return AuthMode(normalized)
    except ValueError as exc:
        raise ValueError("AUTH_MODE must be one of: api_key, jwt, hybrid.") from exc


def load_auth_settings() -> AuthSettings:
    raw_mode = os.getenv("AUTH_MODE", AuthMode.HYBRID.value)
    mode = _parse_auth_mode(raw_mode)
    api_keys = _parse_api_keys(os.getenv("PREDICTION_API_KEYS", "").strip())

    if mode in (AuthMode.API_KEY, AuthMode.HYBRID) and not api_keys:
        raise ValueError(
            "PREDICTION_API_KEYS is required when AUTH_MODE includes api_key."
        )

    return AuthSettings(mode=mode, api_keys=api_keys)


def authenticate_prediction_request(
    request: Request,
    api_key: str | None = Security(_api_key_header),
    bearer_credentials: HTTPAuthorizationCredentials | None = Security(_bearer_header),
) -> AuthContext:
    auth_settings: AuthSettings | None = getattr(request.app.state, "auth_settings", None)
    if auth_settings is None:
        raise HTTPException(status_code=500, detail="Authentication is not configured.")

    if auth_settings.allow_api_key and api_key:
        if any(hmac.compare_digest(api_key, configured_key) for configured_key in auth_settings.api_keys):
            auth_context = AuthContext(auth_method="api_key", principal="api_key_client")
            request.state.auth_context = auth_context
            return auth_context

    if auth_settings.allow_jwt and bearer_credentials:
        if bearer_credentials.scheme.lower() == "bearer" and bearer_credentials.credentials:
            verifier: SupabaseUserTokenVerifier | None = getattr(request.app.state, "user_token_verifier", None)
            if verifier is None:
                raise HTTPException(status_code=500, detail="JWT verification is not configured.")

            user_payload = verifier.verify_access_token(bearer_credentials.credentials)
            auth_context = AuthContext(auth_method="jwt", principal=str(user_payload["id"]))
            request.state.auth_context = auth_context
            return auth_context

    if auth_settings.allow_api_key and auth_settings.allow_jwt:
        detail = "Invalid or missing credentials. Provide X-API-Key or Bearer token."
    elif auth_settings.allow_api_key:
        detail = "Invalid or missing API key."
    else:
        detail = "Invalid or missing Bearer token."

    raise HTTPException(status_code=401, detail=detail)

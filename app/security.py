from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def load_api_keys() -> tuple[str, ...]:
    raw_api_keys = os.getenv("PREDICTION_API_KEYS", "").strip()
    if not raw_api_keys:
        raise ValueError(
            "PREDICTION_API_KEYS is required. Provide one or more comma-separated API keys."
        )

    api_keys = tuple(dict.fromkeys(key.strip() for key in raw_api_keys.split(",") if key.strip()))
    if not api_keys:
        raise ValueError(
            "PREDICTION_API_KEYS is required. Provide one or more comma-separated API keys."
        )

    return api_keys


def require_prediction_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    configured_api_keys: tuple[str, ...] | None = getattr(request.app.state, "prediction_api_keys", None)
    if not configured_api_keys:
        raise HTTPException(status_code=500, detail="Authentication is not configured.")

    if api_key and any(hmac.compare_digest(api_key, configured_key) for configured_key in configured_api_keys):
        return

    raise HTTPException(status_code=401, detail="Invalid or missing API key.")


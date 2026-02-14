from __future__ import annotations

import hashlib
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, Request

from app.security import API_KEY_HEADER_NAME, AUTHORIZATION_HEADER_NAME


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool = True
    requests: int = 60
    window_seconds: int = 60

    def __post_init__(self) -> None:
        if self.requests <= 0:
            raise ValueError("RATE_LIMIT_REQUESTS must be greater than 0.")
        if self.window_seconds <= 0:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be greater than 0.")


class InMemoryRateLimiter:
    def __init__(self, settings: RateLimitSettings, clock: callable = time.time) -> None:
        self._settings = settings
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check_and_consume(self, key: str) -> tuple[bool, int]:
        now = self._clock()
        window_start = now - self._settings.window_seconds

        with self._lock:
            events = self._events[key]
            while events and events[0] <= window_start:
                events.popleft()

            if len(events) >= self._settings.requests:
                retry_after = max(
                    1,
                    math.ceil(self._settings.window_seconds - (now - events[0])),
                )
                return False, retry_after

            events.append(now)
            return True, 0


def _resolve_identity_key(request: Request) -> str:
    api_key = request.headers.get(API_KEY_HEADER_NAME, "").strip()
    if api_key:
        return "api_key:" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]

    auth_header = request.headers.get(AUTHORIZATION_HEADER_NAME, "").strip()
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()
        if bearer_token:
            return "bearer:" + hashlib.sha256(bearer_token.encode("utf-8")).hexdigest()[:16]

    return "anonymous"


def enforce_prediction_rate_limit(request: Request) -> None:
    settings: RateLimitSettings | None = getattr(request.app.state, "rate_limit_settings", None)
    if not settings or not settings.enabled:
        return

    rate_limiter: InMemoryRateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if rate_limiter is None:
        raise HTTPException(status_code=500, detail="Rate limiter is not configured.")

    client_ip = request.client.host if request.client else "unknown"
    identity_key = _resolve_identity_key(request)
    limit_key = f"{client_ip}:{identity_key}"

    allowed, retry_after = rate_limiter.check_and_consume(limit_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(retry_after)},
        )

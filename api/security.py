from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Set

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from common.utils.helpers import env

API_KEY_HEADER = "X-API-Key"
_api_key_header = APIKeyHeader(
    name=API_KEY_HEADER,
    auto_error=False,
    description="API key used to authorize access to protected endpoints.",
)

RATE_LIMIT_WINDOW_SECONDS = int(env("AIG_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(env("AIG_RATE_LIMIT_MAX_REQUESTS", "60"))

_rate_limit_state: Dict[str, Deque[float]] = {}


def _valid_keys() -> Set[str]:
    keys = env("AIG_API_KEYS", "dev-secret")
    return {k.strip() for k in keys.split(",") if k.strip()}


def _enforce_rate_limit(identifier: str, *, now: float | None = None) -> None:
    now = now or time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _rate_limit_state.setdefault(identifier, deque())

    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before trying again.",
        )

    timestamps.append(now)


def require_api_key(request: Request, api_key: str | None = Security(_api_key_header)) -> str:
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key.",
            headers={"WWW-Authenticate": "API Key"},
        )

    if api_key not in _valid_keys():
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "API Key"},
        )

    _enforce_rate_limit(identifier=api_key)
    request.state.authenticated_api_key = api_key
    return api_key


def security_responses() -> dict[int, dict[str, str]]:
    return {
        401: {"description": "Unauthorized: missing or malformed API key."},
        403: {"description": "Forbidden: invalid API key."},
        429: {"description": "Too Many Requests: rate limit exceeded."},
    }

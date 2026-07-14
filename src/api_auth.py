"""Central bearer-token authentication for the dashboard API."""

from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

AUTH_MODE_ENV = "INDEXPILOT_API_AUTH_MODE"
AUTH_TOKEN_ENV = "INDEXPILOT_API_TOKEN"
PUBLIC_PATHS = {"/"}


def get_api_auth_mode() -> str:
    """Return the explicit auth mode; hosted-safe behavior is the default."""
    return os.getenv(AUTH_MODE_ENV, "required").strip().lower()


def api_auth_is_configured() -> bool:
    return get_api_auth_mode() == "required" and bool(os.getenv(AUTH_TOKEN_ENV, ""))


def check_bearer_token(authorization: str | None) -> tuple[int, str] | None:
    """Validate one Authorization header without logging secret material."""
    mode = get_api_auth_mode()
    if mode == "disabled":
        return None
    if mode != "required":
        return 503, "api_auth_mode_invalid"

    expected = os.getenv(AUTH_TOKEN_ENV, "")
    if not expected:
        return 503, "api_auth_not_configured"
    if not authorization:
        return 401, "bearer_token_required"

    scheme, separator, supplied = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not supplied:
        return 401, "bearer_token_required"
    if not secrets.compare_digest(supplied, expected):
        return 401, "invalid_bearer_token"
    return None


async def enforce_api_auth(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Protect every API/docs route while keeping one minimal liveness route public."""
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    failure = check_bearer_token(request.headers.get("authorization"))
    if failure is None:
        return await call_next(request)

    status_code, detail = failure
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)

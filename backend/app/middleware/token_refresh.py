import time
import logging
from typing import Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.schemas import TokenData
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)

# Refresh if token expires within this many seconds
TOKEN_REFRESH_THRESHOLD = 300  # 5 minutes

# Routes that bypass token checking
AUTH_ROUTE_PREFIXES = ("/auth/", "/docs", "/openapi.json")


class TokenRefreshMiddleware:
    """Middleware that checks token validity and refreshes if near expiry."""

    def __init__(
        self,
        token_repository: TokenRepository,
        renew_token_fn: Optional[Callable[[str], TokenData]] = None,
    ):
        self._token_repository = token_repository
        self._renew_token_fn = renew_token_fn

    async def __call__(self, request: Request, call_next):
        # Skip auth-related routes
        if any(request.url.path.startswith(prefix) for prefix in AUTH_ROUTE_PREFIXES):
            return await call_next(request)

        tokens = self._token_repository.load()

        # No tokens at all — require auth
        if tokens is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated", "re_auth_required": True},
            )

        # Check if token needs refresh
        time_until_expiry = tokens.expires_at - time.time()

        if time_until_expiry < TOKEN_REFRESH_THRESHOLD:
            # Try to refresh
            if self._renew_token_fn is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token expired, no renewal available", "re_auth_required": True},
                )
            try:
                new_tokens = self._renew_token_fn(tokens.refresh_token)
                self._token_repository.save(new_tokens)
            except Exception as e:
                _LOGGER.warning(f"Token refresh failed: {e}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token refresh failed", "re_auth_required": True},
                )

        return await call_next(request)

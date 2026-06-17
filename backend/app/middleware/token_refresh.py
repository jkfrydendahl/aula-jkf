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
AUTH_ROUTE_PREFIXES = ("/auth/", "/app-auth/", "/health", "/docs", "/openapi.json")


class TokenRefreshMiddleware:
    """Middleware that checks token validity and refreshes if near expiry."""

    def __init__(
        self,
        app,
        token_repository: TokenRepository,
        renew_token_fn: Optional[Callable[[str], TokenData]] = None,
    ):
        self.app = app
        self._token_repository = token_repository
        self._renew_token_fn = renew_token_fn

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse as StarletteJSONResponse

        request = Request(scope, receive)

        # Skip auth-related routes
        if any(request.url.path.startswith(prefix) for prefix in AUTH_ROUTE_PREFIXES):
            await self.app(scope, receive, send)
            return

        tokens = self._token_repository.load()

        # No tokens at all — require auth
        if tokens is None:
            response = StarletteJSONResponse(
                status_code=401,
                content={"detail": "Not authenticated", "re_auth_required": True},
            )
            await response(scope, receive, send)
            return

        # Check if token needs refresh
        time_until_expiry = tokens.expires_at - time.time()

        if time_until_expiry < TOKEN_REFRESH_THRESHOLD:
            # Try to refresh
            if self._renew_token_fn is None:
                response = StarletteJSONResponse(
                    status_code=401,
                    content={"detail": "Token expired, no renewal available", "re_auth_required": True},
                )
                await response(scope, receive, send)
                return
            try:
                new_tokens = self._renew_token_fn(tokens.refresh_token)
                self._token_repository.save(new_tokens)
            except Exception as e:
                _LOGGER.warning(f"Token refresh failed: {e}")
                response = StarletteJSONResponse(
                    status_code=401,
                    content={"detail": "Token refresh failed", "re_auth_required": True},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)

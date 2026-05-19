import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.models.schemas import TokenData
from app.repositories.token_repository import FileTokenRepository
from app.middleware.token_refresh import TokenRefreshMiddleware


def _build_app_with_middleware(token_repo, renew_fn=None):
    """Create a test app with token refresh middleware and a protected endpoint."""
    app = FastAPI()

    middleware = TokenRefreshMiddleware(
        token_repository=token_repo,
        renew_token_fn=renew_fn,
    )
    app.middleware("http")(middleware)

    @app.get("/children")
    async def get_children():
        return {"children": []}

    @app.get("/auth/start")
    async def auth_start():
        return {"flow_id": "test"}

    return app


class TestTokenAutoRefresh:
    """Scenario 5: Token auto-refresh before expiry."""

    def test_refreshes_near_expired_token(self, tmp_path):
        """
        [SCENARIO] Token is near expiry
        [GIVEN] Token expires in 2 minutes (within 5-min threshold)
        [WHEN] A request to a protected endpoint is made
        [THEN] Middleware refreshes the token and request succeeds
        """
        store_path = str(tmp_path / "tokens.json")
        token_repo = FileTokenRepository(store_path)

        # Save a near-expired token (expires in 2 minutes)
        near_expired = TokenData(
            access_token="old-access",
            refresh_token="valid-refresh",
            expires_at=time.time() + 120,  # 2 min from now
        )
        token_repo.save(near_expired)

        # Mock renew function that returns new tokens
        def mock_renew(refresh_token: str) -> TokenData:
            return TokenData(
                access_token="new-access",
                refresh_token="new-refresh",
                expires_at=time.time() + 3600,
            )

        app = _build_app_with_middleware(token_repo, renew_fn=mock_renew)
        client = TestClient(app)

        resp = client.get("/children")
        assert resp.status_code == 200

        # Token should have been refreshed and persisted
        loaded = token_repo.load()
        assert loaded.access_token == "new-access"
        assert loaded.refresh_token == "new-refresh"

    def test_skips_refresh_for_valid_token(self, tmp_path):
        """
        [SCENARIO] Token is still valid (far from expiry)
        [GIVEN] Token expires in 1 hour
        [WHEN] A request is made
        [THEN] No refresh occurs, request proceeds normally
        """
        store_path = str(tmp_path / "tokens.json")
        token_repo = FileTokenRepository(store_path)

        valid_token = TokenData(
            access_token="valid-access",
            refresh_token="valid-refresh",
            expires_at=time.time() + 3600,  # 1 hour from now
        )
        token_repo.save(valid_token)

        mock_renew = MagicMock()
        app = _build_app_with_middleware(token_repo, renew_fn=mock_renew)
        client = TestClient(app)

        resp = client.get("/children")
        assert resp.status_code == 200
        mock_renew.assert_not_called()

    def test_skips_middleware_for_auth_routes(self, tmp_path):
        """
        [SCENARIO] Auth routes bypass token check
        [GIVEN] No tokens exist
        [WHEN] A request to /auth/start is made
        [THEN] Request proceeds without 401
        """
        store_path = str(tmp_path / "tokens.json")
        token_repo = FileTokenRepository(store_path)
        # No tokens saved

        app = _build_app_with_middleware(token_repo, renew_fn=None)
        client = TestClient(app)

        resp = client.get("/auth/start")
        assert resp.status_code == 200


class TestRefreshTokenExpired:
    """Scenario 6: Refresh token also expired."""

    def test_returns_401_when_refresh_fails(self, tmp_path):
        """
        [SCENARIO] Both tokens are expired
        [GIVEN] Token is expired and refresh also fails
        [WHEN] A request to a protected endpoint is made
        [THEN] 401 with re_auth_required
        """
        store_path = str(tmp_path / "tokens.json")
        token_repo = FileTokenRepository(store_path)

        expired = TokenData(
            access_token="expired-access",
            refresh_token="expired-refresh",
            expires_at=time.time() - 100,  # Already expired
        )
        token_repo.save(expired)

        # Renew function that fails (simulates expired refresh token)
        def mock_renew_fails(refresh_token: str) -> TokenData:
            raise Exception("Refresh token expired")

        app = _build_app_with_middleware(token_repo, renew_fn=mock_renew_fails)
        client = TestClient(app)

        resp = client.get("/children")
        assert resp.status_code == 401
        assert resp.json()["re_auth_required"] is True

    def test_returns_401_when_no_tokens_exist(self, tmp_path):
        """
        [SCENARIO] No tokens at all
        [GIVEN] No tokens have been saved
        [WHEN] A request to a protected endpoint is made
        [THEN] 401 with re_auth_required
        """
        store_path = str(tmp_path / "tokens.json")
        token_repo = FileTokenRepository(store_path)
        # No tokens saved

        app = _build_app_with_middleware(token_repo, renew_fn=None)
        client = TestClient(app)

        resp = client.get("/children")
        assert resp.status_code == 401
        assert resp.json()["re_auth_required"] is True

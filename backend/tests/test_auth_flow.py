import uuid
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.schemas import AuthFlowStatus
from app.repositories.token_repository import FileTokenRepository
from app.services.auth_service import AuthService
from app.routers.auth_router import create_auth_router


def _build_test_app(auth_service):
    """Create a FastAPI test app with auth router wired to the given service."""
    from app.settings import Settings
    settings = Settings(
        token_store_path="dummy",
        push_store_path="dummy",
    )
    app = create_app(settings)
    router = create_auth_router(auth_service)
    app.include_router(router)
    return app


class TestAuthFlowHappyPath:
    """Scenario 1: Auth flow start → poll → complete."""

    def test_start_and_poll_until_complete(self, tmp_path):
        """
        [SCENARIO] Full auth happy path
        [GIVEN] A valid MitID username and mocked login client
        [WHEN] POST /auth/start, then poll GET /auth/status/{flow_id}
        [THEN] Flow completes with tokens persisted
        """
        token_repo = FileTokenRepository(str(tmp_path / "tokens.json"))
        mock_login_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_login_client_class.return_value = mock_client_instance
        mock_client_instance.authenticate.return_value = {
            "success": True,
            "tokens": {
                "access_token": "acc-test",
                "refresh_token": "ref-test",
                "expires_in": 3600,
            },
            "profile_data": {"name": "Test User"},
        }

        auth_service = AuthService(
            token_repository=token_repo,
            login_client_class=mock_login_client_class,
        )
        app = _build_test_app(auth_service)
        client = TestClient(app)

        # Start auth flow
        resp = client.post("/auth/start", json={"username": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert "flow_id" in data
        flow_id = data["flow_id"]

        # Wait for background auth to finish
        auth_service._wait_for_flow(flow_id, timeout=5)

        # Poll status
        resp = client.get(f"/auth/status/{flow_id}")
        assert resp.status_code == 200
        status = resp.json()
        assert status["status"] == AuthFlowStatus.COMPLETE

        # Tokens should be persisted
        loaded = token_repo.load()
        assert loaded is not None
        assert loaded.access_token == "acc-test"


class TestAuthFlowIdentitySelection:
    """Scenario 2: Auth flow with identity selection required."""

    def test_identity_selection_flow(self, tmp_path):
        """
        [SCENARIO] Multiple identities detected
        [GIVEN] MitID login returns identity_selection status
        [WHEN] User selects an identity via POST /auth/select-identity
        [THEN] Flow completes after selection
        """
        token_repo = FileTokenRepository(str(tmp_path / "tokens.json"))
        auth_service = AuthService(
            token_repository=token_repo,
            login_client_class=MagicMock(),
        )

        # Simulate a flow that's waiting for identity selection
        flow_id = "test-identity-flow"
        auth_service._flows[flow_id] = {
            "status": AuthFlowStatus.IDENTITY_SELECTION,
            "identities": [
                {"id": 1, "name": "Parent"},
                {"id": 2, "name": "Guardian"},
            ],
            "identity_event": threading.Event(),
            "selected_identity": None,
        }

        app = _build_test_app(auth_service)
        client = TestClient(app)

        # Poll should show identity_selection
        resp = client.get(f"/auth/status/{flow_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == AuthFlowStatus.IDENTITY_SELECTION
        assert len(resp.json()["identities"]) == 2

        # Select identity
        resp = client.post(
            f"/auth/select-identity/{flow_id}",
            json={"identity_index": 1},
        )
        assert resp.status_code == 200

        # Verify the selection was recorded
        assert auth_service._flows[flow_id]["selected_identity"] == 1


class TestAuthFlowTimeout:
    """Scenario 3: MitID timeout."""

    def test_timeout_returns_error(self, tmp_path):
        """
        [SCENARIO] MitID auth times out
        [GIVEN] Login client raises a timeout exception
        [WHEN] Polling the flow status
        [THEN] Status is error with timeout message
        """
        token_repo = FileTokenRepository(str(tmp_path / "tokens.json"))
        mock_login_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_login_client_class.return_value = mock_client_instance
        mock_client_instance.authenticate.side_effect = TimeoutError("MitID timeout")

        auth_service = AuthService(
            token_repository=token_repo,
            login_client_class=mock_login_client_class,
        )
        app = _build_test_app(auth_service)
        client = TestClient(app)

        resp = client.post("/auth/start", json={"username": "testuser"})
        flow_id = resp.json()["flow_id"]

        auth_service._wait_for_flow(flow_id, timeout=5)

        resp = client.get(f"/auth/status/{flow_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == AuthFlowStatus.ERROR
        assert "timeout" in resp.json()["error"].lower()


class TestAuthFlowInvalidCredentials:
    """Scenario 4: Invalid credentials."""

    def test_invalid_credentials_returns_error(self, tmp_path):
        """
        [SCENARIO] Invalid MitID credentials
        [GIVEN] Login client raises AulaAuthenticationError
        [WHEN] Polling the flow status
        [THEN] Status is error with auth failure message
        """

        token_repo = FileTokenRepository(str(tmp_path / "tokens.json"))
        mock_login_client_class = MagicMock()
        mock_client_instance = MagicMock()
        mock_login_client_class.return_value = mock_client_instance
        mock_client_instance.authenticate.side_effect = Exception(
            "Invalid credentials"
        )

        auth_service = AuthService(
            token_repository=token_repo,
            login_client_class=mock_login_client_class,
        )
        app = _build_test_app(auth_service)
        client = TestClient(app)

        resp = client.post("/auth/start", json={"username": "baduser"})
        flow_id = resp.json()["flow_id"]

        auth_service._wait_for_flow(flow_id, timeout=5)

        resp = client.get(f"/auth/status/{flow_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == AuthFlowStatus.ERROR
        assert "credentials" in resp.json()["error"].lower() or "authentication" in resp.json()["error"].lower()

        # No tokens should be persisted
        assert token_repo.load() is None

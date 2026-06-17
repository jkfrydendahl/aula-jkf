"""Scenarios 13-14: Write operation endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies.app_auth import require_app_auth
from app.routers.action_router import create_action_router
from app.services.aula_service import AulaService


def _build_test_app(aula_service):
    app = FastAPI()
    app.state.user_registry = {"default": {"aula_service": aula_service}}
    app.dependency_overrides[require_app_auth] = lambda: "default"
    app.include_router(create_action_router())
    return app


@pytest.fixture
def mock_aula_service():
    service = MagicMock(spec=AulaService)
    service.send_message.return_value = {"status": "sent", "message_id": "msg-99"}
    service.update_presence.return_value = {"status": "updated"}
    return service


class TestSendMessage:
    """Scenario 13: POST /messages/send."""

    def test_sends_message_with_correct_args(self, mock_aula_service):
        app = _build_test_app(mock_aula_service)
        client = TestClient(app)

        resp = client.post("/messages/send", json={
            "recipient_id": "user-42",
            "subject": "Hello",
            "text": "Meeting tomorrow?",
        })
        assert resp.status_code == 200
        mock_aula_service.send_message.assert_called_once_with(
            recipient_id="user-42",
            subject="Hello",
            text="Meeting tomorrow?",
        )


class TestUpdatePresence:
    """Scenario 14: POST /presence/update."""

    def test_updates_presence_with_correct_args(self, mock_aula_service):
        app = _build_test_app(mock_aula_service)
        client = TestClient(app)

        resp = client.post("/presence/update", json={
            "child_id": "child-1",
            "status": "going_home",
        })
        assert resp.status_code == 200
        mock_aula_service.update_presence.assert_called_once_with(
            child_id="child-1",
            status="going_home",
        )

"""Scenarios 8-12: Read API endpoints."""
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.schemas import TokenData
from app.repositories.token_repository import FileTokenRepository
from app.routers.data_router import create_data_router
from app.services.aula_service import AulaService


def _build_test_app(aula_service, token_repo):
    """Create test app with data router and valid tokens."""
    app = FastAPI()
    router = create_data_router(aula_service)
    app.include_router(router)

    # Save valid token so middleware isn't needed for these focused tests
    token_repo.save(TokenData(
        access_token="valid",
        refresh_token="valid",
        expires_at=time.time() + 3600,
    ))

    return app


@pytest.fixture
def token_repo(tmp_path):
    return FileTokenRepository(str(tmp_path / "tokens.json"))


@pytest.fixture
def mock_aula_service():
    service = MagicMock(spec=AulaService)
    service.get_children.return_value = [
        {"id": "child-1", "name": "Emilie", "institution": "Hojelse Skole", "profile_picture": None},
        {"id": "child-2", "name": "Rasmus", "institution": "Hojelse Skole", "profile_picture": None},
    ]
    service.get_presence.return_value = {
        "status": "Checked in",
        "check_in_time": "07:45",
        "check_out_time": "15:30",
        "activity": "School",
    }
    service.get_messages.return_value = [
        {"id": "msg-1", "subject": "Tur til skoven", "sender": "Anne", "text": "Husk madpakke", "unread": True},
    ]
    service.get_calendar.return_value = [
        {"summary": "Matematik", "start": "2024-01-15T08:00:00", "end": "2024-01-15T08:45:00", "location": "Lokale 3"},
    ]
    service.get_ugeplan.return_value = {
        "current_week": "Uge 3: Emne om vikinger",
        "next_week": "Uge 4: Matematik projekt",
    }
    return service


class TestGetChildren:
    """Scenario 8: GET /children."""

    def test_returns_child_list(self, token_repo, mock_aula_service):
        app = _build_test_app(mock_aula_service, token_repo)
        client = TestClient(app)

        resp = client.get("/children")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "Emilie"
        assert data[1]["name"] == "Rasmus"
        mock_aula_service.get_children.assert_called_once()


class TestGetPresence:
    """Scenario 9: GET /presence/{child_id}."""

    def test_returns_presence_details(self, token_repo, mock_aula_service):
        app = _build_test_app(mock_aula_service, token_repo)
        client = TestClient(app)

        resp = client.get("/presence/child-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Checked in"
        assert data["check_in_time"] == "07:45"
        mock_aula_service.get_presence.assert_called_once_with("child-1")


class TestGetMessages:
    """Scenario 10: GET /messages."""

    def test_returns_messages(self, token_repo, mock_aula_service):
        app = _build_test_app(mock_aula_service, token_repo)
        client = TestClient(app)

        resp = client.get("/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["subject"] == "Tur til skoven"
        assert data[0]["unread"] is True
        mock_aula_service.get_messages.assert_called_once()


class TestGetCalendar:
    """Scenario 11: GET /calendar/{child_id}."""

    def test_returns_calendar_events(self, token_repo, mock_aula_service):
        app = _build_test_app(mock_aula_service, token_repo)
        client = TestClient(app)

        resp = client.get("/calendar/child-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["summary"] == "Matematik"
        assert data[0]["location"] == "Lokale 3"
        mock_aula_service.get_calendar.assert_called_once_with("child-1")


class TestGetUgeplan:
    """Scenario 12: GET /ugeplan/{child_id}."""

    def test_returns_weekly_plan(self, token_repo, mock_aula_service):
        app = _build_test_app(mock_aula_service, token_repo)
        client = TestClient(app)

        resp = client.get("/ugeplan/child-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "current_week" in data
        assert "vikinger" in data["current_week"]
        mock_aula_service.get_ugeplan.assert_called_once_with("child-1")

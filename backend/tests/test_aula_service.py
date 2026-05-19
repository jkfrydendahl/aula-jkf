"""Tests for AulaService wiring to real client."""
from unittest.mock import MagicMock, patch
import pytest

from app.services.aula_service import AulaService


@pytest.fixture
def mock_client():
    """Create a mock AulaClient with realistic data."""
    client = MagicMock()
    client._children = [
        {"id": 123, "name": "Alice Jensen", "userId": 456},
        {"id": 789, "name": "Bob Jensen", "userId": 101},
    ]
    client._institutions = {123: "Solskolen", 789: "Solskolen"}
    client._daily_overview = {
        "123": {
            "status": "checked_in",
            "entryTime": "08:00",
            "exitTime": "15:30",
            "exitWith": "Mor",
            "comment": None,
            "spareTimeActivity": "SFO",
        }
    }
    client._threads = [
        {
            "id": 1001,
            "subject": "School trip",
            "sender": {"name": "Teacher A"},
            "lastMessage": {"sendDateTime": "2024-01-15T10:00:00"},
            "isUnread": True,
            "latestMessage": {"text": {"html": "<p>Hello!</p>"}},
        }
    ]
    client._skoleskema = {
        "123": [
            {
                "title": "Math",
                "startDateTime": "2024-01-15T09:00:00",
                "endDateTime": "2024-01-15T10:00:00",
                "allDay": False,
                "description": "Chapter 5",
            }
        ]
    }
    client.ugeplaner = {"123": {"week": 3, "plans": [{"subject": "Danish", "text": "Read pages 10-20"}]}}
    client.unread_messages = 2
    client._tokens = {"access_token": "test-token"}
    return client


def test_get_children(mock_client):
    service = AulaService(mock_client)
    children = service.get_children()
    assert len(children) == 2
    assert children[0] == {"id": "123", "name": "Alice Jensen", "institution": "Solskolen"}
    assert children[1] == {"id": "789", "name": "Bob Jensen", "institution": "Solskolen"}


def test_get_presence(mock_client):
    service = AulaService(mock_client)
    presence = service.get_presence("123")
    assert presence["status"] == "checked_in"
    assert presence["check_in_time"] == "08:00"
    assert presence["exit_with"] == "Mor"


def test_get_presence_unknown(mock_client):
    service = AulaService(mock_client)
    presence = service.get_presence("999")
    assert presence["status"] == "unknown"


def test_get_messages(mock_client):
    service = AulaService(mock_client)
    messages = service.get_messages()
    assert len(messages) == 1
    assert messages[0]["subject"] == "School trip"
    assert messages[0]["is_read"] is False


def test_get_calendar(mock_client):
    service = AulaService(mock_client)
    events = service.get_calendar("123")
    assert len(events) == 1
    assert events[0]["title"] == "Math"


def test_get_ugeplan(mock_client):
    service = AulaService(mock_client)
    ugeplan = service.get_ugeplan("123")
    assert ugeplan["week"] == 3


def test_get_unread_count(mock_client):
    service = AulaService(mock_client)
    assert service.get_unread_count() == 2


def test_is_authenticated(mock_client):
    service = AulaService(mock_client)
    assert service.is_authenticated is True

    mock_client._tokens = {}
    assert service.is_authenticated is False


def test_send_message(mock_client):
    mock_client.custom_api_call.return_value = {"id": 999}
    service = AulaService(mock_client)
    result = service.send_message("456", "Test", "<p>Hi</p>")
    assert result["success"] is True
    mock_client.custom_api_call.assert_called_once()


def test_update_presence(mock_client):
    mock_client.custom_api_call.return_value = {"status": "ok"}
    service = AulaService(mock_client)
    result = service.update_presence("123", "checked_out")
    assert result["success"] is True
    mock_client.custom_api_call.assert_called_once()

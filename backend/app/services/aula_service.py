"""AulaService: Facade wrapping the Aula client for data access."""
from typing import Any, Optional
import logging

from app.aula_client import AulaClient, AulaClientError, AulaAuthRequiredError
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)


class AulaService:
    """Wraps the Aula client and normalizes data for API consumption."""

    def __init__(self, client: AulaClient):
        self._client = client

    @property
    def is_authenticated(self) -> bool:
        """Check if the client has valid tokens."""
        return bool(self._client._tokens and self._client._tokens.get("access_token"))

    def refresh_data(self) -> None:
        """Call update_data() on the underlying client to refresh all cached data."""
        self._client.update_data()

    def get_children(self) -> list[dict[str, Any]]:
        """Return list of child profiles."""
        children = []
        for child in self._client._children:
            children.append({
                "id": str(child["id"]),
                "name": child.get("name", ""),
                "institution": self._client._institutions.get(child["id"], ""),
            })
        return children

    def get_presence(self, child_id: str) -> dict[str, Any]:
        """Return presence info for a child."""
        overview = self._client._daily_overview.get(child_id)
        if not overview:
            return {"child_id": child_id, "status": "unknown"}

        return {
            "child_id": child_id,
            "status": overview.get("status", "unknown"),
            "check_in_time": overview.get("entryTime"),
            "check_out_time": overview.get("exitTime"),
            "exit_with": overview.get("exitWith"),
            "comment": overview.get("comment"),
            "spare_time_activity": overview.get("spareTimeActivity"),
        }

    def get_messages(self) -> list[dict[str, Any]]:
        """Return messages list (threads from last update_data)."""
        messages = []
        if hasattr(self._client, '_threads'):
            for thread in self._client._threads:
                messages.append({
                    "id": str(thread.get("id", "")),
                    "subject": thread.get("subject", ""),
                    "sender": thread.get("sender", {}).get("name", ""),
                    "timestamp": thread.get("lastMessage", {}).get("sendDateTime", ""),
                    "is_read": not thread.get("isUnread", False),
                    "text": thread.get("latestMessage", {}).get("text", {}).get("html", ""),
                })
        return messages

    def get_calendar(self, child_id: str) -> list[dict[str, Any]]:
        """Return calendar events for a child."""
        events = []
        if hasattr(self._client, '_skoleskema') and child_id in self._client._skoleskema:
            for event in self._client._skoleskema[child_id]:
                events.append({
                    "title": event.get("title", ""),
                    "start": event.get("startDateTime", ""),
                    "end": event.get("endDateTime", ""),
                    "all_day": event.get("allDay", False),
                    "description": event.get("description", ""),
                })
        return events

    def get_ugeplan(self, child_id: str) -> dict[str, Any]:
        """Return weekly plan for a child."""
        if hasattr(self._client, 'ugeplaner') and child_id in self._client.ugeplaner:
            return self._client.ugeplaner[child_id]
        return {}

    def send_message(self, recipient_id: str, subject: str, text: str) -> dict[str, Any]:
        """Send a message via the Aula API."""
        result = self._client.custom_api_call(
            uri="messaging.sendMessage",
            post_data={
                "subject": subject,
                "text": {"html": text},
                "recipients": [{"id": int(recipient_id)}],
            },
        )
        return {"success": True, "data": result}

    def update_presence(self, child_id: str, status: str) -> dict[str, Any]:
        """Update child presence status."""
        # Map status to exitWith/entryTime based on Aula's API
        result = self._client.custom_api_call(
            uri="presence.updateDailyOverview",
            post_data={
                "childId": int(child_id),
                "status": status,
            },
        )
        return {"success": True, "data": result}

    def get_unread_count(self) -> int:
        """Return number of unread messages."""
        return self._client.unread_messages


"""AulaService: Facade wrapping the Aula client for data access."""
from typing import Any


class AulaService:
    """Wraps the Aula client and normalizes data for API consumption."""

    def get_children(self) -> list[dict[str, Any]]:
        """Return list of child profiles."""
        raise NotImplementedError

    def get_presence(self, child_id: str) -> dict[str, Any]:
        """Return presence info for a child."""
        raise NotImplementedError

    def get_messages(self) -> list[dict[str, Any]]:
        """Return messages list."""
        raise NotImplementedError

    def get_calendar(self, child_id: str) -> list[dict[str, Any]]:
        """Return calendar events for a child."""
        raise NotImplementedError

    def get_ugeplan(self, child_id: str) -> dict[str, Any]:
        """Return weekly plan for a child."""
        raise NotImplementedError

    def send_message(self, recipient_id: str, subject: str, text: str) -> dict[str, Any]:
        """Send a message."""
        raise NotImplementedError

    def update_presence(self, child_id: str, status: str) -> dict[str, Any]:
        """Update child presence status."""
        raise NotImplementedError

import logging

_LOGGER = logging.getLogger(__name__)


class BackgroundPoller:
    """Periodically checks for new Aula data and triggers push notifications."""

    def __init__(self, aula_service, push_service, previous_unread_count: int = 0):
        self._aula_service = aula_service
        self._push_service = push_service
        self._previous_unread_count = previous_unread_count

    def tick(self):
        """Run one poll cycle. Called by scheduler."""
        try:
            current_count = self._aula_service.get_unread_count()

            if current_count > self._previous_unread_count:
                new_count = current_count - self._previous_unread_count
                self._push_service.send_notification(
                    title=f"New Aula message{'s' if new_count > 1 else ''}",
                    body=f"You have {new_count} new unread message{'s' if new_count > 1 else ''}",
                )

            self._previous_unread_count = current_count

        except Exception as e:
            _LOGGER.error(f"Background poll failed: {e}")

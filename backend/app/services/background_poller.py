import logging

_LOGGER = logging.getLogger(__name__)


class BackgroundPoller:
    """Periodically checks for new Aula data and triggers push notifications."""

    def __init__(self, aula_service, push_service, previous_unread_count: int = 0):
        self._aula_service = aula_service
        self._push_service = push_service
        self._previous_counts = {"messages": 0, "posts": 0, "vacations": 0}

    def tick(self):
        """Run one poll cycle. Called by scheduler."""
        try:
            self._aula_service.refresh_all()
            current_counts = self._aula_service.get_new_item_counts()

            total_previous = sum(self._previous_counts.values())
            total_current = sum(current_counts.values())

            if total_current > total_previous:
                new_count = total_current - total_previous
                self._push_service.send_notification(
                    title="Ny besked i Aula" if new_count == 1 else f"{new_count} nye beskeder i Aula",
                    body="Tryk for at åbne",
                )

            self._previous_counts = current_counts

        except Exception as e:
            _LOGGER.error(f"Background poll failed: {e}")

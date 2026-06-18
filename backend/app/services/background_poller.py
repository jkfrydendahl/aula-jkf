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
            _LOGGER.info(f"Poll tick: counts={current_counts}, previous={self._previous_counts}")

            # Posts count is a delta (new since last check) — fire if any new.
            # Messages and vacations are totals — fire if they increased.
            new_posts = current_counts.get("posts", 0)
            messages_increased = current_counts.get("messages", 0) > self._previous_counts.get("messages", 0)
            vacations_increased = current_counts.get("vacations", 0) > self._previous_counts.get("vacations", 0)

            if new_posts > 0 or messages_increased or vacations_increased:
                new_count = new_posts + (
                    max(0, current_counts.get("messages", 0) - self._previous_counts.get("messages", 0))
                ) + (
                    max(0, current_counts.get("vacations", 0) - self._previous_counts.get("vacations", 0))
                )
                self._push_service.send_notification(
                    title="Ny besked i Aula" if new_count == 1 else f"{new_count} nye beskeder i Aula",
                    body="Tryk for at åbne",
                )

            # Store totals for messages/vacations; posts delta resets automatically.
            self._previous_counts = {
                "messages": current_counts.get("messages", 0),
                "posts": 0,
                "vacations": current_counts.get("vacations", 0),
            }

        except Exception as e:
            _LOGGER.error(f"Background poll failed: {e}")

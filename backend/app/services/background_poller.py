import logging

_LOGGER = logging.getLogger(__name__)


class BackgroundPoller:
    """Periodically checks for new Aula data and triggers push notifications."""

    def __init__(self, aula_service, push_service, previous_unread_count: int = 0):
        self._aula_service = aula_service
        self._push_service = push_service
        self._previous_counts = None  # None = uninitialized; seed on first tick
        self._previous_pickup_states: dict | None = None  # None = uninitialized; seed on first tick

    def tick(self):
        """Run one poll cycle. Called by scheduler."""
        try:
            self._aula_service.refresh_all()
            current_counts = self._aula_service.get_new_item_counts()

            if self._previous_counts is None:
                # First tick: seed baseline to avoid startup spike notifications.
                self._previous_counts = {
                    "messages": current_counts.get("messages", 0),
                    "posts": 0,
                    "vacations": current_counts.get("vacations", 0),
                }
                # Also seed pickup states so first real comparison has a baseline.
                try:
                    self._previous_pickup_states = self._aula_service.get_pickup_states()
                except Exception as e:
                    _LOGGER.warning(f"Failed to seed pickup states baseline: {e}")
                _LOGGER.info(f"Poll tick (baseline seeded): counts={current_counts}")
                return

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

            # Store totals for messages/vacations; track downward too so we don't
            # miss new items that arrive after the user reads existing ones.
            self._previous_counts = {
                "messages": min(self._previous_counts.get("messages", 0), current_counts.get("messages", 0)),
                "posts": 0,
                "vacations": min(self._previous_counts.get("vacations", 0), current_counts.get("vacations", 0)),
            }

            # Check for pickup type changes for any child.
            try:
                current_pickup_states = self._aula_service.get_pickup_states()
                if self._previous_pickup_states is not None:
                    for child_id, current_state in current_pickup_states.items():
                        prev_state = self._previous_pickup_states.get(child_id)
                        if prev_state is None:
                            continue
                        if (current_state["activity_type"] != prev_state["activity_type"] or
                                current_state["exit_with"] != prev_state["exit_with"]):
                            child_name = self._aula_service.get_child_name(child_id)
                            _LOGGER.info(
                                f"Pickup changed for {child_name} (id={child_id}): "
                                f"{prev_state} → {current_state}"
                            )
                            self._push_service.send_notification(
                                title="Afhentning ændret",
                                body=f"Afhentning for {child_name} er ændret",
                            )
                self._previous_pickup_states = current_pickup_states
            except Exception as e:
                _LOGGER.warning(f"Pickup state check failed: {e}")

        except Exception as e:
            _LOGGER.error(f"Background poll failed: {e}")

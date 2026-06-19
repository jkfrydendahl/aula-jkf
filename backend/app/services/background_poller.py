import logging

_LOGGER = logging.getLogger(__name__)


class BackgroundPoller:
    """Periodically checks for new Aula data and triggers push notifications."""

    def __init__(self, aula_service, push_service, previous_unread_count: int = 0):
        self._aula_service = aula_service
        self._push_service = push_service
        self._previous_counts = None  # None = uninitialized; seed on first tick
        self._previous_pickup_states: dict | None = None  # None = uninitialized; seed on first tick
        self._previous_presence_states: dict | None = None  # None = uninitialized; seed on first tick

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
                # Also seed pickup and presence states so first real comparison has a baseline.
                try:
                    self._previous_pickup_states = self._aula_service.get_pickup_states()
                except Exception as e:
                    _LOGGER.warning(f"Failed to seed pickup states baseline: {e}")
                try:
                    self._previous_presence_states = self._aula_service.get_presence_states_for_poller()
                except Exception as e:
                    _LOGGER.warning(f"Failed to seed presence states baseline: {e}")
                _LOGGER.info(f"Poll tick (baseline seeded): counts={current_counts}")
                return

            _LOGGER.info(f"Poll tick: counts={current_counts}, previous={self._previous_counts}")

            # Posts count is a delta (new since last check) — fire if any new.
            # Messages and vacations are totals — fire if they increased.
            cur_messages = current_counts.get("messages", 0)
            cur_vacations = current_counts.get("vacations", 0)
            prev_messages = self._previous_counts.get("messages", 0)
            prev_vacations = self._previous_counts.get("vacations", 0)
            new_posts = current_counts.get("posts", 0)
            messages_increased = cur_messages > prev_messages
            vacations_increased = cur_vacations > prev_vacations
            notified = False

            if new_posts > 0 or messages_increased or vacations_increased:
                new_count = new_posts + max(0, cur_messages - prev_messages) + max(0, cur_vacations - prev_vacations)
                self._push_service.send_notification(
                    title="Ny besked i Aula" if new_count == 1 else f"{new_count} nye beskeder i Aula",
                    body="Tryk for at åbne",
                )
                notified = True

            # After notifying: set previous = current so we don't re-notify on next tick.
            # Without notification: track downward (min) so a new item after reading still triggers.
            self._previous_counts = {
                "messages": cur_messages if notified else min(prev_messages, cur_messages),
                "posts": 0,
                "vacations": cur_vacations if notified else min(prev_vacations, cur_vacations),
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
                            # Suppress morning auto-reset to unspecified state
                            is_reset = (current_state["activity_type"] == 0 and current_state["exit_with"] == "")
                            if not is_reset:
                                child_name = self._aula_service.get_child_name(child_id)
                                _LOGGER.info(
                                    f"Pickup changed for {child_name} (id={child_id}): "
                                    f"{prev_state} → {current_state}"
                                )
                                self._push_service.send_notification(
                                    title="Afhentning ændret",
                                    body=f"Afhentning for {child_name} er ændret",
                                )
                            else:
                                _LOGGER.info(f"Pickup reset to unspecified for child {child_id} — suppressed")
                self._previous_pickup_states = current_pickup_states
            except Exception as e:
                _LOGGER.warning(f"Pickup state check failed: {e}")

            # Check for presence status changes (notify when child checks in).
            try:
                current_presence = self._aula_service.get_presence_states_for_poller()
                if self._previous_presence_states is not None:
                    for child_id, current_status in current_presence.items():
                        prev_status = self._previous_presence_states.get(child_id)
                        if prev_status is None:
                            continue
                        if current_status != prev_status and current_status == "checked_in":
                            if self._aula_service._known_presence_states.pop(child_id, None) == current_status:
                                _LOGGER.info(f"Check-in for child {child_id} was triggered by us — suppressed")
                            else:
                                child_name = self._aula_service.get_child_name(child_id)
                                _LOGGER.info(f"Child checked in: {child_name} (id={child_id})")
                                self._push_service.send_notification(
                                    title=f"{child_name} er ankommet",
                                    body="Barnet er tjekket ind",
                                )
                        elif current_status != prev_status and current_status == "checked_out":
                            if self._aula_service._known_presence_states.pop(child_id, None) == current_status:
                                _LOGGER.info(f"Check-out for child {child_id} was triggered by us — suppressed")
                            else:
                                child_name = self._aula_service.get_child_name(child_id)
                                _LOGGER.info(f"Child checked out: {child_name} (id={child_id})")
                                self._push_service.send_notification(
                                    title=f"{child_name} er afhentet",
                                    body="Barnet er tjekket ud",
                                )
                self._previous_presence_states = current_presence
            except Exception as e:
                _LOGGER.warning(f"Presence state check failed: {e}")

        except Exception as e:
            _LOGGER.error(f"Background poll failed: {e}")

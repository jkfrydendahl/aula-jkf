import logging
from typing import Optional

from app.repositories.push_repository import PushRepository, PushSubscription

_LOGGER = logging.getLogger(__name__)


class PushService:
    """Manages push subscriptions and sends notifications."""

    def __init__(self, push_repository: PushRepository, vapid_private_key: str, vapid_claim_email: str):
        self._repo = push_repository
        self._vapid_private_key = vapid_private_key
        self._vapid_claim_email = vapid_claim_email

    def subscribe(self, subscription: PushSubscription) -> None:
        self._repo.save(subscription)

    def unsubscribe(self, endpoint: str) -> None:
        self._repo.remove(endpoint)

    def send_notification(self, title: str, body: str) -> None:
        """Send push notification to all subscribers."""
        subs = self._repo.load_all()
        for sub in subs:
            try:
                self._send_to_subscriber(sub, title, body)
            except Exception as e:
                _LOGGER.warning(f"Failed to send push to {sub.endpoint}: {e}")

    def _send_to_subscriber(self, sub: PushSubscription, title: str, body: str) -> None:
        """Send to a single subscriber using pywebpush."""
        import json
        from pywebpush import webpush

        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": sub.keys},
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=self._vapid_private_key,
            vapid_claims={"sub": f"mailto:{self._vapid_claim_email}"},
        )

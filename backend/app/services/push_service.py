import json
import logging
import os
import subprocess

from app.repositories.push_repository import PushRepository, PushSubscription

_LOGGER = logging.getLogger(__name__)

_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "send_push.js")


class PushService:
    """Manages push subscriptions and sends notifications."""

    def __init__(
        self,
        push_repository: PushRepository,
        vapid_private_key: str,
        vapid_public_key: str,
        vapid_claim_email: str,
    ):
        self._repo = push_repository
        self._vapid_private_key = vapid_private_key
        self._vapid_public_key = vapid_public_key
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
        """Send to a single subscriber via Node.js web-push (Apple-compatible)."""
        payload = json.dumps(
            {
                "endpoint": sub.endpoint,
                "keys": sub.keys,
                "title": title,
                "body": body,
                "vapid_public_key": self._vapid_public_key,
                "vapid_private_key": self._vapid_private_key,
                "vapid_email": self._vapid_claim_email,
            }
        )

        result = subprocess.run(
            ["node", os.path.abspath(_SCRIPT_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "node send_push.js failed")

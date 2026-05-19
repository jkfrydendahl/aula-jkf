"""Scenarios 15-17: Background poller and push notifications."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repositories.push_repository import FilePushRepository, PushSubscription
from app.services.push_service import PushService
from app.services.background_poller import BackgroundPoller
from app.routers.push_router import create_push_router


@pytest.fixture
def push_repo(tmp_path):
    return FilePushRepository(str(tmp_path / "push_subs.json"))


class TestPollerDetectsNewMessage:
    """Scenario 15: Poller detects new message → sends push."""

    def test_sends_push_on_new_unread(self, push_repo):
        mock_aula_service = MagicMock()
        mock_aula_service.get_unread_count.return_value = 3  # New count

        mock_push_service = MagicMock()

        poller = BackgroundPoller(
            aula_service=mock_aula_service,
            push_service=mock_push_service,
            previous_unread_count=1,  # Old count was 1
        )

        poller.tick()

        mock_push_service.send_notification.assert_called_once()
        call_args = mock_push_service.send_notification.call_args
        assert "new" in call_args[1]["title"].lower() or "message" in call_args[1]["title"].lower()


class TestPollerNoNewMessages:
    """Scenario 16: Poller: no new messages → no push."""

    def test_no_push_when_count_unchanged(self, push_repo):
        mock_aula_service = MagicMock()
        mock_aula_service.get_unread_count.return_value = 2  # Same as before

        mock_push_service = MagicMock()

        poller = BackgroundPoller(
            aula_service=mock_aula_service,
            push_service=mock_push_service,
            previous_unread_count=2,  # Same
        )

        poller.tick()

        mock_push_service.send_notification.assert_not_called()


class TestPushSubscribeUnsubscribe:
    """Scenario 17: Push subscribe/unsubscribe."""

    def test_subscribe_stores_subscription(self, push_repo):
        push_service = PushService(
            push_repository=push_repo,
            vapid_private_key="test-key",
            vapid_claim_email="test@example.com",
        )

        sub = PushSubscription(
            endpoint="https://push.example.com/sub/123",
            keys={"p256dh": "key1", "auth": "key2"},
        )
        push_service.subscribe(sub)

        # Verify it's stored
        subs = push_repo.load_all()
        assert len(subs) == 1
        assert subs[0].endpoint == "https://push.example.com/sub/123"

    def test_unsubscribe_removes_subscription(self, push_repo):
        push_service = PushService(
            push_repository=push_repo,
            vapid_private_key="test-key",
            vapid_claim_email="test@example.com",
        )

        sub = PushSubscription(
            endpoint="https://push.example.com/sub/123",
            keys={"p256dh": "key1", "auth": "key2"},
        )
        push_service.subscribe(sub)
        push_service.unsubscribe("https://push.example.com/sub/123")

        subs = push_repo.load_all()
        assert len(subs) == 0

    def test_push_router_subscribe(self, push_repo):
        push_service = PushService(
            push_repository=push_repo,
            vapid_private_key="test-key",
            vapid_claim_email="test@example.com",
        )
        app = FastAPI()
        app.include_router(create_push_router(push_service))
        client = TestClient(app)

        resp = client.post("/push/subscribe", json={
            "endpoint": "https://push.example.com/sub/456",
            "keys": {"p256dh": "k1", "auth": "k2"},
        })
        assert resp.status_code == 200
        assert push_repo.load_all()[0].endpoint == "https://push.example.com/sub/456"

    def test_push_router_unsubscribe(self, push_repo):
        push_service = PushService(
            push_repository=push_repo,
            vapid_private_key="test-key",
            vapid_claim_email="test@example.com",
        )
        # Pre-save a subscription
        push_repo.save(PushSubscription(
            endpoint="https://push.example.com/sub/789",
            keys={"p256dh": "k1", "auth": "k2"},
        ))

        app = FastAPI()
        app.include_router(create_push_router(push_service))
        client = TestClient(app)

        resp = client.post("/push/unsubscribe", json={
            "endpoint": "https://push.example.com/sub/789",
        })
        assert resp.status_code == 200
        assert len(push_repo.load_all()) == 0

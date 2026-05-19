import pytest
from app.settings import Settings


@pytest.fixture
def settings(tmp_path):
    """Settings with temp paths for isolated tests."""
    return Settings(
        token_store_path=str(tmp_path / "tokens.json"),
        push_store_path=str(tmp_path / "push_subs.json"),
        vapid_private_key="test-private-key",
        vapid_public_key="test-public-key",
        vapid_claim_email="test@example.com",
    )

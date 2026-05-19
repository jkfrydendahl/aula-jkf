import json

from app.models.schemas import TokenData
from app.repositories.token_repository import FileTokenRepository


class TestFileTokenRepository:
    """Scenario 7: Token persistence across restart."""

    def test_save_and_load_tokens(self, tmp_path):
        """
        [SCENARIO] Tokens survive a restart
        [GIVEN] Tokens are saved via FileTokenRepository
        [WHEN] A new FileTokenRepository instance loads from the same path
        [THEN] The loaded tokens match what was saved
        """
        store_path = str(tmp_path / "tokens.json")
        tokens = TokenData(
            access_token="acc-123",
            refresh_token="ref-456",
            expires_at=1700000000.0,
        )

        # Save
        repo = FileTokenRepository(store_path)
        repo.save(tokens)

        # Simulate restart: new instance, same path
        repo2 = FileTokenRepository(store_path)
        loaded = repo2.load()

        assert loaded is not None
        assert loaded.access_token == "acc-123"
        assert loaded.refresh_token == "ref-456"
        assert loaded.expires_at == 1700000000.0

    def test_load_returns_none_when_no_file(self, tmp_path):
        """
        [SCENARIO] No tokens file exists
        [GIVEN] No tokens have been saved
        [WHEN] load() is called
        [THEN] Returns None
        """
        store_path = str(tmp_path / "tokens.json")
        repo = FileTokenRepository(store_path)
        assert repo.load() is None

    def test_save_creates_parent_directories(self, tmp_path):
        """
        [SCENARIO] Storage path has nested directories
        [GIVEN] The parent directory does not exist
        [WHEN] save() is called
        [THEN] Directories are created and tokens are persisted
        """
        store_path = str(tmp_path / "nested" / "dir" / "tokens.json")
        tokens = TokenData(
            access_token="acc",
            refresh_token="ref",
            expires_at=1.0,
        )

        repo = FileTokenRepository(store_path)
        repo.save(tokens)

        # Verify file was written
        with open(store_path) as f:
            data = json.load(f)
        assert data["access_token"] == "acc"

    def test_delete_removes_file(self, tmp_path):
        """
        [SCENARIO] Tokens are deleted (e.g., on logout)
        [GIVEN] Tokens exist on disk
        [WHEN] delete() is called
        [THEN] load() returns None
        """
        store_path = str(tmp_path / "tokens.json")
        tokens = TokenData(
            access_token="acc",
            refresh_token="ref",
            expires_at=1.0,
        )

        repo = FileTokenRepository(store_path)
        repo.save(tokens)
        repo.delete()

        assert repo.load() is None

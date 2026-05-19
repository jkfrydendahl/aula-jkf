"""Scenario 20: API version fallback on HTTP 410."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.api_version import find_working_api_version


class TestApiVersionFallback:
    """Scenario 20: API version fallback on 410."""

    def test_increments_version_on_410(self):
        """
        [SCENARIO] Aula API returns 410 on v22
        [GIVEN] API at /api/v22 returns HTTP 410
        [WHEN] find_working_api_version() is called starting at v22
        [THEN] It tries v23 and succeeds
        """
        mock_session = MagicMock()

        # v22 returns 410, v23 returns 200 with valid data
        response_410 = MagicMock(status_code=410)
        response_200 = MagicMock(status_code=200)
        response_200.json.return_value = {
            "data": {"profiles": [{"id": 1}]}
        }
        mock_session.get.side_effect = [response_410, response_200]

        result = find_working_api_version(mock_session, start_version=22, access_token="tok")

        assert result["version"] == 23
        assert result["profiles"] == [{"id": 1}]
        assert mock_session.get.call_count == 2

    def test_uses_first_version_if_200(self):
        """
        [SCENARIO] First version works
        [GIVEN] API at /api/v22 returns 200
        [WHEN] find_working_api_version() is called
        [THEN] Returns v22 immediately
        """
        mock_session = MagicMock()
        response_200 = MagicMock(status_code=200)
        response_200.json.return_value = {
            "data": {"profiles": [{"id": 1}]}
        }
        mock_session.get.return_value = response_200

        result = find_working_api_version(mock_session, start_version=22, access_token="tok")

        assert result["version"] == 22
        assert mock_session.get.call_count == 1

    def test_raises_on_max_attempts(self):
        """
        [SCENARIO] All versions return 410
        [GIVEN] API keeps returning 410 for all attempted versions
        [WHEN] Max attempts reached
        [THEN] Raises RuntimeError
        """
        mock_session = MagicMock()
        response_410 = MagicMock(status_code=410)
        mock_session.get.return_value = response_410

        with pytest.raises(RuntimeError, match="Could not find working API version"):
            find_working_api_version(mock_session, start_version=22, access_token="tok", max_attempts=3)

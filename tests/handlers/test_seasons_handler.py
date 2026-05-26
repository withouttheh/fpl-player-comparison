"""
tests/handlers/test_seasons_handler.py — Unit tests for seasons_handler.serve_seasons.

Tests cover:
  - Response shape: list of season objects with id and label
  - "current" season is always first in the list
  - Archive seasons from ARCHIVE_SEASONS appear with correct labels
  - No API call is made (seasons list is static)
  - Security headers present on response
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from handlers.seasons_handler import serve_seasons
from tests.helpers import MockRequest
from utils.config import ARCHIVE_SEASONS


class TestSeasonsHandlerResponse(unittest.TestCase):
    """Response shape and content."""

    def _call(self) -> MockRequest:
        request = MockRequest("/api/seasons")
        serve_seasons(request)
        return request

    def test_returns_200(self):
        self.assertEqual(self._call().last_status, 200)

    def test_response_is_a_list(self):
        self.assertIsInstance(self._call().response_json(), list)

    def test_response_content_type_is_json(self):
        request = self._call()
        self.assertIn("application/json", request._headers.get("content-type", ""))

    def test_first_entry_is_current_season(self):
        seasons = self._call().response_json()
        self.assertGreater(len(seasons), 0)
        self.assertEqual(seasons[0]["id"], "current")

    def test_current_season_label_is_live(self):
        seasons = self._call().response_json()
        self.assertEqual(seasons[0]["label"], "Live")

    def test_archive_seasons_are_included(self):
        seasons = self._call().response_json()
        returned_ids = {s["id"] for s in seasons}
        for archive_season in ARCHIVE_SEASONS:
            self.assertIn(archive_season, returned_ids)

    def test_archive_season_label_format(self):
        """Archive season label must be 'YYYY/YY Archive' (e.g. '2025/26 Archive')."""
        seasons = self._call().response_json()
        for s in seasons:
            if s["id"] == "current":
                continue
            year, suffix = s["id"].split("-")
            expected_label = f"{year}/{suffix} Archive"
            self.assertEqual(s["label"], expected_label, f"Bad label for season {s['id']}")

    def test_each_season_has_id_and_label(self):
        seasons = self._call().response_json()
        for s in seasons:
            self.assertIn("id", s, f"Season object missing 'id': {s}")
            self.assertIn("label", s, f"Season object missing 'label': {s}")

    def test_total_count_equals_one_plus_archive_seasons(self):
        """Total seasons = 1 (live) + len(ARCHIVE_SEASONS)."""
        seasons = self._call().response_json()
        self.assertEqual(len(seasons), 1 + len(ARCHIVE_SEASONS))

    def test_no_outbound_api_call_made(self):
        """Seasons are a static list — no FPL API call should be made."""
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            self._call()
            mock_get.assert_not_called()

    def test_security_headers_present(self):
        request = self._call()
        self.assertIn("x-content-type-options", request._headers)
        self.assertIn("x-frame-options", request._headers)
        self.assertIn("content-security-policy", request._headers)


if __name__ == "__main__":
    unittest.main()

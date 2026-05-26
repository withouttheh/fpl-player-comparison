"""
tests/handlers/test_fixtures_handler.py — Unit tests for fixtures_handler.serve_fixtures.

Mirrors the structure of test_history_handler.py with two differences:
  - Cache TTL is 3600s (1 hour) not 300s (5 minutes)
  - Output fields are event, is_home, difficulty, team_h, team_a
    (not gameweek stats)

Player ID validation is identical to the history handler —
the same _MAX_PLAYER_ID constant and same 400 response behaviour.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache import cache
from handlers.fixtures_handler import _CACHE_TTL, _MAX_PLAYER_ID, serve_fixtures
from tests.helpers import MockHTTPResponse, MockRequest, make_url_router

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_BOOTSTRAP = json.loads((_FIXTURES_DIR / "bootstrap_static.json").read_text())
_ELEMENT_SUMMARY = json.loads((_FIXTURES_DIR / "element_summary.json").read_text())

_EXPECTED_OUTPUT_FIELDS = {"event", "is_home", "difficulty", "team_h", "team_a"}


def _make_mock():
    return make_url_router(
        {
            "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
            "element-summary": MockHTTPResponse(_ELEMENT_SUMMARY),
        }
    )


class TestFixturesHandlerValidation(unittest.TestCase):
    """Same player ID validation rules as history_handler."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_player_id_zero_returns_400(self):
        request = MockRequest("/api/player/0/fixtures")
        serve_fixtures(request, player_id="0")
        self.assertEqual(request.last_status, 400)

    def test_player_id_above_max_returns_400(self):
        request = MockRequest(f"/api/player/{_MAX_PLAYER_ID + 1}/fixtures")
        serve_fixtures(request, player_id=str(_MAX_PLAYER_ID + 1))
        self.assertEqual(request.last_status, 400)

    def test_valid_player_id_does_not_return_400(self):
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_fixtures(request, player_id="1")
        self.assertNotEqual(request.last_status, 400)

    def test_validation_blocks_api_call_for_invalid_id(self):
        request = MockRequest("/api/player/0/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            serve_fixtures(request, player_id="0")
            mock_get.assert_not_called()


class TestFixturesHandlerCache(unittest.TestCase):
    """Fixtures cache uses a different key and TTL from history."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_miss_calls_fpl_api(self):
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_fixtures(request, player_id="1")
            self.assertTrue(mock_get.called)

    def test_cache_hit_skips_fpl_api(self):
        cache.set("fixtures:1", [{"event": 30}], ttl=3600)
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            serve_fixtures(request, player_id="1")
            mock_get.assert_not_called()

    def test_cache_key_uses_fixtures_namespace(self):
        """Key must be 'fixtures:{id}' not 'history:{id}' — different data."""
        request = MockRequest("/api/player/7/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_fixtures(request, player_id="7")
        self.assertIsNotNone(cache.get("fixtures:7"))
        self.assertIsNone(
            cache.get("history:7"), "Fixture data must not be stored under history key"
        )

    def test_fixtures_and_history_cache_do_not_collide(self):
        """Separate handlers for the same player ID must use separate cache keys."""
        cache.set("history:1", [{"round": 1}], ttl=300)
        cache.set("fixtures:1", [{"event": 30}], ttl=3600)

        # Reading history must return history data.
        self.assertEqual(cache.get("history:1"), [{"round": 1}])
        # Reading fixtures must return fixture data.
        self.assertEqual(cache.get("fixtures:1"), [{"event": 30}])

    def test_cache_ttl_is_one_hour(self):
        """Fixture schedule changes rarely — 1 hour TTL is appropriate."""
        self.assertEqual(_CACHE_TTL, 3600)


class TestFixturesHandlerResponse(unittest.TestCase):
    """Response shape and content."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _call(self, player_id: str = "1") -> MockRequest:
        request = MockRequest(f"/api/player/{player_id}/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_fixtures(request, player_id=player_id)
        return request

    def test_returns_200_on_success(self):
        self.assertEqual(self._call().last_status, 200)

    def test_response_is_a_list(self):
        self.assertIsInstance(self._call().response_json(), list)

    def test_response_has_correct_number_of_fixtures(self):
        # Fixture file has 2 upcoming fixtures.
        self.assertEqual(len(self._call().response_json()), 2)

    def test_each_fixture_has_expected_fields(self):
        fixtures = self._call().response_json()
        for fixture in fixtures:
            for field in _EXPECTED_OUTPUT_FIELDS:
                self.assertIn(field, fixture, f"Missing field '{field}' in: {fixture}")

    def test_team_ids_are_resolved_to_short_names(self):
        """team_h and team_a must be short names, not integer IDs."""
        fixtures = self._call().response_json()
        for fixture in fixtures:
            if "team_h" in fixture:
                self.assertIsInstance(
                    fixture["team_h"], str, "team_h should be a string short name"
                )
            if "team_a" in fixture:
                self.assertIsInstance(
                    fixture["team_a"], str, "team_a should be a string short name"
                )

    def test_difficulty_is_integer(self):
        """FDR difficulty must be an integer 1–5."""
        fixtures = self._call().response_json()
        for fixture in fixtures:
            if "difficulty" in fixture:
                self.assertIsInstance(fixture["difficulty"], int)
                self.assertIn(fixture["difficulty"], range(1, 6))

    def test_is_home_is_boolean(self):
        fixtures = self._call().response_json()
        for fixture in fixtures:
            if "is_home" in fixture:
                self.assertIsInstance(fixture["is_home"], bool)

    def test_security_headers_present(self):
        request = self._call()
        self.assertIn("x-content-type-options", request._headers)
        self.assertIn("content-security-policy", request._headers)


class TestFixturesHandlerErrors(unittest.TestCase):
    """API failures return 502."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_network_failure_returns_502(self):
        import requests as req

        request = MockRequest("/api/player/1/fixtures")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("unreachable"),
        ):
            serve_fixtures(request, player_id="1")
        self.assertEqual(request.last_status, 502)

    def test_missing_fixtures_key_returns_502(self):
        bad_summary = {"history": [], "history_past": []}  # fixtures key missing
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = make_url_router(
                {
                    "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
                    "element-summary": MockHTTPResponse(bad_summary),
                }
            )
            serve_fixtures(request, player_id="1")
        self.assertEqual(request.last_status, 502)

    def test_empty_fixtures_returns_empty_list(self):
        """No upcoming fixtures (end of season) returns 200 with empty array."""
        empty_summary = dict(_ELEMENT_SUMMARY, fixtures=[])
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = make_url_router(
                {
                    "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
                    "element-summary": MockHTTPResponse(empty_summary),
                }
            )
            serve_fixtures(request, player_id="1")
        self.assertEqual(request.last_status, 200)

    def test_error_body_does_not_leak_internals(self):
        import requests as req

        request = MockRequest("/api/player/1/fixtures")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("internal/path/detail"),
        ):
            serve_fixtures(request, player_id="1")
        body = request.response_body().decode()
        self.assertNotIn("internal/path/detail", body)

    def test_timeout_passed_to_requests_get(self):
        request = MockRequest("/api/player/1/fixtures")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_fixtures(request, player_id="1")
            for call in mock_get.call_args_list:
                _, kwargs = call
                self.assertEqual(kwargs.get("timeout"), 10)


if __name__ == "__main__":
    unittest.main()

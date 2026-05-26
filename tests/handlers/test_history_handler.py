"""
tests/handlers/test_history_handler.py — Unit tests for history_handler.serve_history.

Tests cover:
  - Player ID validation (range enforcement, not just format)
  - Cache hit/miss and per-player cache key namespacing
  - ICT/xG fields are returned as floats, not strings
  - FPL API failures produce 502
  - Response contains the correct fields

Player ID rules tested:
  - 0 → 400 (below minimum)
  - 1 → valid
  - 2000 → valid (upper boundary)
  - 2001 → 400 (above maximum)
  - Very large numbers → 400
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache import cache
from handlers.history_handler import _CACHE_TTL, _MAX_PLAYER_ID, _OUTPUT_FIELDS, serve_history
from tests.helpers import MockHTTPResponse, MockRequest, make_url_router
from utils.config import ARCHIVE_SEASONS

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_BOOTSTRAP = json.loads((_FIXTURES_DIR / "bootstrap_static.json").read_text())
_ELEMENT_SUMMARY = json.loads((_FIXTURES_DIR / "element_summary.json").read_text())


def _make_mock():
    """Return a side_effect that routes bootstrap vs element-summary calls."""
    return make_url_router(
        {
            "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
            "element-summary": MockHTTPResponse(_ELEMENT_SUMMARY),
        }
    )


class TestHistoryHandlerValidation(unittest.TestCase):
    """Player ID range is validated before any outbound request."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_player_id_zero_returns_400(self):
        request = MockRequest("/api/player/0/history")
        serve_history(request, player_id="0")
        self.assertEqual(request.last_status, 400)

    def test_player_id_above_max_returns_400(self):
        request = MockRequest(f"/api/player/{_MAX_PLAYER_ID + 1}/history")
        serve_history(request, player_id=str(_MAX_PLAYER_ID + 1))
        self.assertEqual(request.last_status, 400)

    def test_very_large_player_id_returns_400(self):
        request = MockRequest("/api/player/999999/history")
        serve_history(request, player_id="999999")
        self.assertEqual(request.last_status, 400)

    def test_player_id_one_is_valid(self):
        """ID 1 is the minimum valid value."""
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id="1")
        self.assertEqual(request.last_status, 200)

    def test_player_id_at_max_boundary_is_valid(self):
        """ID == _MAX_PLAYER_ID is the maximum valid value."""
        request = MockRequest(f"/api/player/{_MAX_PLAYER_ID}/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id=str(_MAX_PLAYER_ID))
        # Will return 200 or 502 depending on whether the API has this player.
        # Either is acceptable — 400 is not.
        self.assertNotEqual(request.last_status, 400)

    def test_validation_happens_before_api_call(self):
        """An invalid ID must not trigger any outbound HTTP request."""
        request = MockRequest("/api/player/0/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            serve_history(request, player_id="0")
            mock_get.assert_not_called()

    def test_400_response_body_describes_valid_range(self):
        """The 400 message must tell the client what the valid range is."""
        request = MockRequest("/api/player/9999/history")
        serve_history(request, player_id="9999")
        body = request.response_body().decode()
        self.assertIn("1", body)
        self.assertIn(str(_MAX_PLAYER_ID), body)


class TestHistoryHandlerCache(unittest.TestCase):
    """Cache is keyed per player ID so different players don't collide."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_miss_calls_fpl_api(self):
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id="1")
            self.assertTrue(mock_get.called)

    def test_cache_hit_skips_fpl_api(self):
        cache.set("history:1", [{"round": 1}], ttl=300)
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            serve_history(request, player_id="1")
            mock_get.assert_not_called()

    def test_different_players_cached_independently(self):
        """Player 1 cache must not be served for player 2 requests."""
        cache.set("history:1", [{"round": 1, "player": "one"}], ttl=300)

        request = MockRequest("/api/player/2/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id="2")
            # Player 2 had a cache miss so the API must have been called.
            self.assertTrue(mock_get.called)

    def test_cache_key_is_namespaced_with_player_id(self):
        """Cache key format must be 'history:{player_id}' to avoid collisions."""
        request = MockRequest("/api/player/42/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id="42")
        # The cache should have an entry under 'history:42'.
        self.assertIsNotNone(cache.get("history:42"))

    def test_cache_ttl_is_five_minutes(self):
        """History cache TTL must be 300 seconds (5 minutes)."""
        self.assertEqual(_CACHE_TTL, 300)


class TestHistoryHandlerResponse(unittest.TestCase):
    """Response content and data types."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _call(self, player_id: str = "1") -> MockRequest:
        request = MockRequest(f"/api/player/{player_id}/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id=player_id)
        return request

    def test_returns_200_on_success(self):
        self.assertEqual(self._call().last_status, 200)

    def test_response_is_a_list(self):
        self.assertIsInstance(self._call().response_json(), list)

    def test_response_has_correct_number_of_gameweeks(self):
        # Fixture has 2 gameweeks of history.
        self.assertEqual(len(self._call().response_json()), 2)

    def test_influence_is_float_not_string(self):
        """FPL API returns 'influence' as a string. Handler must cast to float."""
        history = self._call().response_json()
        for gw in history:
            if "influence" in gw:
                self.assertIsInstance(
                    gw["influence"],
                    float,
                    f"influence should be float, got {type(gw['influence'])}",
                )

    def test_xg_fields_are_floats(self):
        """All xG/xA/xGI/xGC fields must be float, not string."""
        float_fields = [
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "expected_goals_conceded",
        ]
        history = self._call().response_json()
        for gw in history:
            for field in float_fields:
                if field in gw:
                    self.assertIsInstance(
                        gw[field], float, f"'{field}' should be float, got {type(gw[field])}"
                    )

    def test_ict_index_is_float(self):
        history = self._call().response_json()
        for gw in history:
            if "ict_index" in gw:
                self.assertIsInstance(gw["ict_index"], float)

    def test_opponent_team_is_resolved_to_short_name(self):
        """opponent_team ID must be resolved to a team short name."""
        history = self._call().response_json()
        for gw in history:
            if "opponent_team" in gw:
                # Should be 'MCI', not 14 (the raw team ID from the fixture).
                self.assertEqual(gw["opponent_team"], "MCI")

    def test_output_fields_are_subset_of_declared_fields(self):
        """Response must only contain fields in _OUTPUT_FIELDS."""
        history = self._call().response_json()
        declared = set(_OUTPUT_FIELDS)
        for gw in history:
            extra = set(gw.keys()) - declared
            self.assertEqual(extra, set(), f"Unexpected fields in history row: {extra}")

    def test_security_headers_present(self):
        request = self._call()
        self.assertIn("x-content-type-options", request._headers)
        self.assertIn("content-security-policy", request._headers)


class TestHistoryHandlerErrors(unittest.TestCase):
    """API failures and edge cases."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_network_failure_returns_502(self):
        import requests as req

        request = MockRequest("/api/player/1/history")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("unreachable"),
        ):
            serve_history(request, player_id="1")
        self.assertEqual(request.last_status, 502)

    def test_missing_history_key_in_fpl_response_returns_502(self):
        """If element-summary has no 'history' key, return 502 not 500."""
        bad_summary = {"fixtures": [], "history_past": []}  # 'history' missing
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = make_url_router(
                {
                    "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
                    "element-summary": MockHTTPResponse(bad_summary),
                }
            )
            serve_history(request, player_id="1")
        self.assertEqual(request.last_status, 502)

    def test_empty_history_returns_502(self):
        """An empty history array (no gameweeks played) returns 502."""
        empty_summary = dict(_ELEMENT_SUMMARY, history=[])
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = make_url_router(
                {
                    "bootstrap-static": MockHTTPResponse(_BOOTSTRAP),
                    "element-summary": MockHTTPResponse(empty_summary),
                }
            )
            serve_history(request, player_id="1")
        self.assertEqual(request.last_status, 502)

    def test_error_body_does_not_leak_internals(self):
        import requests as req

        request = MockRequest("/api/player/1/history")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("db_password=secret"),
        ):
            serve_history(request, player_id="1")
        body = request.response_body().decode()
        self.assertNotIn("db_password", body)
        self.assertNotIn("Traceback", body)

    def test_timeout_passed_to_requests_get(self):
        request = MockRequest("/api/player/1/history")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.side_effect = _make_mock()
            serve_history(request, player_id="1")
            for call in mock_get.call_args_list:
                _, kwargs = call
                self.assertEqual(kwargs.get("timeout"), 10)


class TestHistoryHandlerArchive(unittest.TestCase):
    """Archive season path: reads from S3 mock, separate cache key, no player ID block."""

    def setUp(self):
        cache.clear()
        self._env = patch.dict(os.environ, {"FPL_MOCK": "1"})
        self._env.start()

    def tearDown(self):
        cache.clear()
        self._env.stop()

    def _call(self, player_id: str = "1", season: str | None = None) -> MockRequest:
        season = season or ARCHIVE_SEASONS[0]
        request = MockRequest(f"/api/player/{player_id}/history?season={season}")
        serve_history(request, player_id=player_id)
        return request

    def test_valid_archive_season_returns_200(self):
        self.assertEqual(self._call().last_status, 200)

    def test_archive_response_is_a_list(self):
        self.assertIsInstance(self._call().response_json(), list)

    def test_archive_response_has_history_fields(self):
        history = self._call().response_json()
        for gw in history:
            self.assertIn("round", gw)

    def test_archive_ict_fields_are_floats(self):
        history = self._call().response_json()
        for gw in history:
            for field in ("influence", "creativity", "threat", "ict_index"):
                if field in gw:
                    self.assertIsInstance(gw[field], float, f"'{field}' must be float in archive")

    def test_invalid_season_falls_back_to_live_api(self):
        """Unknown ?season= must fall back to the live FPL API, not S3.

        Temporarily removes FPL_MOCK so the live path uses requests.get.
        """
        self._env.stop()
        try:
            request = MockRequest("/api/player/1/history?season=1999-00")
            with patch("utils.loaders.base_loader.requests.get") as mock_get:
                mock_get.side_effect = _make_mock()
                serve_history(request, player_id="1")
                self.assertTrue(mock_get.called)
        finally:
            self._env.start()

    def test_archive_cache_key_namespaced_with_season_and_player(self):
        season = ARCHIVE_SEASONS[0]
        self._call(player_id="1", season=season)
        expected_key = f"history:{season}:1"
        self.assertIsNotNone(cache.get(expected_key), f"Expected cache key '{expected_key}'")

    def test_archive_cache_does_not_pollute_live_cache(self):
        """Archive fetch must not write to live 'history:1' cache key."""
        self._call(player_id="1")
        self.assertIsNone(cache.get("history:1"))

    def test_player_id_still_validated_for_archive(self):
        """Player ID range validation applies even when a season param is present."""
        season = ARCHIVE_SEASONS[0]
        request = MockRequest(f"/api/player/0/history?season={season}")
        serve_history(request, player_id="0")
        self.assertEqual(request.last_status, 400)


if __name__ == "__main__":
    unittest.main()

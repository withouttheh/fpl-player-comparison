"""
tests/handlers/test_players_handler.py — Unit tests for players_handler.serve_players.

Tests cover:
  - Cache hit skips the FPL API entirely
  - Cache miss fetches, processes, and caches the result
  - Response shape: correct fields, correct types, now_cost divided by 10
  - FPL API failures produce 502, not 500 or a traceback
  - No extra columns leak into the response

Mock strategy:
    We patch `utils.loaders.base_loader.requests.get` — the single point
    where all outbound HTTP calls originate. The handler → loader →
    base_loader chain runs normally; only the network call is replaced.
    This tests the full pipeline (loading + preprocessing + serialisation)
    against controlled fixture data.

Why not mock the loader classes directly?
    Mocking at the requests level tests more of the real code path.
    It also catches bugs in the loader and preprocessor layers that a
    loader-level mock would hide.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path so imports work when running from any directory.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cache import cache
from handlers.players_handler import serve_players, _CACHE_KEY, _CACHE_TTL, _OUTPUT_FIELDS
from tests.helpers import MockRequest, MockHTTPResponse

# Load fixture data once for the whole module.
_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_BOOTSTRAP = json.loads((_FIXTURES_DIR / "bootstrap_static.json").read_text())


class TestPlayersHandlerCache(unittest.TestCase):
    """Cache behaviour: hit, miss, TTL, key."""

    def setUp(self):
        # Always start with a clean cache so tests don't bleed into each other.
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cache_miss_calls_fpl_api(self):
        """On a cold cache, the handler must fetch from the FPL API."""
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse(_BOOTSTRAP)
            serve_players(request)
            self.assertTrue(mock_get.called, "Expected FPL API to be called on cache miss")

    def test_cache_hit_does_not_call_fpl_api(self):
        """On a warm cache, the handler must serve from cache without any HTTP call."""
        # Pre-populate the cache with the processed result.
        cache.set(_CACHE_KEY, [{"id": 1, "full_name": "Cached Player"}], ttl=3600)

        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            serve_players(request)
            mock_get.assert_not_called()

    def test_cache_hit_serves_cached_data(self):
        """Data returned on a cache hit is exactly what was cached."""
        cached_players = [{"id": 99, "full_name": "Cache Test Player"}]
        cache.set(_CACHE_KEY, cached_players, ttl=3600)

        request = MockRequest("/api/players")
        serve_players(request)

        self.assertEqual(request.response_json(), cached_players)

    def test_result_is_cached_after_fetch(self):
        """After a successful fetch, the result must be stored in the cache."""
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse(_BOOTSTRAP)
            serve_players(request)

        # Cache should now hold the processed players list.
        cached = cache.get(_CACHE_KEY)
        self.assertIsNotNone(cached)
        self.assertIsInstance(cached, list)

    def test_cache_ttl_is_one_hour(self):
        """The cache TTL constant must be 3600 seconds (1 hour)."""
        self.assertEqual(_CACHE_TTL, 3600)


class TestPlayersHandlerResponse(unittest.TestCase):
    """Response shape, types, and field selection."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _call(self) -> MockRequest:
        """Helper: make one request through the handler with the fixture data."""
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse(_BOOTSTRAP)
            serve_players(request)
        return request

    def test_returns_200_on_success(self):
        request = self._call()
        self.assertEqual(request.last_status, 200)

    def test_response_content_type_is_json(self):
        request = self._call()
        self.assertIn("application/json", request._headers.get("content-type", ""))

    def test_response_is_a_list(self):
        request = self._call()
        self.assertIsInstance(request.response_json(), list)

    def test_response_contains_correct_number_of_players(self):
        # Our fixture has 2 players.
        request = self._call()
        self.assertEqual(len(request.response_json()), 2)

    def test_each_player_has_all_output_fields(self):
        """Every player object must contain exactly the declared output fields."""
        request = self._call()
        players = request.response_json()
        for player in players:
            for field in _OUTPUT_FIELDS:
                self.assertIn(field, player, f"Missing field '{field}' in player: {player}")

    def test_no_extra_fields_in_response(self):
        """No columns beyond _OUTPUT_FIELDS must appear in the response.

        Leaking extra columns could expose internal data or bloat the response.
        """
        request = self._call()
        players = request.response_json()
        expected = set(_OUTPUT_FIELDS)
        for player in players:
            extra = set(player.keys()) - expected
            self.assertEqual(extra, set(), f"Unexpected fields in response: {extra}")

    def test_now_cost_is_divided_by_10(self):
        """FPL stores prices as integers × 10. We divide server-side."""
        request = self._call()
        players = request.response_json()
        # Fixture: Salah now_cost = 130 → should become 13.0
        salah = next(p for p in players if p["id"] == 1)
        self.assertAlmostEqual(salah["now_cost"], 13.0)

    def test_now_cost_is_float_not_integer(self):
        """now_cost must be a float (e.g. 13.0) not an integer (130)."""
        request = self._call()
        players = request.response_json()
        for player in players:
            self.assertIsInstance(
                player["now_cost"], float,
                f"now_cost should be float, got {type(player['now_cost'])}"
            )

    def test_full_name_is_concatenation_of_first_and_last(self):
        request = self._call()
        players = request.response_json()
        salah = next(p for p in players if p["id"] == 1)
        self.assertEqual(salah["full_name"], "Mohamed Salah")

    def test_position_is_derived_from_element_type(self):
        """element_type=3 → MID, element_type=4 → FWD."""
        request = self._call()
        players = request.response_json()
        salah = next(p for p in players if p["id"] == 1)
        haaland = next(p for p in players if p["id"] == 2)
        self.assertEqual(salah["position"], "MID")
        self.assertEqual(haaland["position"], "FWD")

    def test_team_id_is_resolved_to_short_name(self):
        """team=10 → 'LIV', team=14 → 'MCI'."""
        request = self._call()
        players = request.response_json()
        salah = next(p for p in players if p["id"] == 1)
        haaland = next(p for p in players if p["id"] == 2)
        self.assertEqual(salah["team"], "LIV")
        self.assertEqual(haaland["team"], "MCI")

    def test_security_headers_present(self):
        request = self._call()
        self.assertIn("x-content-type-options", request._headers)
        self.assertIn("x-frame-options", request._headers)
        self.assertIn("content-security-policy", request._headers)


class TestPlayersHandlerErrors(unittest.TestCase):
    """FPL API failures produce 502 with a generic message."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_network_failure_returns_502(self):
        """A requests.ConnectionError must produce 502, not 500 or a crash."""
        import requests as req
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get",
                   side_effect=req.exceptions.ConnectionError("FPL API unreachable")):
            serve_players(request)
        self.assertEqual(request.last_status, 502)

    def test_http_error_returns_502(self):
        """A 503 from the FPL API must produce 502 to the client."""
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse({}, status_code=503)
            serve_players(request)
        self.assertEqual(request.last_status, 502)

    def test_missing_elements_key_returns_502(self):
        """If the FPL API response has no 'elements' key, return 502."""
        bad_data = {"teams": _BOOTSTRAP["teams"]}  # elements key missing
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse(bad_data)
            serve_players(request)
        self.assertEqual(request.last_status, 502)

    def test_error_response_body_is_generic(self):
        """Error body must not contain exception details or stack traces."""
        import requests as req
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get",
                   side_effect=req.exceptions.ConnectionError("secret internal detail")):
            serve_players(request)
        body = request.response_body().decode()
        self.assertNotIn("secret internal detail", body)
        self.assertNotIn("Traceback", body)

    def test_timeout_is_passed_to_requests_get(self):
        """requests.get must be called with timeout=10 to prevent thread starvation."""
        request = MockRequest("/api/players")
        with patch("utils.loaders.base_loader.requests.get") as mock_get:
            mock_get.return_value = MockHTTPResponse(_BOOTSTRAP)
            serve_players(request)
            # Every call must have been made with timeout=10.
            for call in mock_get.call_args_list:
                _, kwargs = call
                self.assertEqual(
                    kwargs.get("timeout"), 10,
                    "requests.get called without timeout=10 — thread starvation risk"
                )


if __name__ == "__main__":
    unittest.main()

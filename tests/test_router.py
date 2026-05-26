"""
tests/test_router.py — Unit tests for router.Router.

Tests cover:
  - Correct dispatch to handler functions
  - 404 for unknown paths
  - 405 for wrong HTTP method (with Allow header)
  - 400 for null bytes in path
  - 414 for paths exceeding the length limit
  - Path normalisation (double slashes)
  - Named path parameter extraction (player_id)

How we test without an HTTP server:
    We create a MockRequest object that mimics the parts of
    BaseHTTPRequestHandler that the router reads (path, command) and writes
    to (send_response, send_header, end_headers, wfile). This lets the router
    run in complete isolation — no socket, no port, no thread.

Why mock at the request level and not patch handler functions?
    Patching handlers verifies that the router calls the right function.
    Using a mock request verifies the full dispatch path including how the
    router writes 4xx error responses. Both approaches are used below.
"""

import io
import unittest
from unittest.mock import patch

from router import Router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockRequest:
    """Minimal stand-in for BaseHTTPRequestHandler.

    Records all calls made by the router so tests can assert on them.
    wfile is a BytesIO buffer so written bytes can be inspected.
    """

    def __init__(self, path: str, method: str = "GET"):
        self.path = path
        self.command = method
        self.wfile = io.BytesIO()
        self._responses: list[int] = []
        self._headers: dict[str, str] = {}

    def send_response(self, code: int, message: str = None):
        self._responses.append(code)

    def send_header(self, name: str, value: str):
        self._headers[name.lower()] = value

    def end_headers(self):
        pass

    @property
    def last_status(self) -> int | None:
        return self._responses[-1] if self._responses else None

    def log_date_time_string(self):
        return "01/Jan/2026 00:00:00"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouterDispatch(unittest.TestCase):
    """Correct handler is called for valid routes."""

    def setUp(self):
        self.router = Router()

    # Patches target the module where the function lives, not router.py.
    # The router resolves handlers via getattr(module, func_name) at call
    # time, so patching the attribute on the source module is what works.

    def test_get_api_players_calls_serve_players(self):
        request = MockRequest("/api/players")
        with patch("handlers.players_handler.serve_players") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request)

    def test_get_api_player_history_calls_serve_history_with_id(self):
        request = MockRequest("/api/player/42/history")
        with patch("handlers.history_handler.serve_history") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request, player_id="42")

    def test_get_api_player_fixtures_calls_serve_fixtures_with_id(self):
        request = MockRequest("/api/player/7/fixtures")
        with patch("handlers.fixtures_handler.serve_fixtures") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request, player_id="7")

    def test_get_static_file_calls_serve_static(self):
        request = MockRequest("/static/js/app.js")
        with patch("handlers.static_handler.serve_static") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request)

    def test_get_root_calls_serve_static(self):
        request = MockRequest("/")
        with patch("handlers.static_handler.serve_static") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request)

    def test_player_id_is_passed_as_string(self):
        # The router passes player_id as a string — the handler converts to int.
        request = MockRequest("/api/player/999/history")
        with patch("handlers.history_handler.serve_history") as mock_handler:
            self.router.dispatch(request)
            _, kwargs = mock_handler.call_args
            self.assertIsInstance(kwargs["player_id"], str)
            self.assertEqual(kwargs["player_id"], "999")


class TestRouterNotFound(unittest.TestCase):
    """Unknown paths return 404."""

    def setUp(self):
        self.router = Router()

    def test_unknown_path_returns_404(self):
        request = MockRequest("/does/not/exist")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_partial_api_path_returns_404(self):
        request = MockRequest("/api")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_api_player_without_id_returns_404(self):
        request = MockRequest("/api/player//history")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_non_numeric_player_id_returns_404(self):
        # The route pattern requires digits only — letters must not match.
        request = MockRequest("/api/player/abc/history")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_float_player_id_returns_404(self):
        # A decimal point is not a digit — must not match.
        request = MockRequest("/api/player/4.2/history")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_negative_player_id_returns_404(self):
        # The minus sign is not matched by the digit pattern — must not match.
        request = MockRequest("/api/player/-1/history")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)


class TestRouterMethodEnforcement(unittest.TestCase):
    """Wrong HTTP method returns 405 with an Allow header."""

    def setUp(self):
        self.router = Router()

    def test_post_to_api_players_returns_405(self):
        request = MockRequest("/api/players", method="POST")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 405)

    def test_405_response_includes_allow_header(self):
        request = MockRequest("/api/players", method="DELETE")
        self.router.dispatch(request)
        self.assertIn("allow", request._headers)
        self.assertIn("GET", request._headers["allow"])

    def test_put_to_history_returns_405(self):
        request = MockRequest("/api/player/1/history", method="PUT")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 405)

    def test_head_to_unknown_path_returns_404_not_405(self):
        """404 takes priority over 405 — path is checked before method."""
        request = MockRequest("/does/not/exist", method="HEAD")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)


class TestRouterSecurityGuards(unittest.TestCase):
    """Security-critical input rejection."""

    def setUp(self):
        self.router = Router()

    def test_null_byte_in_path_returns_400(self):
        """Null bytes are always malformed and rejected before any matching."""
        request = MockRequest("/static/app.js\x00../../etc/passwd")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 400)

    def test_null_byte_in_api_path_returns_400(self):
        request = MockRequest("/api/players\x00extra")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 400)

    def test_path_exceeding_max_length_returns_414(self):
        long_path = "/api/players?" + "x" * 600
        request = MockRequest(long_path)
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 414)

    def test_path_at_max_length_boundary_is_processed(self):
        """A path of exactly MAX_PATH_LENGTH characters must not be rejected."""
        from router import _MAX_PATH_LENGTH

        # Build a path that hits exactly the limit.
        # /api/players is 12 chars; pad query string to reach limit.
        base = "/api/players?"
        padding = "x" * (_MAX_PATH_LENGTH - len(base))
        request = MockRequest(base + padding)
        # Should not return 414. May be 200 or 404 depending on handler behaviour.
        self.router.dispatch(request)
        self.assertNotEqual(request.last_status, 414)


class TestRouterPathNormalisation(unittest.TestCase):
    """Double slashes in paths are normalised before matching."""

    def setUp(self):
        self.router = Router()

    def test_double_slash_within_path_is_normalised(self):
        # /api//players has a double slash inside the path component.
        # urlparse leaves this in parsed.path; the router collapses it.
        request = MockRequest("/api//players")
        with patch("handlers.players_handler.serve_players") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once()

    def test_leading_double_slash_is_treated_as_protocol_relative_url(self):
        # //api/players is a protocol-relative URL per RFC 3986.
        # urlparse correctly parses netloc='api', path='/players'.
        # /players does not match any route — this is safe behaviour,
        # not a normalisation bug.
        request = MockRequest("//api/players")
        self.router.dispatch(request)
        self.assertEqual(request.last_status, 404)

    def test_triple_slash_is_normalised(self):
        request = MockRequest("///api/players")
        with patch("handlers.players_handler.serve_players") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once()


class TestRouterQueryStringIgnored(unittest.TestCase):
    """Query strings are stripped before route matching."""

    def setUp(self):
        self.router = Router()

    def test_query_string_on_players_route_is_ignored(self):
        request = MockRequest("/api/players?sort=name&page=1")
        with patch("handlers.players_handler.serve_players") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once()

    def test_query_string_on_history_route_is_ignored(self):
        request = MockRequest("/api/player/5/history?gw=10")
        with patch("handlers.history_handler.serve_history") as mock_handler:
            self.router.dispatch(request)
            mock_handler.assert_called_once_with(request, player_id="5")


class TestRouterUnhandledException(unittest.TestCase):
    """Unhandled exceptions in handlers do not crash the server thread."""

    def test_handler_exception_returns_500(self):
        """If a handler raises, the router catches it and returns 500."""
        router = Router()
        request = MockRequest("/api/players")

        with patch("handlers.players_handler.serve_players", side_effect=RuntimeError("boom")):
            router.dispatch(request)

        self.assertEqual(request.last_status, 500)

    def test_handler_exception_does_not_propagate(self):
        """Exception must not bubble up to the caller (server thread)."""
        router = Router()
        request = MockRequest("/api/players")

        with patch("handlers.players_handler.serve_players", side_effect=Exception("unexpected")):
            try:
                router.dispatch(request)
            except Exception as exc:
                self.fail(f"Exception propagated from router: {exc}")


if __name__ == "__main__":
    unittest.main()

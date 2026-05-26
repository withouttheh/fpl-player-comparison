"""
tests/handlers/test_static_handler.py — Unit tests for static_handler.serve_static.

Priority: this is the first handler test suite because static file serving
is the highest-risk handler in the project. The attack surface is the
filesystem — a path traversal bug serves arbitrary files to anyone.

Test categories:
  1. Path traversal attacks (the security-critical cases)
  2. Normal file serving (happy path)
  3. MIME type enforcement
  4. Edge cases (missing files, directories, encoded paths)

How we test without a real HTTP server:
    MockRequest mirrors the interface of BaseHTTPRequestHandler.
    The static handler reads request.path and writes to request.wfile.
    We check the recorded status codes and headers.

Why we create real temporary files:
    Path traversal tests must exercise the real filesystem because that is
    where the vulnerability lives. We create a controlled temp directory
    as the static root for each test, write known files into it, and verify
    the handler serves only those files.
"""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from handlers.static_handler import serve_static

# ---------------------------------------------------------------------------
# MockRequest
# ---------------------------------------------------------------------------


class MockRequest:
    """Stand-in for BaseHTTPRequestHandler used in all handler tests."""

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

    def response_body(self) -> bytes:
        return self.wfile.getvalue()


# ---------------------------------------------------------------------------
# Helper: temporary static root
# ---------------------------------------------------------------------------


class StaticHandlerTestCase(unittest.TestCase):
    """Base class that creates a temporary directory as the static root.

    Each test gets a fresh directory with no leftover files from other tests.
    We patch STATIC_ROOT in static_handler so the handler uses our temp dir
    instead of the real static/ folder.
    """

    def setUp(self):
        # Create a temporary directory to act as the static root.
        self._tmpdir = tempfile.TemporaryDirectory()
        self.static_root = Path(self._tmpdir.name)

        # Write a real file we can serve in happy-path tests.
        (self.static_root / "index.html").write_text(
            "<html><body>FPL</body></html>", encoding="utf-8"
        )
        (self.static_root / "style.css").write_text("body { margin: 0; }", encoding="utf-8")

        js_dir = self.static_root / "js"
        js_dir.mkdir()
        (js_dir / "app.js").write_text("console.log('FPL');", encoding="utf-8")

        # Patch STATIC_ROOT and INDEX_FILE in the handler module.
        self._root_patch = patch("handlers.static_handler.STATIC_ROOT", self.static_root.resolve())
        self._index_patch = patch(
            "handlers.static_handler.INDEX_FILE",
            (self.static_root / "index.html").resolve(),
        )
        self._root_patch.start()
        self._index_patch.start()

    def tearDown(self):
        self._root_patch.stop()
        self._index_patch.stop()
        self._tmpdir.cleanup()


# ---------------------------------------------------------------------------
# 1. Path traversal attacks
# ---------------------------------------------------------------------------


class TestPathTraversal(StaticHandlerTestCase):
    """The handler must never serve a file outside the static root.

    These test cases represent real attack patterns. Each one must return
    403 Forbidden, not 200 or 500.
    """

    def test_dotdot_in_path_is_blocked(self):
        # Classic path traversal: /static/../../server.py
        request = MockRequest("/static/../../server.py")
        serve_static(request)
        self.assertEqual(request.last_status, 403)

    def test_dotdot_in_subpath_is_blocked(self):
        # Traversal starting from a subdirectory.
        request = MockRequest("/static/js/../../../server.py")
        serve_static(request)
        self.assertEqual(request.last_status, 403)

    def test_absolute_path_is_blocked(self):
        # Attempting to serve an absolute path.
        request = MockRequest("/static//etc/passwd")
        serve_static(request)
        # Either 403 (traversal blocked) or 404 (file doesn't exist in static root).
        # Both are correct — 200 is not acceptable.
        self.assertIn(request.last_status, {403, 404})

    def test_encoded_dotdot_is_blocked(self):
        # %2e%2e is URL-encoded '..' — decoded by unquote() before path resolution.
        # After decoding: /static/../../server.py
        request = MockRequest("/static/%2e%2e/%2e%2e/server.py")
        serve_static(request)
        self.assertEqual(request.last_status, 403)

    def test_double_encoded_slash_is_blocked(self):
        # %2F is an encoded slash. Some naive implementations forget to decode.
        request = MockRequest("/static/..%2F..%2Fserver.py")
        serve_static(request)
        self.assertIn(request.last_status, {403, 404})

    def test_path_outside_static_root_is_blocked(self):
        # A file that exists on the system but is not in the static root.
        request = MockRequest("/static/../cache.py")
        serve_static(request)
        self.assertEqual(request.last_status, 403)

    def test_null_byte_path_does_not_serve_file(self):
        # Null bytes in paths are blocked by the router, but test defence in depth.
        # The static handler should not crash or serve unexpected content.
        request = MockRequest("/static/app.js\x00../../server.py")
        serve_static(request)
        # Any non-200 response is acceptable.
        self.assertNotEqual(request.last_status, 200)

    def test_directory_listing_is_blocked(self):
        # Requesting a directory path should return 404, not a file listing.
        request = MockRequest("/static/js/")
        serve_static(request)
        self.assertEqual(request.last_status, 404)

    def test_static_root_itself_is_not_served(self):
        # Requesting exactly /static/ should 404, not serve the directory.
        request = MockRequest("/static/")
        serve_static(request)
        self.assertEqual(request.last_status, 404)


# ---------------------------------------------------------------------------
# 2. Happy path: normal file serving
# ---------------------------------------------------------------------------


class TestNormalFileServing(StaticHandlerTestCase):
    """Files within the static root are served correctly."""

    def test_root_path_serves_index_html(self):
        request = MockRequest("/")
        serve_static(request)
        self.assertEqual(request.last_status, 200)
        self.assertIn(b"FPL", request.response_body())

    def test_static_css_file_is_served(self):
        request = MockRequest("/static/style.css")
        serve_static(request)
        self.assertEqual(request.last_status, 200)
        self.assertIn(b"margin", request.response_body())

    def test_static_js_file_in_subdirectory_is_served(self):
        request = MockRequest("/static/js/app.js")
        serve_static(request)
        self.assertEqual(request.last_status, 200)
        self.assertIn(b"FPL", request.response_body())

    def test_response_body_matches_file_contents_exactly(self):
        expected = b"body { margin: 0; }"
        request = MockRequest("/static/style.css")
        serve_static(request)
        self.assertEqual(request.response_body(), expected)

    def test_missing_file_returns_404(self):
        request = MockRequest("/static/does_not_exist.js")
        serve_static(request)
        self.assertEqual(request.last_status, 404)


# ---------------------------------------------------------------------------
# 3. MIME type enforcement
# ---------------------------------------------------------------------------


class TestMimeTypes(StaticHandlerTestCase):
    """Content-Type must always be set from the file extension, never guessed."""

    def test_html_file_has_html_content_type(self):
        request = MockRequest("/")
        serve_static(request)
        self.assertIn("text/html", request._headers.get("content-type", ""))

    def test_css_file_has_css_content_type(self):
        request = MockRequest("/static/style.css")
        serve_static(request)
        self.assertIn("text/css", request._headers.get("content-type", ""))

    def test_js_file_has_javascript_content_type(self):
        request = MockRequest("/static/js/app.js")
        serve_static(request)
        content_type = request._headers.get("content-type", "")
        # Browsers accept both text/javascript and application/javascript.
        self.assertTrue(
            "javascript" in content_type,
            f"Expected javascript content type, got: {content_type}",
        )

    def test_unknown_extension_falls_back_to_octet_stream(self):
        # A file with an unrecognised extension must use the safest default.
        # application/octet-stream tells the browser to treat it as a download,
        # not attempt to execute or render it.
        unknown_file = self.static_root / "data.fpl"
        unknown_file.write_bytes(b"\x00\x01\x02\x03")

        request = MockRequest("/static/data.fpl")
        serve_static(request)
        self.assertIn("octet-stream", request._headers.get("content-type", ""))

    def test_content_type_options_header_is_nosniff(self):
        # X-Content-Type-Options: nosniff must be set on every response.
        request = MockRequest("/static/style.css")
        serve_static(request)
        self.assertEqual(request._headers.get("x-content-type-options"), "nosniff")

    def test_security_headers_present_on_all_responses(self):
        request = MockRequest("/static/style.css")
        serve_static(request)
        self.assertIn("x-frame-options", request._headers)
        self.assertIn("content-security-policy", request._headers)
        self.assertIn("referrer-policy", request._headers)


# ---------------------------------------------------------------------------
# 4. Query strings and path edge cases
# ---------------------------------------------------------------------------


class TestPathEdgeCases(StaticHandlerTestCase):
    """Edge cases in how paths are interpreted."""

    def test_query_string_is_ignored_when_serving_file(self):
        # /static/style.css?v=123 should serve style.css, ignoring ?v=123.
        request = MockRequest("/static/style.css?v=123")
        serve_static(request)
        self.assertEqual(request.last_status, 200)
        self.assertIn(b"margin", request.response_body())

    def test_content_length_matches_actual_body_length(self):
        # Content-Length must match the actual bytes written.
        # A mismatch causes the client to wait or truncate the response.
        request = MockRequest("/static/style.css")
        serve_static(request)
        declared = int(request._headers.get("content-length", -1))
        actual = len(request.response_body())
        self.assertEqual(declared, actual)

    def test_path_with_space_encoded_as_percent20(self):
        # Create a file with a space in the name and serve it via %20.
        spaced_file = self.static_root / "my file.css"
        spaced_file.write_text("/* spaced */", encoding="utf-8")

        request = MockRequest("/static/my%20file.css")
        serve_static(request)
        self.assertEqual(request.last_status, 200)


if __name__ == "__main__":
    unittest.main()

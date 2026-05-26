"""
tests/helpers.py — Shared test utilities.

MockRequest and MockHTTPResponse are used across all handler test suites.
Defining them here avoids duplication and keeps the test files focused on
what they are testing, not on infrastructure.

Why not a pytest conftest.py fixture?
    MockRequest is a class, not a pytest fixture. It does not need the
    pytest fixture lifecycle (setup/teardown, scope, parametrize). A plain
    import is simpler and more explicit — you can see exactly where
    MockRequest comes from without knowing pytest's fixture resolution rules.
"""

import io
import json

import requests


class MockRequest:
    """Stand-in for BaseHTTPRequestHandler in handler unit tests.

    Records every call made by handlers so tests can assert on:
      - The HTTP status code (last_status)
      - The response headers (_headers dict)
      - The raw response bytes (response_body())
      - The decoded JSON body (response_json())
    """

    def __init__(self, path: str = "/", method: str = "GET"):
        self.path = path
        self.command = method
        self.wfile = io.BytesIO()
        self._responses: list[int] = []
        self._headers: dict[str, str] = {}

    def send_response(self, code: int, message: str = None):
        self._responses.append(code)

    def send_header(self, name: str, value: str):
        # Store headers in lowercase so assertions don't depend on casing.
        self._headers[name.lower()] = value

    def end_headers(self):
        pass

    @property
    def last_status(self) -> int | None:
        return self._responses[-1] if self._responses else None

    def response_body(self) -> bytes:
        return self.wfile.getvalue()

    def response_json(self) -> object:
        """Decode the response body as JSON. Raises if body is not valid JSON."""
        return json.loads(self.wfile.getvalue())

    def log_date_time_string(self) -> str:
        return "01/Jan/2026 00:00:00"


class MockHTTPResponse:
    """Stand-in for a requests.Response object.

    Used to mock requests.get() return values without making real HTTP calls.
    Mirrors the parts of requests.Response that BaseLoader.load_data() uses:
      - raise_for_status()
      - json()
    """

    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        """Raise requests.HTTPError if status_code indicates a failure."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._data


def make_url_router(routes: dict):
    """Return a side_effect function that maps URL substrings to mock responses.

    Used when a test needs requests.get() to return different data depending
    on which FPL endpoint is being called.

    Example:
        mock_get.side_effect = make_url_router({
            "bootstrap-static": MockHTTPResponse(BOOTSTRAP_DATA),
            "element-summary":  MockHTTPResponse(ELEMENT_SUMMARY_DATA),
        })

    The first route whose key appears as a substring in the URL wins.
    If no route matches, ConnectionError is raised — this makes unexpected
    URL calls fail loudly in tests rather than silently returning None.
    """

    def _side_effect(url: str, **kwargs):
        for substring, response in routes.items():
            if substring in url:
                return response
        raise requests.exceptions.ConnectionError(
            f"Test mock: no route for URL '{url}'. "
            f"Add it to the routes dict or check the handler's import path."
        )

    return _side_effect

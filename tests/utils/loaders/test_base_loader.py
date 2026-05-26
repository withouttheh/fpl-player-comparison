"""
tests/utils/loaders/test_base_loader.py — Unit tests for BaseLoader.load_data.

Tests cover:
  - Successful fetch returns parsed JSON
  - requests.get is called with timeout=10 (thread-starvation guard)
  - Non-200 responses raise and return None
  - Network failures return None (never propagate to caller)
  - Error output goes to stdout (current implementation) — captured so tests don't pollute output

The base_url + endpoint join is tested here because that logic lives in load_data.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import requests as req

from utils.loaders.base_loader import BaseLoader


class TestBaseLoaderSuccess(unittest.TestCase):
    def test_returns_parsed_json_on_success(self):
        loader = BaseLoader("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"key": "value"}

        with patch("utils.loaders.base_loader.requests.get", return_value=mock_resp):
            result = loader.load_data("some-endpoint/")

        self.assertEqual(result, {"key": "value"})

    def test_constructs_url_from_base_and_endpoint(self):
        loader = BaseLoader("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}

        with patch("utils.loaders.base_loader.requests.get", return_value=mock_resp) as mock_get:
            loader.load_data("bootstrap-static/")

        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://example.com/api/bootstrap-static/")

    def test_timeout_10_passed_to_requests_get(self):
        loader = BaseLoader("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}

        with patch("utils.loaders.base_loader.requests.get", return_value=mock_resp) as mock_get:
            loader.load_data("some/")

        _, kwargs = mock_get.call_args
        self.assertEqual(
            kwargs.get("timeout"), 10, "timeout=10 must be passed to prevent thread starvation"
        )

    def test_raise_for_status_is_called(self):
        """Non-2xx responses must be caught via raise_for_status."""
        loader = BaseLoader("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"ok": True}

        with patch("utils.loaders.base_loader.requests.get", return_value=mock_resp):
            loader.load_data("endpoint/")

        mock_resp.raise_for_status.assert_called_once()


class TestBaseLoaderFailures(unittest.TestCase):
    def test_connection_error_returns_none(self):
        loader = BaseLoader("https://example.com/api")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("unreachable"),
        ):
            result = loader.load_data("endpoint/")
        self.assertIsNone(result)

    def test_timeout_error_returns_none(self):
        loader = BaseLoader("https://example.com/api")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.Timeout("timed out"),
        ):
            result = loader.load_data("endpoint/")
        self.assertIsNone(result)

    def test_http_error_returns_none(self):
        """A 503 from the FPL API must return None, not crash."""
        loader = BaseLoader("https://example.com/api")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("503")

        with patch("utils.loaders.base_loader.requests.get", return_value=mock_resp):
            result = loader.load_data("endpoint/")

        self.assertIsNone(result)

    def test_network_failure_does_not_raise(self):
        """load_data must never propagate an exception to its caller."""
        loader = BaseLoader("https://example.com/api")
        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("network down"),
        ):
            try:
                loader.load_data("endpoint/")
            except Exception as exc:
                self.fail(f"load_data raised an exception: {exc}")


if __name__ == "__main__":
    unittest.main()

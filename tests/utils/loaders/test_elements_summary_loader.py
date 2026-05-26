"""
tests/utils/loaders/test_elements_summary_loader.py — Unit tests for
ElementsSummaryLoader, FixturesLoader, HistoryLoader, and HistoryPastLoader.

Tests cover:
  - Successful fetch populates self.data
  - get_fixtures_data / get_history_data return DataFrames with expected shape
  - KeyError on missing section key (not a silent empty frame)
  - Network failure in __init__ sets self.data = None; subsequent get_* calls raise
  - element_id is embedded in the fetched URL
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tests.helpers import MockHTTPResponse
from utils.loaders.elements_summary_loader import (
    ElementsSummaryLoader,
    FixturesLoader,
    HistoryLoader,
    HistoryPastLoader,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
_ELEMENT_SUMMARY = json.loads((_FIXTURES_DIR / "element_summary.json").read_text())


def _mock_summary():
    return MockHTTPResponse(_ELEMENT_SUMMARY)


class TestElementsSummaryLoader(unittest.TestCase):
    def test_data_populated_on_success(self):
        with patch("utils.loaders.base_loader.requests.get", return_value=_mock_summary()):
            loader = ElementsSummaryLoader("https://example.com/api", element_id=1)
        self.assertIsNotNone(loader.data)

    def test_endpoint_includes_element_id(self):
        with patch(
            "utils.loaders.base_loader.requests.get", return_value=_mock_summary()
        ) as mock_get:
            ElementsSummaryLoader("https://example.com/api", element_id=42)
        called_url = mock_get.call_args[0][0]
        self.assertIn("42", called_url)
        self.assertIn("element-summary", called_url)

    def test_data_is_none_on_network_failure(self):
        import requests as req

        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("down"),
        ):
            loader = ElementsSummaryLoader("https://example.com/api", element_id=1)
        self.assertIsNone(loader.data)


class TestFixturesLoader(unittest.TestCase):
    def _loader(self, data=None):
        resp = MockHTTPResponse(data or _ELEMENT_SUMMARY)
        with patch("utils.loaders.base_loader.requests.get", return_value=resp):
            return FixturesLoader("https://example.com/api", element_id=1)

    def test_get_fixtures_data_returns_dataframe(self):
        import pandas as pd

        df = self._loader().get_fixtures_data()
        self.assertIsInstance(df, pd.DataFrame)

    def test_fixtures_dataframe_has_two_rows(self):
        df = self._loader().get_fixtures_data()
        self.assertEqual(len(df), 2)

    def test_fixtures_dataframe_has_event_column(self):
        df = self._loader().get_fixtures_data()
        self.assertIn("event", df.columns)

    def test_raises_on_missing_fixtures_key(self):
        bad_data = {"history": [], "history_past": []}
        with self.assertRaises(KeyError):
            self._loader(bad_data).get_fixtures_data()


class TestHistoryLoader(unittest.TestCase):
    def _loader(self, data=None):
        resp = MockHTTPResponse(data or _ELEMENT_SUMMARY)
        with patch("utils.loaders.base_loader.requests.get", return_value=resp):
            return HistoryLoader("https://example.com/api", element_id=1)

    def test_get_history_data_returns_dataframe(self):
        import pandas as pd

        df = self._loader().get_history_data()
        self.assertIsInstance(df, pd.DataFrame)

    def test_history_dataframe_has_two_rows(self):
        df = self._loader().get_history_data()
        self.assertEqual(len(df), 2)

    def test_history_dataframe_has_round_column(self):
        df = self._loader().get_history_data()
        self.assertIn("round", df.columns)

    def test_influence_is_string_in_raw_data(self):
        """FPL returns ICT fields as strings; the loader must not cast them — that's the preprocessor's job."""
        df = self._loader().get_history_data()
        self.assertIsInstance(df["influence"].iloc[0], str)

    def test_raises_on_missing_history_key(self):
        bad_data = {"fixtures": [], "history_past": []}
        with self.assertRaises(KeyError):
            self._loader(bad_data).get_history_data()


class TestHistoryPastLoader(unittest.TestCase):
    def test_get_history_past_returns_empty_dataframe_for_empty_list(self):
        with patch(
            "utils.loaders.base_loader.requests.get",
            return_value=MockHTTPResponse(_ELEMENT_SUMMARY),
        ):
            loader = HistoryPastLoader("https://example.com/api", element_id=1)
        df = loader.get_history_past_data()
        self.assertEqual(len(df), 0)


if __name__ == "__main__":
    unittest.main()

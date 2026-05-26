"""
tests/utils/loaders/test_bootstrap_loader.py — Unit tests for BootstrapStaticLoader,
ElementsLoader, and TeamsLoader.

Tests cover:
  - Successful fetch populates self.data
  - get_elements_data returns a DataFrame with expected shape
  - get_teams_data returns a DataFrame with expected shape
  - Missing 'elements' or 'teams' key in API response returns None gracefully
  - Network failure in __init__ sets self.data = None without crashing
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tests.helpers import MockHTTPResponse
from utils.loaders.bootstrap_static_loader import (
    BootstrapStaticLoader,
    ElementsLoader,
    TeamsLoader,
)

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
_BOOTSTRAP = json.loads((_FIXTURES_DIR / "bootstrap_static.json").read_text())


def _mock_bootstrap():
    return MockHTTPResponse(_BOOTSTRAP)


class TestBootstrapStaticLoader(unittest.TestCase):
    def test_data_is_populated_on_success(self):
        with patch("utils.loaders.base_loader.requests.get", return_value=_mock_bootstrap()):
            loader = BootstrapStaticLoader("https://example.com/api")
        self.assertIsNotNone(loader.data)
        self.assertIn("elements", loader.data)
        self.assertIn("teams", loader.data)

    def test_data_is_none_on_network_failure(self):
        import requests as req

        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("down"),
        ):
            loader = BootstrapStaticLoader("https://example.com/api")
        self.assertIsNone(loader.data)

    def test_fetches_bootstrap_static_endpoint(self):
        with patch(
            "utils.loaders.base_loader.requests.get", return_value=_mock_bootstrap()
        ) as mock_get:
            BootstrapStaticLoader("https://example.com/api")
        called_url = mock_get.call_args[0][0]
        self.assertIn("bootstrap-static", called_url)


class TestElementsLoader(unittest.TestCase):
    def _loader(self):
        with patch("utils.loaders.base_loader.requests.get", return_value=_mock_bootstrap()):
            return ElementsLoader("https://example.com/api")

    def test_get_elements_data_returns_dataframe(self):
        import pandas as pd

        loader = self._loader()
        df = loader.get_elements_data()
        self.assertIsInstance(df, pd.DataFrame)

    def test_elements_dataframe_has_two_players(self):
        df = self._loader().get_elements_data()
        self.assertEqual(len(df), 2)

    def test_elements_dataframe_has_id_column(self):
        df = self._loader().get_elements_data()
        self.assertIn("id", df.columns)

    def test_returns_none_when_data_is_none(self):
        import requests as req

        with patch(
            "utils.loaders.base_loader.requests.get",
            side_effect=req.exceptions.ConnectionError("down"),
        ):
            loader = ElementsLoader("https://example.com/api")
        self.assertIsNone(loader.get_elements_data())

    def test_returns_none_when_elements_key_missing(self):
        bad_data = {"teams": _BOOTSTRAP["teams"]}
        with patch(
            "utils.loaders.base_loader.requests.get", return_value=MockHTTPResponse(bad_data)
        ):
            loader = ElementsLoader("https://example.com/api")
        self.assertIsNone(loader.get_elements_data())


class TestTeamsLoader(unittest.TestCase):
    def _loader(self):
        with patch("utils.loaders.base_loader.requests.get", return_value=_mock_bootstrap()):
            return TeamsLoader("https://example.com/api")

    def test_get_teams_data_returns_dataframe(self):
        import pandas as pd

        loader = self._loader()
        df = loader.get_teams_data()
        self.assertIsInstance(df, pd.DataFrame)

    def test_teams_dataframe_has_two_teams(self):
        df = self._loader().get_teams_data()
        self.assertEqual(len(df), 2)

    def test_teams_dataframe_has_short_name_column(self):
        df = self._loader().get_teams_data()
        self.assertIn("short_name", df.columns)

    def test_team_short_names_are_as_expected(self):
        df = self._loader().get_teams_data()
        short_names = set(df["short_name"].tolist())
        self.assertEqual(short_names, {"LIV", "MCI"})


if __name__ == "__main__":
    unittest.main()

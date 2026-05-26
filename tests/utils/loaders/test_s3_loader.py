"""
tests/utils/loaders/test_s3_loader.py — Unit tests for utils/loaders/s3_loader.py.

Tests cover both code paths:
  - FPL_MOCK=1: reads from data/ directory (no AWS credentials needed)
  - Real mode: calls boto3.client("s3").get_object (mocked via unittest.mock)

S3BootstrapLoader tests:
  - get_elements_data() returns a DataFrame on success
  - get_teams_data() returns a DataFrame on success
  - Returns None when the expected key is absent
  - Data is loaded lazily and cached in-object (second call does not re-read)

S3ElementSummaryLoader tests:
  - get_history_data() returns a DataFrame on success
  - get_history_data() raises KeyError when 'history' key is missing
  - get_fixtures_data() always returns an empty DataFrame (no upcoming fixtures)
  - Correct S3 key is constructed from bucket, season, and element_id
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.loaders.s3_loader import S3BootstrapLoader, S3ElementSummaryLoader

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
_BOOTSTRAP_JSON = json.loads((_DATA_DIR / "bootstrap_static.json").read_text())
_ELEMENT_SUMMARY_JSON = json.loads((_DATA_DIR / "element_summary.json").read_text())


class TestS3BootstrapLoaderMockMode(unittest.TestCase):
    """S3BootstrapLoader with FPL_MOCK=1 reads from data/ directory."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"FPL_MOCK": "1"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_get_elements_data_returns_dataframe(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        result = loader.get_elements_data()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertFalse(result.empty)

    def test_get_elements_data_has_id_column(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        df = loader.get_elements_data()
        self.assertIn("id", df.columns)

    def test_get_teams_data_returns_dataframe(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        result = loader.get_teams_data()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertFalse(result.empty)

    def test_get_teams_data_has_short_name_column(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        df = loader.get_teams_data()
        self.assertIn("short_name", df.columns)

    def test_get_elements_data_returns_none_on_missing_key(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        loader._data = {"teams": []}  # inject data without 'elements' key
        result = loader.get_elements_data()
        self.assertIsNone(result)

    def test_get_teams_data_returns_none_on_missing_key(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        loader._data = {"elements": []}  # inject data without 'teams' key
        result = loader.get_teams_data()
        self.assertIsNone(result)

    def test_get_elements_data_returns_none_when_data_is_none(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        loader._data = None
        with patch("utils.loaders.s3_loader._mock_get_json", return_value=None):
            result = loader.get_elements_data()
        self.assertIsNone(result)

    def test_data_loaded_lazily_on_first_call(self):
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        self.assertIsNone(loader._data)
        loader.get_elements_data()
        self.assertIsNotNone(loader._data)

    def test_data_cached_in_object_across_calls(self):
        """Second call to get_elements_data must not re-read the file."""
        loader = S3BootstrapLoader("test-bucket", "2025-26")
        with patch("utils.loaders.s3_loader._mock_get_json") as mock_read:
            mock_read.return_value = _BOOTSTRAP_JSON
            loader.get_elements_data()
            loader.get_elements_data()
            # File should only be read once.
            self.assertEqual(mock_read.call_count, 1)


class TestS3ElementSummaryLoaderMockMode(unittest.TestCase):
    """S3ElementSummaryLoader with FPL_MOCK=1 reads from data/ directory."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"FPL_MOCK": "1"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_get_history_data_returns_dataframe(self):
        loader = S3ElementSummaryLoader("test-bucket", "2025-26", 1)
        df = loader.get_history_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)

    def test_get_history_data_has_round_column(self):
        loader = S3ElementSummaryLoader("test-bucket", "2025-26", 1)
        df = loader.get_history_data()
        self.assertIn("round", df.columns)

    def test_get_history_data_raises_on_missing_key(self):
        loader = S3ElementSummaryLoader("test-bucket", "2025-26", 1)
        loader._data = {"fixtures": [], "history_past": []}  # no 'history' key
        with self.assertRaises(KeyError):
            loader.get_history_data()

    def test_get_fixtures_data_always_returns_empty_dataframe(self):
        """Completed seasons have no upcoming fixtures."""
        loader = S3ElementSummaryLoader("test-bucket", "2025-26", 1)
        df = loader.get_fixtures_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)

    def test_element_id_stored_on_instance(self):
        loader = S3ElementSummaryLoader("test-bucket", "2025-26", 42)
        self.assertEqual(loader.element_id, 42)


class TestS3BootstrapLoaderRealMode(unittest.TestCase):
    """S3BootstrapLoader without FPL_MOCK reads from S3 via boto3."""

    def _make_s3_response(self, data: dict):
        """Build a fake boto3 get_object response."""
        body = MagicMock()
        body.read.return_value = json.dumps(data).encode()
        return {"Body": body}

    def test_get_elements_data_calls_s3(self):
        loader = S3BootstrapLoader("my-bucket", "2025-26")
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = self._make_s3_response(_BOOTSTRAP_JSON)
        with patch("boto3.client", return_value=mock_s3):
            result = loader.get_elements_data()
        mock_s3.get_object.assert_called_once_with(
            Bucket="my-bucket", Key="fpl/2025-26/bootstrap_static.json"
        )
        self.assertIsInstance(result, pd.DataFrame)

    def test_s3_key_includes_season(self):
        loader = S3BootstrapLoader("my-bucket", "2024-25")
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = self._make_s3_response(_BOOTSTRAP_JSON)
        with patch("boto3.client", return_value=mock_s3):
            loader.get_elements_data()
        _, kwargs = mock_s3.get_object.call_args
        self.assertIn("2024-25", kwargs["Key"])

    def test_returns_none_on_s3_error(self):
        loader = S3BootstrapLoader("my-bucket", "2025-26")
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        with patch("boto3.client", return_value=mock_s3):
            result = loader.get_elements_data()
        self.assertIsNone(result)


class TestS3ElementSummaryLoaderRealMode(unittest.TestCase):
    """S3ElementSummaryLoader without FPL_MOCK reads from S3 via boto3."""

    def _make_s3_response(self, data: dict):
        body = MagicMock()
        body.read.return_value = json.dumps(data).encode()
        return {"Body": body}

    def test_get_history_data_calls_correct_s3_key(self):
        loader = S3ElementSummaryLoader("my-bucket", "2025-26", 99)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = self._make_s3_response(_ELEMENT_SUMMARY_JSON)
        with patch("boto3.client", return_value=mock_s3):
            loader.get_history_data()
        _, kwargs = mock_s3.get_object.call_args
        self.assertEqual(kwargs["Key"], "fpl/2025-26/element_summary/99.json")
        self.assertEqual(kwargs["Bucket"], "my-bucket")

    def test_returns_none_on_s3_error(self):
        loader = S3ElementSummaryLoader("my-bucket", "2025-26", 1)
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("AccessDenied")
        with patch("boto3.client", return_value=mock_s3):
            with self.assertRaises(KeyError):
                loader.get_history_data()


if __name__ == "__main__":
    unittest.main()

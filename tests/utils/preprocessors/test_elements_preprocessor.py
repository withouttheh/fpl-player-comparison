"""
tests/utils/preprocessors/test_elements_preprocessor.py — Unit tests for
ElementsPreprocessor and the two elements_summary preprocessors.

Tests cover:
  - ElementsPreprocessor.preprocess_elements adds full_name, position, resolves team
  - HistoryPreprocessor.preprocess_history resolves opponent_team to short name
  - FixturesPreprocessor.preprocess_fixtures resolves team_h and team_a to short names
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor
from utils.preprocessors.elements_summary_preprocessors import (
    FixturesPreprocessor,
    HistoryPreprocessor,
)


def _teams():
    return pd.DataFrame(
        [
            {"id": 10, "short_name": "LIV"},
            {"id": 14, "short_name": "MCI"},
        ]
    )


def _players():
    return pd.DataFrame(
        [
            {
                "id": 1,
                "first_name": "Mohamed",
                "second_name": "Salah",
                "element_type": 3,
                "team": 10,
                "now_cost": 130,
            },
            {
                "id": 2,
                "first_name": "Erling",
                "second_name": "Haaland",
                "element_type": 4,
                "team": 14,
                "now_cost": 150,
            },
        ]
    )


class TestElementsPreprocessor(unittest.TestCase):
    def _run(self):
        pp = ElementsPreprocessor(data=_players(), teams_data=_teams())
        return pp.preprocess_elements(team_columns=["team"])

    def test_full_name_is_added(self):
        df = self._run()
        self.assertIn("full_name", df.columns)
        self.assertListEqual(df["full_name"].tolist(), ["Mohamed Salah", "Erling Haaland"])

    def test_position_is_added(self):
        df = self._run()
        self.assertIn("position", df.columns)
        self.assertListEqual(df["position"].tolist(), ["MID", "FWD"])

    def test_team_id_resolved_to_short_name(self):
        df = self._run()
        self.assertListEqual(df["team"].tolist(), ["LIV", "MCI"])

    def test_original_id_column_preserved(self):
        df = self._run()
        self.assertIn("id", df.columns)


class TestHistoryPreprocessor(unittest.TestCase):
    def _history_df(self):
        return pd.DataFrame(
            [
                {"round": 1, "opponent_team": 14, "total_points": 12},
                {"round": 2, "opponent_team": 14, "total_points": 6},
            ]
        )

    def test_opponent_team_resolved_to_short_name(self):
        pp = HistoryPreprocessor(data=self._history_df(), teams_data=_teams())
        df = pp.preprocess_history(["opponent_team"])
        self.assertListEqual(df["opponent_team"].tolist(), ["MCI", "MCI"])

    def test_other_columns_untouched(self):
        pp = HistoryPreprocessor(data=self._history_df(), teams_data=_teams())
        df = pp.preprocess_history(["opponent_team"])
        self.assertListEqual(df["total_points"].tolist(), [12, 6])


class TestFixturesPreprocessor(unittest.TestCase):
    def _fixtures_df(self):
        return pd.DataFrame(
            [
                {"event": 30, "is_home": True, "difficulty": 2, "team_h": 10, "team_a": 14},
                {"event": 31, "is_home": False, "difficulty": 4, "team_h": 14, "team_a": 10},
            ]
        )

    def test_team_h_and_team_a_resolved(self):
        pp = FixturesPreprocessor(data=self._fixtures_df(), teams_data=_teams())
        df = pp.preprocess_fixtures(["team_h", "team_a"])
        self.assertListEqual(df["team_h"].tolist(), ["LIV", "MCI"])
        self.assertListEqual(df["team_a"].tolist(), ["MCI", "LIV"])

    def test_difficulty_column_untouched(self):
        pp = FixturesPreprocessor(data=self._fixtures_df(), teams_data=_teams())
        df = pp.preprocess_fixtures(["team_h", "team_a"])
        self.assertListEqual(df["difficulty"].tolist(), [2, 4])

    def test_is_home_column_untouched(self):
        pp = FixturesPreprocessor(data=self._fixtures_df(), teams_data=_teams())
        df = pp.preprocess_fixtures(["team_h", "team_a"])
        self.assertListEqual(df["is_home"].tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()

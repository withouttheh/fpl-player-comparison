"""
tests/utils/preprocessors/test_base_preprocessor.py — Unit tests for BasePreprocessor.

Tests cover:
  - _build_team_mapping produces correct id → short_name dict
  - _build_team_mapping returns {} when teams_data is None
  - replace_team_ids_with_names resolves integer IDs to short names in-place
  - replace_team_ids_with_names is a no-op when teams_data is absent
  - map_element_type_to_position maps 1→GK, 2→DEF, 3→MID, 4→FWD
  - create_full_name concatenates first_name and second_name
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from utils.preprocessors.base_preprocessor import BasePreprocessor


def _make_teams():
    return pd.DataFrame(
        [
            {"id": 10, "short_name": "LIV"},
            {"id": 14, "short_name": "MCI"},
        ]
    )


def _make_players():
    return pd.DataFrame(
        [
            {
                "id": 1,
                "first_name": "Mohamed",
                "second_name": "Salah",
                "element_type": 3,
                "team": 10,
            },
            {
                "id": 2,
                "first_name": "Erling",
                "second_name": "Haaland",
                "element_type": 4,
                "team": 14,
            },
        ]
    )


class TestTeamMapping(unittest.TestCase):
    def test_build_team_mapping_returns_correct_dict(self):
        teams = _make_teams()
        bp = BasePreprocessor(data=pd.DataFrame(), teams_data=teams)
        self.assertEqual(bp.team_mapping, {10: "LIV", 14: "MCI"})

    def test_build_team_mapping_returns_empty_dict_when_teams_data_is_none(self):
        bp = BasePreprocessor(data=pd.DataFrame(), teams_data=None)
        self.assertEqual(bp.team_mapping, {})

    def test_replace_team_ids_resolves_to_short_names(self):
        df = _make_players()
        bp = BasePreprocessor(data=df, teams_data=_make_teams())
        result = bp.replace_team_ids_with_names(["team"])
        self.assertListEqual(result["team"].tolist(), ["LIV", "MCI"])

    def test_replace_team_ids_is_noop_without_teams_data(self):
        df = _make_players()
        bp = BasePreprocessor(data=df.copy(), teams_data=None)
        result = bp.replace_team_ids_with_names(["team"])
        # Should be unchanged integers
        self.assertListEqual(result["team"].tolist(), [10, 14])

    def test_replace_team_ids_handles_multiple_columns(self):
        df = pd.DataFrame(
            [
                {"team_h": 10, "team_a": 14},
                {"team_h": 14, "team_a": 10},
            ]
        )
        bp = BasePreprocessor(data=df, teams_data=_make_teams())
        result = bp.replace_team_ids_with_names(["team_h", "team_a"])
        self.assertListEqual(result["team_h"].tolist(), ["LIV", "MCI"])
        self.assertListEqual(result["team_a"].tolist(), ["MCI", "LIV"])


class TestPositionMapping(unittest.TestCase):
    def test_gk_maps_from_element_type_1(self):
        df = pd.DataFrame([{"element_type": 1}])
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.map_element_type_to_position()
        self.assertEqual(bp.data["position"].iloc[0], "GK")

    def test_def_maps_from_element_type_2(self):
        df = pd.DataFrame([{"element_type": 2}])
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.map_element_type_to_position()
        self.assertEqual(bp.data["position"].iloc[0], "DEF")

    def test_mid_maps_from_element_type_3(self):
        df = pd.DataFrame([{"element_type": 3}])
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.map_element_type_to_position()
        self.assertEqual(bp.data["position"].iloc[0], "MID")

    def test_fwd_maps_from_element_type_4(self):
        df = pd.DataFrame([{"element_type": 4}])
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.map_element_type_to_position()
        self.assertEqual(bp.data["position"].iloc[0], "FWD")

    def test_all_four_positions_in_one_dataframe(self):
        df = pd.DataFrame(
            [
                {"element_type": 1},
                {"element_type": 2},
                {"element_type": 3},
                {"element_type": 4},
            ]
        )
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.map_element_type_to_position()
        self.assertListEqual(bp.data["position"].tolist(), ["GK", "DEF", "MID", "FWD"])


class TestFullName(unittest.TestCase):
    def test_create_full_name_concatenates_first_and_last(self):
        df = pd.DataFrame(
            [
                {"first_name": "Mohamed", "second_name": "Salah"},
            ]
        )
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.create_full_name()
        self.assertEqual(bp.data["full_name"].iloc[0], "Mohamed Salah")

    def test_full_name_for_multiple_players(self):
        df = pd.DataFrame(
            [
                {"first_name": "Mohamed", "second_name": "Salah"},
                {"first_name": "Erling", "second_name": "Haaland"},
            ]
        )
        bp = BasePreprocessor(data=df, teams_data=None)
        bp.create_full_name()
        self.assertListEqual(bp.data["full_name"].tolist(), ["Mohamed Salah", "Erling Haaland"])


if __name__ == "__main__":
    unittest.main()

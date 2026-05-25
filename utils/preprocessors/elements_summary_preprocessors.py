"""
utils/preprocessors/elements_summary_preprocessors.py — Transforms per-player
DataFrames from /element-summary/{id}/.

Three preprocessors, one per data section:

FixturesPreprocessor   — resolves team_h and team_a integer IDs to short names
                         so the frontend can display "LIV vs MCI" not "12 vs 13"

HistoryPreprocessor    — resolves opponent_team ID to short name
                         Note: ICT/xG float coercion is done in history_handler.py,
                         not here, because the handler knows which columns to coerce
                         and the preprocessor should not need to know about field names

HistoryPastPreprocessor — no transforms currently needed; past-season data from the
                          FPL API already uses team names, not IDs
"""

from utils.preprocessors.base_preprocessor import BasePreprocessor


class FixturesPreprocessor(BasePreprocessor):
	"""Preprocesses upcoming fixtures from element-summary."""

	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)

	def preprocess_fixtures(self, column_names):
		"""Resolve team IDs in column_names (e.g. team_h, team_a) to short names."""
		return self.replace_team_ids_with_names(column_names)


class HistoryPreprocessor(BasePreprocessor):
	"""Preprocesses this-season gameweek history from element-summary."""

	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)

	def preprocess_history(self, column_names):
		"""Resolve team IDs in column_names (e.g. opponent_team) to short names."""
		return self.replace_team_ids_with_names(column_names)


class HistoryPastPreprocessor(BasePreprocessor):
	"""Preprocesses previous-season summary data from element-summary. No team ID mapping needed."""

	def __init__(self, data):
		super().__init__(data)

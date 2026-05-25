"""
utils/preprocessors/bootstrap_static_preprocessors.py — Transforms the
player roster DataFrame from /bootstrap-static/.

ElementsPreprocessor takes the raw elements DataFrame (one row per player,
~80 columns) and applies three transforms in sequence:
  1. create_full_name()              — "Mohamed" + "Salah" → "Mohamed Salah"
  2. map_element_type_to_position()  — element_type 3 → "MID"
  3. replace_team_ids_with_names()   — team 12 → "LIV"

Why do this in the preprocessor rather than the handler?
    Handlers deal with HTTP: status codes, serialisation, caching. They
    should not also contain data wrangling logic. Keeping transforms here
    means they can be tested independently of the HTTP layer, and the handler
    stays short and readable.
"""

from utils.preprocessors.base_preprocessor import BasePreprocessor


class ElementsPreprocessor(BasePreprocessor):
	"""Preprocesses the elements (player roster) DataFrame from bootstrap-static."""

	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)

	def preprocess_elements(self, team_columns):
		"""Add full_name and position columns, then resolve team IDs in team_columns to short names."""
		self.create_full_name()
		self.map_element_type_to_position()
		return self.replace_team_ids_with_names(team_columns)

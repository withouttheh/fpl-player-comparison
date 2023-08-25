from utils.preprocessors.base_preprocessor import BasePreprocessor

class FixturesPreprocessor(BasePreprocessor):
	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)
		self.teams_data = teams_data

	def preprocess_fixtures(self, column_names):
		return self.replace_team_ids_with_names(column_names)

class HistoryPreprocessor(BasePreprocessor):
	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)
		self.teams_data = teams_data

	def preprocess_history(self, column_names):
		return self.replace_team_ids_with_names(column_names)


class HistoryPastPreprocessor(BasePreprocessor):
	def __init__(self, data):
		super().__init__(data)
from utils.preprocessors.base_preprocessor import BasePreprocessor


class ElementsPreprocessor(BasePreprocessor):
	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)
		self.teams_data = teams_data

	def preprocess_elements(self, column_name):
		return self.replace_team_ids_with_names(column_name)

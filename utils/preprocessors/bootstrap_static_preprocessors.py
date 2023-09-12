from utils.preprocessors.base_preprocessor import BasePreprocessor


class ElementsPreprocessor(BasePreprocessor):
	def __init__(self, data, teams_data):
		super().__init__(data, teams_data)
		self.teams_data = teams_data

	def preprocess_elements(self, column_name):
		self.create_full_name()
		self.map_element_type_to_position()
		return self.replace_team_ids_with_names(column_name)

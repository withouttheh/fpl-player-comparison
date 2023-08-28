from utils.loaders.bootstrap_static_loader import ElementsLoader, TeamsLoader
from utils.loaders.elements_summary_loader import FixturesLoader, HistoryLoader, HistoryPastLoader
from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor, HistoryPreprocessor, HistoryPastPreprocessor

from utils.config import base_url

class PlayerModel:
	def __init__(self):
		self.base_url = base_url
		self.teams_data = self.load_and_preprocess_teams_data()
		self.elements_data = self.load_and_preprocess_elements_data()
		self.fixtures_data = self.load_and_preprocess_fixtures_data()
		self.history_data = self.load_and_preprocess_history_data()
		self.history_data = None


	def load_and_preprocess_elements_data(self):
		elements_loader = ElementsLoader(self.base_url)
		elements_data = elements_loader.get_elements_data()
		elements_preprocessor = ElementsPreprocessor(elements_data, self.teams_data)
		column_name = ['team']
		return elements_preprocessor.preprocess_elements(column_name)

	def load_and_preprocess_teams_data(self):
		teams_loader = TeamsLoader(self.base_url)
		return teams_loader.get_teams_data()

	def load_and_preprocess_fixtures_data(self):
		fixtures_loader = FixturesLoader(self.base_url)
		fixtures_data = fixtures_loader.get_fixtures_data()
		fixtures_preprocessor = FixturesPreprocessor(fixtures_data, self.teams_data)
		column_names = ['team_h', 'team_a']
		return fixtures_preprocessor.preprocess_fixtures(column_names)

	def load_and_preprocess_history_data(self):
		history_loader = HistoryLoader(self.base_url)
		history_data = history_loader.get_history_data()
		history_preprocessor = HistoryPreprocessor(history_data, self.teams_data)
		column_names = ['opponent_team']
		return history_preprocessor.preprocess_history(column_names)

	def get_player_data(self, web_name):
		return self.elements_data.loc[self.elements_data['web_name'] == web_name]

	def get_fixtures_data(self, player_id):
		fixtures_loader = FixturesLoader(self.base_url, player_id)
		return self.fixtures_loader.get_fixtures_data()

	def get_history_data(self, player_id):
		history_loader = HistoryLoader(self.base_url, player_id)
		return self.history_loader.get_history_data(player_id)
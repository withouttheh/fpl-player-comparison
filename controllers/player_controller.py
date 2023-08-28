from models.player_model import PlayerModel
from views.player_view import PlayerView
from utils.loaders.elements_summary_loader import FixturesLoader, HistoryLoader
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor, HistoryPreprocessor

from utils.config import base_url

class PlayerController:
	def __init__(self):
		self.model = PlayerModel()
		self.view = PlayerView()


	def display_player_info(self, web_name):
		player_data = self.model.get_player_data(web_name)
		player_id = player_data['id'].values[0]
		player_team = player_data['team'].values[0]


		#Upcoming fixtures
		fixtures_loader = FixturesLoader(self.model.base_url, player_id)
		fixtures_data = fixtures_loader.get_fixtures_data()
		fixtures_preprocessor = FixturesPreprocessor(fixtures_data, self.model.teams_data)

		column_names = ['team_h', 'team_a']
		fixtures_data = fixtures_preprocessor.preprocess_fixtures(column_names)
		fixtures_data['opponent'] = fixtures_data.apply(lambda row: row['team_h'] if row['team_a'] == player_team else row['team_a'], axis=1)

		#Past fixtures
		history_loader = HistoryLoader(self.model.base_url, player_id)
		history_data = history_loader.get_history_data()
		history_preprocessor = HistoryPreprocessor(history_data, self.model.teams_data)
		column_names = ['opponent_team']
		history_data = history_preprocessor.preprocess_history(column_names)


		self.view.render_player_info(player_data, fixtures_data, history_data)

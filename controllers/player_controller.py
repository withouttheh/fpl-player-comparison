from models.player_model import PlayerModel
from views.player_view import PlayerView
from utils.loaders.elements_summary_loader import FixturesLoader, HistoryLoader
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor, HistoryPreprocessor

from utils.config import base_url

import plotly.express as px
import pandas as pd

class PlayerController:
	def __init__(self):
		self.model = PlayerModel()
		self.view = PlayerView()


	def display_player_info(self, full_name):
		player_data = self.model.get_player_data(full_name)
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

	def plot_side_by_side_bar(self, player_names, gw_range, stat): 

		dfs = []

		for player_name in player_names:
			player_data = self.model.get_player_data(player_name)
			player_id = player_data['id'].values[0]

			history_loader = HistoryLoader(self.model.base_url, player_id)
			history_data = history_loader.get_history_data()

			selected_history_data_range = history_data.iloc[gw_range[0] - 1 : gw_range[1]]
			selected_history_data_range.loc[:, 'name'] = player_name
			selected_history_data_range.loc[:, 'gameweek'] = selected_history_data_range['round'].apply(lambda x: f'GW {x}')
			dfs.append(selected_history_data_range)

		df = pd.concat(dfs, ignore_index=True).sort_values('gameweek')
		fig = px.histogram(df, x="gameweek", y=stat, color="name", barmode="group", text_auto=True) 

		self.view.render_side_by_side_bar(fig)

	def plot_side_by_side_line(self, player_names, gw_range, stat): 

		dfs = []

		for player_name in player_names:
			player_data = self.model.get_player_data(player_name)
			player_id = player_data['id'].values[0]

			history_loader = HistoryLoader(self.model.base_url, player_id)
			history_data = history_loader.get_history_data()
			print(history_data.info())
			
			selected_columns = ['influence', 'creativity', 'threat', 'ict_index', 'expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded']
			history_data[selected_columns] = history_data[selected_columns].astype(float)
		
			numeric_columns = history_data.select_dtypes(include=['int', 'float'])
			numeric_columns.drop(columns=['round'], inplace=True)
			cumulative_sum = numeric_columns.cumsum()
			history_data[numeric_columns.columns] = cumulative_sum

			selected_history_data_range = history_data.iloc[gw_range[0] - 1 : gw_range[1]]
			selected_history_data_range.loc[:, 'name'] = player_name
			selected_history_data_range.loc[:, 'gameweek'] = selected_history_data_range['round'].apply(lambda x: f'GW {x}')
			dfs.append(selected_history_data_range) 

		df = pd.concat(dfs, ignore_index=True).sort_values('gameweek')
		fig = px.line(df, x="gameweek", y=stat, color="name", markers=True) 

		self.view.render_side_by_side_line(fig)
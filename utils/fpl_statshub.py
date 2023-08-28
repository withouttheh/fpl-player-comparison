from utils.loaders.bootstrap_static_loader import TeamsLoader
from utils.loaders.elements_summary_loader import FixturesLoader, HistoryLoader, HistoryPastLoader
from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor, HistoryPreprocessor, HistoryPastPreprocessor

import pandas as pd

class FplStatsHub:
    def __init__(self, base_url):
        self.base_url = base_url
        self.teams_loader = TeamsLoader(self.base_url)
        self.elements_loader = ElementsLoader(self.base_url)
        self.fixtures_loader = FixturesLoader(self.base_url)
        self.history_loader = HistoryLoader(self.base_url)
        self.history_past_loader = HistoryPastLoader(self.base_url)
        self.column_names_elements = ['team']
        self.column_names_fixtures = ['team_h', 'team_a']
        self.column_names_history = ['opponent_team']

    def load_and_preprocess_data(self):
        elements_data = self.elements_loader.get_elements_data()
        teams_data = self.teams_loader.get_teams_data()
        fixtures_data = self.fixtures_loader.get_fixtures_data()
        history_data = self.history_loader.get_history_data()
        history_past_data = self.history_past_loader.get_history_past_data()

        elements_preprocessor = ElementsPreprocessor(elements_data, teams_data)
        fixtures_preprocessor = FixturesPreprocessor(fixtures_data, teams_data)
        history_preprocessor = HistoryPreprocessor(history_data, teams_data)
        history_past_preprocessor = HistoryPastPreprocessor(history_past_data)

        self.elements_data = elements_preprocessor.preprocess_elements(self.column_names_elements)
        self.teams_data = teams_data
        self.fixtures_data = fixtures_preprocessor.preprocess_fixtures(self.column_names_fixtures)
        self.history_data = history_preprocessor.preprocess_history(self.column_names_history)
        self.history_past_data = history_past_data

    def display_player_info(self, col, web_name):

    	player_data = self.elements_data.loc[self.elements_data['web_name'] == web_name]
    	player_id = player_data['id'].values[0]
    	player_team = player_data['team'].values[0]

    	fixtures_data = FixturesLoader(self.base_url, player_id).get_fixtures_data()
    	fixtures_preprocessor = FixturesPreprocessor(fixtures_data, self.teams_data)
    	fixtures_data = fixtures_preprocessor.preprocess_fixtures(self.column_names_fixtures)
    	fixtures_data['opponent'] = fixtures_data.apply(lambda row: row['team_h'] if row['team_a'] == player_team else row['team_a'], axis=1)

    	history_data_cols = ['opponent_team', 'minutes', 'total_points', 'goals_scored', 'assists', 'clean_sheets', 'bps' ]
    	history_data =  HistoryLoader(self.base_url, player_id).get_history_data()
    	history_preprocessor = HistoryPreprocessor(history_data, self.teams_data)
    	history_data = history_preprocessor.preprocess_history(self.column_names_history)


    	col.text(f"Team: {player_data['team'].values[0]}")
    	col.text(f"Selected by: {player_data['selected_by_percent'].values[0]}%")
    	col.text(f"Price: {player_data['now_cost'].values[0] / 10}")

    	def display_styled_markdown(col, text, styles):
	    	style_str = ";".join([f"{key}:{value}" for key, value in styles.items()])
	    	styled_text = f"<p style='{style_str}'>{text}</p>"
	    	col.markdown(styled_text, unsafe_allow_html=True)
    	styles = {
    		'text-align': 'center'
    		}

    	text = "Averages"
    	display_styled_markdown(col, text, styles)

    	# col.text(history_data['minutes'].mean())
    	col.table(fixtures_data['opponent'].head(6)) 
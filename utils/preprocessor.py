import pandas as pd
import numpy as np
import requests

class Preprocessor:
    def __init__(self, elements_data, teams_data):
        self.elements_df = pd.DataFrame(elements_data)
        self.teams_df = pd.DataFrame(teams_data)
        self.team_mapping = self.create_team_mapping()

    def create_team_mapping(self):
        team_codes = self.elements_df['team'].unique()
        team_names = self.teams_df['short_name'].unique()
        return dict(zip(team_codes, team_names))

    def get_player_data(self, web_name):
        player_data = self.elements_df[self.elements_df['web_name'] == web_name]
        return player_data
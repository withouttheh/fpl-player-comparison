import pandas as pd
import numpy as np
import requests


class FPLStatsHub:
    def __init__(self, data_loader, preprocessor, player_data_retriever):
        self.data_loader = data_loader
        self.preprocessor = preprocessor
        self.player_data_retriever = player_data_retriever

    def display_player_info(self, col, web_name):
        player_data = self.preprocessor.get_player_data(web_name)
        col.text(f"Team: {self.preprocessor.team_mapping[player_data['team'].values[0]]}")
        col.text(f"Selected by: {player_data['selected_by_percent'].values[0]}%")
        col.text(f"Price: {player_data['now_cost'].values[0] / 10}")

      # Get the element_id for the selected player from the Preprocessor's DataFrame
        element_id = self.preprocessor.elements_df.loc[self.preprocessor.elements_df['web_name'] == web_name, 'id'].values[0]
        
        # Retrieve player's detailed data
        player_data = self.player_data_retriever.get_player_data(element_id)
        
        if player_data:
            fixtures = player_data.get("fixtures")
            history = player_data.get("history")
            history_past = player_data.get("history_past")
            col.text("Player's Detailed Data:")
            col.write("Fixtures:", fixtures)
            col.write("History:", history)
            col.write("History Past:", history_past)
        else:
            col.text("Failed to retrieve player's detailed data.")

class PlayerDataRetriever:
    def __init__(self, base_url):
        self.base_url = base_url

    def get_player_data(self, element_id):
        """Retrieve player's detailed data using the element_id."""
        endpoint = f"element-summary/{element_id}/"
        full_url = f"{self.base_url}/{endpoint}"
        response = requests.get(full_url)
        
        if response.status_code == 200:
            player_data = response.json()
            return player_data
        else:
            return None
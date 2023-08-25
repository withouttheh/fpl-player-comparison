import streamlit as st
import pandas as pd
import numpy as np
import requests

import streamlit as st
from utils.fpl_statshub import FplStatsHub
from utils.loaders.bootstrap_static_loader import ElementsLoader
from utils.loaders.bootstrap_static_loader import TeamsLoader

from utils.loaders.elements_summary_loader import FixturesLoader
from utils.loaders.elements_summary_loader import HistoryLoader
from utils.loaders.elements_summary_loader import HistoryPastLoader

# Define the base URL
base_url = "https://fantasy.premierleague.com/api"

# Create an instance of FplStatsHub
fpl_statshub = FplStatsHub(base_url)

# Load and preprocess data
fpl_statshub.load_and_preprocess_data()

# Display the processed data using st.write
st.title('FPL StatsHub')

st.subheader('Elements Data')
st.write(fpl_statshub.elements_data)

elements_loader = TeamsLoader(base_url)
elements_data = elements_loader.get_teams_data()  

st.write(elements_data)

elements_loader = FixturesLoader(base_url)
elements_data = elements_loader.get_fixtures_data()  

st.write(elements_data)


st.subheader('Fixtures Data')
st.write(fpl_statshub.fixtures_data)

st.subheader('History Data')
st.write(fpl_statshub.history_data)

st.subheader('History Past Data')
st.write(fpl_statshub.history_past_data)


# from utils.fplstatshub import FPLStatsHub, PlayerDataRetriever
# from utils.loaders.bootstrap_static_loader import ElementsLoader, TeamsLoader
# from utils.loaders.elements_summary_loader import FixturesLoader, HistoryLoader, HistoryPastLoader

# from utils.preprocessor import Preprocessor

# base_url = "https://fantasy.premierleague.com/api"
# st.title('FPL StatsHub')

# elements_loader = ElementsLoader(base_url)
# elements_data = elements_loader.get_elements_data()  

# teams_loader = TeamsLoader(base_url)
# teams_data = teams_loader.get_teams_data()

# st.write(elements_data.head())
# st.write(teams_data.head())

# element_id = 5  # Example element_id

# fixtures_loader = FixturesLoader(base_url, element_id)
# fixtures = fixtures_loader.get_fixtures_data()

# history_loader = HistoryLoader(base_url, element_id)
# history = history_loader.get_history_data()

# history_past_loader = HistoryPastLoader(base_url, element_id)
# history_past = history_past_loader.get_history_past_data()

# st.write("Remaining Fixtures:", fixtures)
# st.write("Past Games This Season:", history)
# st.write("Past Seasons:", history_past)


# elements_data = data['elements']
# teams_data = data['teams']

# preprocessor = Preprocessor(elements_data, teams_data)
# player_data_retriever = PlayerDataRetriever('https://fantasy.premierleague.com/api')
# stats_hub = FPLStatsHub(data_loader, preprocessor, player_data_retriever)

# col1, col2, col3 = st.columns(3)


# st.subheader('Raw data')

# with col1:
#     st.header("Column 1")
#     st.write("This is the first column.")
#     selected_player1 = st.selectbox("Player", options=preprocessor.elements_df['web_name'].sort_values(), key="Player 1")
#     st.write('You selected:', selected_player1)
#     stats_hub.display_player_info(col1, selected_player1)

# with col2:
#     st.header("Column 2")
#     st.write("This is the second column.")

# with col3:
#     st.header("Column 3")
#     st.write("This is the third column.")
#     selected_player2 = st.selectbox("Player", options=preprocessor.elements_df['web_name'].sort_values(), key="Player 2")
#     st.write('You selected:', selected_player2)
#     stats_hub.display_player_info(col3, selected_player2)




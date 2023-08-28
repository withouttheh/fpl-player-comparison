import streamlit as st
from controllers.player_controller import PlayerController

st.title("FPL Player Info App")

player_controller = PlayerController()
 
col1, col2 = st.columns(2)

with col1:
    selected_player1 = st.selectbox("Player", options=player_controller.model.elements_data['web_name'].sort_values(), key="Player 1")
    player_controller.display_player_info(selected_player1)

with col2:
    selected_player2 = st.selectbox("Player", options=player_controller.model.elements_data['web_name'].sort_values(), key="Player 2")
    player_controller.display_player_info(selected_player2)

# # Define the base URL
# base_url = "https://fantasy.premierleague.com/api"

# # Create an instance of FplStatsHub
# fpl_statshub = FplStatsHub(base_url)

# # Load and preprocess data
# fpl_statshub.load_and_preprocess_data()

# # # Display the processed data using st.write
# # st.title('FPL StatsHub')

# # st.subheader('Elements Data')
# # st.write(fpl_statshub.elements_data)

# # st.subheader('Fixtures Data')
# # st.write(fpl_statshub.fixtures_data)

# # st.subheader('History Data')
# # st.write(fpl_statshub.history_data)

# # st.subheader('History Past Data')
# # st.write(fpl_statshub.history_past_data)

# col1, col2 = st.columns(2)

# st.subheader('Raw data')

# with col1:
#     st.header("Column 1")
#     st.write("This is the first column.")
#     selected_player1 = st.selectbox("Player", options=fpl_statshub.elements_data['web_name'].sort_values(), key="Player 1")
#     st.write('You selected:', selected_player1)
#     fpl_statshub.display_player_info(col1, selected_player1)

# with col2:
#     st.header("Column 2")
#     st.write("This is the third column.")
#     selected_player2 = st.selectbox("Player", options=fpl_statshub.elements_data['web_name'].sort_values(), key="Player 2")
#     st.write('You selected:', selected_player2)
#     fpl_statshub.display_player_info(col2, selected_player2)




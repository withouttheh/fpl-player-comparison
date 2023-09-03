import streamlit as st
from controllers.player_controller import PlayerController

st.set_page_config()


st.markdown(f"<p style='text-align: center; font-size: 32px; font-weight: 700; margin-bottom: 16px;'>FPL Player Comparison</p>", unsafe_allow_html=True)
		
player_controller = PlayerController()
 
col1, col2 = st.columns(2)
 
with col1:
    selected_player1 = st.selectbox("Type player name...", options=player_controller.model.elements_data['web_name'].sort_values(), key="Player 1")
    player_controller.display_player_info(selected_player1)

with col2:
    selected_player2 = st.selectbox("Type player name...", options=player_controller.model.elements_data['web_name'].sort_values(), key="Player 2")
    player_controller.display_player_info(selected_player2)

columns = ['total_points', 'minutes',
       'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
       'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards',
       'red_cards', 'saves', 'bonus', 'bps', 'influence', 'creativity',
       'threat', 'ict_index', 'expected_goals', 'expected_assists',
       'expected_goal_involvements', 'expected_goals_conceded', 'value',
       'transfers_balance', 'selected', 'transfers_in', 'transfers_out']

print(player_controller.model.history_data[columns])

season_stats = st.selectbox("Select stat...", options=columns, key="Stats")

slider_min = 1
slider_max = player_controller.model.history_data['fixture'].size	

gw_slider = st.slider('Gameweek', min_value=slider_min, max_value=slider_max, value=(slider_min, slider_max), key='gw_slider')

players = [selected_player1, selected_player2]
player_controller.plot_side_by_side_bar(players, gw_slider, season_stats)
player_controller.plot_side_by_side_line(players, gw_slider, season_stats)


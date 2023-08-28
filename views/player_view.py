import streamlit as st

class PlayerView:
	def render_player_info(self, player_data, fixtures_data):
		st.text(f"Team: {player_data['team'].values[0]}")
		st.text(f"Selected by: {player_data['selected_by_percent'].values[0]}%")
		st.text(f"Price: {player_data['now_cost'].values[0] / 10}")
		st.write("Next Fixtures:")
		st.table(fixtures_data['opponent'][:6])  # Customize columns as needed
import streamlit as st

class PlayerView:
	def render_player_info(self, player_data, fixtures_data, history_data):
		st.markdown(f"<p style='text-align: center;'><strong>Team:</strong>  {player_data['team'].values[0]}</p>", unsafe_allow_html=True)
		st.markdown(f"<p style='text-align: center;'><strong>Selected by:  </strong>{player_data['selected_by_percent'].values[0]}%</p>", unsafe_allow_html=True)
		st.markdown(f"<p style='text-align: center;'><strong>Price:  </strong>{player_data['now_cost'].values[0] / 10}</p>", unsafe_allow_html=True)
		
		# Render the fixtures table
		st.markdown("<p style='text-align: center;'><strong>Upcoming Fixtures:</strong></p>", unsafe_allow_html=True)
		
		fixtures_table_html = "<table style='margin-bottom: 16px;'><tr>"

		for _, row in fixtures_data.head(6).iterrows():
			opponent_team = row['opponent']
			fixtures_table_html += f"<td>{opponent_team}</td>"

		fixtures_table_html += "</tr></table>"

		st.markdown(fixtures_table_html, unsafe_allow_html=True)

		# Render the history table
		st.markdown("<p style='text-align: center;'><strong>Past Fixtures:</strong></p>", unsafe_allow_html=True)
		
		history_table_html = "<table style='margin-bottom: 16px; margin-left: auto; margin-right: auto;'>"
		history_table_html += "<tr><th>Team</th><th>Mins</th><th>Pts</th><th>BP</th><th>GS</th><th>A</th><th>GC</th></tr>"

		for _, row in history_data.head(5).iterrows():
			opponent_team = row['opponent_team']
			minutes = row['minutes']
			points = row['total_points']
			bonus_points = row['bonus']
			goals_scored = row['goals_scored']
			assists = row['assists']
			goals_conceded = row['goals_conceded']
			history_table_html += f"<tr><td>{opponent_team}</td><td>{minutes}</td><td>{points}</td><td>{bonus_points}</td><td>{goals_scored}</td><td>{assists}</td><td>{goals_conceded}</td></tr>"

		history_table_html += "</table>"

		st.markdown(history_table_html, unsafe_allow_html=True)
	
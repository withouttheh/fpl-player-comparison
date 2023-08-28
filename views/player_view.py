import streamlit as st

class PlayerView:
	def render_player_info(self, player_data, fixtures_data):
		st.markdown(f"<p style='text-align: center;'><strong>Team:</strong>  {player_data['team'].values[0]}</p>", unsafe_allow_html=True)
		st.markdown(f"<p style='text-align: center;'><strong>Selected by:  </strong>{player_data['selected_by_percent'].values[0]}%</p>", unsafe_allow_html=True)
		st.markdown(f"<p style='text-align: center;'><strong>Price:  </strong>{player_data['now_cost'].values[0] / 10}</p>", unsafe_allow_html=True)
		st.markdown("<p style='text-align: center;'><strong>Upcoming Fixtures:</strong></p>", unsafe_allow_html=True)
		
		table_html = "<table><tr>"

		for _, row in fixtures_data.head(6).iterrows():
			opponent_team = row['opponent']
			table_html += f"<td>{opponent_team}</td>"

		table_html += "</tr></table>"

		st.markdown(table_html, unsafe_allow_html=True)
	
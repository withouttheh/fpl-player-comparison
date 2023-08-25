import numpy as np

class BasePreprocessor:
	def __init__(self, data=None, teams_data=None):
		self.data = data
		self.teams_data = teams_data
		self.team_mapping = self.create_team_mapping()

	def create_team_mapping(self):
		if self.teams_data is None:
			return {}

		team_mapping = dict(zip(self.teams_data['id'], self.teams_data['short_name']))
		return team_mapping

	def replace_team_ids_with_names(self, column_names):
		if self.team_mapping:
			for column_name in column_names:
				self.data[column_name] = self.data[column_name].map(self.team_mapping)
		return self.data

    # def create_team_mapping(self, column_names):
    #     if self.teams_data is not None:
    #     	for column_name in column_names:
    #     		team_codes = np.sort(self.data[column_name].unique())
    #     		team_mapping = dict(zip(self.teams_data['id'], self.teams_data['short_name']))
    #     		print(teams_dict)
    #     		self.data.loc[:, column_name] = self.data[column_name].apply(lambda x: teams_dict.get(x, x))
    #     return self.data

# class BasePreprocessor:
#     def __init__(self, data=None, teams_data=None):
#         self.data = data
#         self.teams_data = teams_data
#         self.team_mapping = self.create_team_mapping()

#     def create_team_mapping(self):
#         if self.teams_data is None:
#             return {}

#         team_mapping = dict(zip(self.teams_data['id'], self.teams_data['short_name']))
#         return team_mapping

#     def replace_team_ids_with_names(self, column_name):
#         if self.team_mapping:
#             self.data[column_name] = self.data[column_name].map(self.team_mapping)
#         return self.data





from utils.loaders.base_loader import BaseLoader
import pandas as pd

class ElementsSummaryLoader(BaseLoader):
	def __init__(self, base_url, element_id):
		super().__init__(base_url)
		self.endpoint = f"element-summary/{element_id}/"
		self.data = self.load_data(self.endpoint)

class FixturesLoader(ElementsSummaryLoader):
	def __init__(self, base_url, element_id=1):
		super().__init__(base_url, element_id)

	def get_fixtures_data(self):
		fixtures = pd.DataFrame(self.data['fixtures'])
		return fixtures


class HistoryLoader(ElementsSummaryLoader):
	def __init__(self, base_url, element_id=1):
		super().__init__(base_url, element_id)

	def get_history_data(self):
		history = pd.DataFrame(self.data['history'])
		return history

class HistoryPastLoader(ElementsSummaryLoader):
	def __init__(self, base_url, element_id=1):
		super().__init__(base_url, element_id)

	def get_history_past_data(self):
		history_past = pd.DataFrame(self.data['history_past'])
		return history_past
 
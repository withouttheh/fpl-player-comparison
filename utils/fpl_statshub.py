from utils.loaders.bootstrap_static_loader import ElementsLoader
from utils.loaders.bootstrap_static_loader import TeamsLoader

from utils.loaders.elements_summary_loader import FixturesLoader
from utils.loaders.elements_summary_loader import HistoryLoader
from utils.loaders.elements_summary_loader import HistoryPastLoader

from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor
from utils.preprocessors.elements_summary_preprocessors import HistoryPreprocessor
from utils.preprocessors.elements_summary_preprocessors import HistoryPastPreprocessor

class FplStatsHub:
    def __init__(self, base_url):
        self.base_url = base_url
        self.teams_loader = TeamsLoader(self.base_url)
        self.elements_loader = ElementsLoader(self.base_url)
        self.fixtures_loader = FixturesLoader(self.base_url)
        self.history_loader = HistoryLoader(self.base_url)
        self.history_past_loader = HistoryPastLoader(self.base_url)

    def load_and_preprocess_data(self):
        elements_data = self.elements_loader.get_elements_data()
        teams_data = self.teams_loader.get_teams_data()
        fixtures_data = self.fixtures_loader.get_fixtures_data()
        history_data = self.history_loader.get_history_data()
        history_past_data = self.history_past_loader.get_history_past_data()

        column_names_elements = ['team']
        column_names_fixtures = ['team_h', 'team_a']
        column_names_history = ['opponent_team']

        elements_preprocessor = ElementsPreprocessor(elements_data, teams_data)
        fixtures_preprocessor = FixturesPreprocessor(fixtures_data, teams_data)
        history_preprocessor = HistoryPreprocessor(history_data, teams_data)
        history_past_preprocessor = HistoryPastPreprocessor(history_past_data)

        self.elements_data = elements_preprocessor.preprocess_elements(column_names_elements)
        self.fixtures_data = fixtures_preprocessor.preprocess_fixtures(column_names_fixtures)
        self.history_data = history_preprocessor.preprocess_history(column_names_history)
        self.history_past_data = history_past_data

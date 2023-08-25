from utils.loaders.base_loader import BaseLoader
import pandas as pd

class BootstrapStaticLoader(BaseLoader):
    def __init__(self, base_url):
        super().__init__(base_url)
        self.endpoint = "bootstrap-static/"
        self.data = self.load_data(self.endpoint)

class ElementsLoader(BootstrapStaticLoader):
    def __init__(self, base_url):
        super().__init__(base_url)

    def get_elements_data(self):
        if self.data is not None and 'elements' in self.data:
            elements_data = pd.DataFrame(self.data['elements'])
            return elements_data
        else:
            return None

class TeamsLoader(BootstrapStaticLoader):
    def __init__(self, base_url):
        super().__init__(base_url)

    def get_teams_data(self):
        teams_data = pd.DataFrame(self.data['teams'])
        return teams_data

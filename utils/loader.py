
import requests

class DataLoader:
    def __init__(self, url):
        self.url = url

    def load_data(self):
        r = requests.get(self.url)
        data = r.json()
        return data
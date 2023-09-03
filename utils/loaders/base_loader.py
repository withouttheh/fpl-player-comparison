import requests

class BaseLoader:
    def __init__(self, base_url):
        self.base_url = base_url
     
    def load_data(self, endpoint):
        """Load data from the specified endpoint."""

        full_url = f"{self.base_url}/{endpoint}"
        
        try:
            r = requests.get(full_url)
            r.raise_for_status()  # Raise an exception for HTTP error responses
            data = r.json()
            return data
        except requests.exceptions.RequestException as e:
            print("Error fetching data:", e)
            return None
"""
utils/loaders/bootstrap_static_loader.py — Loaders for /bootstrap-static/.

bootstrap-static is the FPL API's "master record" for the current season:
every player, every team, element types, gameweek metadata. It is fetched
once per request (not once per server lifetime) and the result is cached
by the handler layer for 1 hour.

Why fetch in __init__ instead of lazily?
    The subclasses (ElementsLoader, TeamsLoader) each need different slices
    of the same API response. Fetching once in the parent __init__ means
    both slices share a single HTTP round trip — even if a handler
    instantiates both loaders separately, the result is the same JSON.
    In practice, handlers instantiate one or both and the cache ensures
    only one real API call happens per TTL window.

Cache TTL (controlled by the handler, not here): 1 hour.
    bootstrap-static changes only during transfer deadline windows and when
    the FPL team processes score/bonus updates — at most a few times per day.
"""

import pandas as pd

from utils.loaders.base_loader import BaseLoader


class BootstrapStaticLoader(BaseLoader):
    """Fetches /bootstrap-static/ once and stores the raw JSON for subclass use."""

    def __init__(self, base_url):
        super().__init__(base_url)
        self.endpoint = "bootstrap-static/"
        self.data = self.load_data(self.endpoint)


class ElementsLoader(BootstrapStaticLoader):
    """Extracts the 'elements' array (all players) from bootstrap-static."""

    def __init__(self, base_url):
        super().__init__(base_url)

    def get_elements_data(self):
        """Return a DataFrame of all players, or None if the fetch failed."""
        if self.data is not None and 'elements' in self.data:
            return pd.DataFrame(self.data['elements'])
        return None


class TeamsLoader(BootstrapStaticLoader):
    """Extracts the 'teams' array from bootstrap-static."""

    def __init__(self, base_url):
        super().__init__(base_url)

    def get_teams_data(self):
        """Return a DataFrame of all Premier League teams."""
        return pd.DataFrame(self.data['teams'])

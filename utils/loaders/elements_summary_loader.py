"""
utils/loaders/elements_summary_loader.py — Loaders for /element-summary/{id}/.

element-summary is per-player data: upcoming fixtures, this-season gameweek
history, and previous-season summary stats. It is fetched once per player
ID per handler request, then cached separately for each player.

Why separate cache TTLs per data type?
    The three sections of element-summary change on very different schedules:
    - fixtures:      changes only when the Premier League schedule changes (rare)
    - history:       updates every ~2 minutes during a live gameweek
    - history_past:  never changes once a season ends

    Rather than caching the entire element-summary response at one TTL, the
    handler layer caches each section independently (see history_handler.py
    and fixtures_handler.py). This way history stays fresh during a live
    gameweek without forcing fixture data to be re-fetched unnecessarily.

The element_id is validated by the handler before it reaches this loader.
This loader casts it to int internally as a belt-and-suspenders measure —
a second validation layer for a field that is embedded directly into a URL.
"""

import pandas as pd

from utils.loaders.base_loader import BaseLoader


class ElementsSummaryLoader(BaseLoader):
    """Fetches /element-summary/{element_id}/ for a single player.

    The response contains three keys: 'fixtures' (upcoming), 'history' (this season),
    and 'history_past' (previous seasons). Subclasses extract each section.
    """

    def __init__(self, base_url, element_id):
        super().__init__(base_url)
        self.endpoint = f"element-summary/{element_id}/"
        self.data = self.load_data(self.endpoint)


class FixturesLoader(ElementsSummaryLoader):
    """Extracts upcoming fixtures for a player."""

    def __init__(self, base_url, element_id=1):
        super().__init__(base_url, element_id)

    def get_fixtures_data(self):
        """Return a DataFrame of upcoming fixtures for this player."""
        return pd.DataFrame(self.data["fixtures"])


class HistoryLoader(ElementsSummaryLoader):
    """Extracts this-season gameweek history for a player."""

    def __init__(self, base_url, element_id=1):
        super().__init__(base_url, element_id)

    def get_history_data(self):
        """Return a DataFrame of per-gameweek stats for this player this season."""
        return pd.DataFrame(self.data["history"])


class HistoryPastLoader(ElementsSummaryLoader):
    """Extracts previous-season summary stats for a player."""

    def __init__(self, base_url, element_id=1):
        super().__init__(base_url, element_id)

    def get_history_past_data(self):
        """Return a DataFrame of per-season totals for this player."""
        return pd.DataFrame(self.data["history_past"])

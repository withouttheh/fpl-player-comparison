"""
handlers/players_handler.py — GET /api/players

Returns a JSON array of all current-season FPL players with the fields
the frontend needs to populate the player dropdowns and display player cards.

Data source:
    FPL API /bootstrap-static/ → elements array.
    Fetched via utils.loaders, preprocessed via utils.preprocessors.
    Cached for 1 hour (bootstrap-static changes rarely during the day).

Fields returned per player:
    id, full_name, team, position, now_cost, total_points,
    selected_by_percent, form

Why only these fields?
    The frontend only needs these fields for the dropdown list and the
    player info card. Sending the full elements payload (~80 columns per
    player × 700 players) would be ~500KB of JSON on every page load.
    Selecting a subset keeps the response small and fast.

now_cost is divided by 10 here (not in the frontend) because:
    FPL stores prices as integers (e.g. 125 = £12.5m). Dividing server-side
    means the frontend receives the correct decimal value and does not need
    to know about FPL's internal representation.
"""

import sys

from cache import cache
from handlers.base_handler import send_error, send_json
from utils.config import base_url
from utils.loaders.bootstrap_static_loader import ElementsLoader, TeamsLoader
from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor

# Cache key for the processed players list.
_CACHE_KEY = "players"

# How long to cache the player list (seconds).
# bootstrap-static is updated by FPL at most a few times per day.
_CACHE_TTL = 3600  # 1 hour

# Only these columns are sent to the frontend.
_OUTPUT_FIELDS = [
    "id",
    "full_name",
    "team",
    "position",
    "now_cost",
    "total_points",
    "selected_by_percent",
    "form",
]


def serve_players(request, **kwargs) -> None:
    """Handle GET /api/players.

    Returns a JSON array of player objects. Checks the cache first;
    fetches from the FPL API on a cache miss.
    """
    try:
        players = _get_players()
    except Exception as exc:
        print(f"[ERROR] serve_players: {exc}", file=sys.stderr)
        send_error(request, 502, "Failed to retrieve player data")
        return

    send_json(request, players)


def _get_players() -> list[dict]:
    """Return the players list, using the cache if available.

    Raises:
        ValueError: if the FPL API response is missing expected keys.
        Any requests exception if the network call fails.
    """
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    players = _fetch_and_process()
    cache.set(_CACHE_KEY, players, ttl=_CACHE_TTL)
    return players


def _fetch_and_process() -> list[dict]:
    """Fetch from the FPL API and return a list of player dicts.

    Raises on any network error or missing response keys — callers are
    responsible for converting exceptions to HTTP error responses.
    """
    teams_loader = TeamsLoader(base_url)
    teams_data = teams_loader.get_teams_data()

    elements_loader = ElementsLoader(base_url)
    elements_data = elements_loader.get_elements_data()

    if elements_data is None:
        raise ValueError("FPL API returned no elements data")

    preprocessor = ElementsPreprocessor(elements_data, teams_data)
    df = preprocessor.preprocess_elements(["team"])

    # Divide now_cost by 10 to convert FPL internal format to £m.
    df["now_cost"] = df["now_cost"] / 10

    # Select only the columns the frontend needs.
    available = [col for col in _OUTPUT_FIELDS if col in df.columns]
    df = df[available]

    return df.to_dict(orient="records")

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
from urllib.parse import parse_qs, urlparse

from cache import cache
from handlers.base_handler import send_error, send_json
from utils.config import ARCHIVE_SEASONS, S3_BUCKET, base_url
from utils.loaders.bootstrap_static_loader import ElementsLoader, TeamsLoader
from utils.loaders.s3_loader import S3BootstrapLoader
from utils.preprocessors.bootstrap_static_preprocessors import ElementsPreprocessor

# Cache key for the live processed players list.
_CACHE_KEY = "players"

# How long to cache the player list (seconds).
# bootstrap-static is updated by FPL at most a few times per day.
_CACHE_TTL = 3600  # 1 hour

# Archive data never changes — cache for 24 hours.
_ARCHIVE_CACHE_TTL = 86400

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

    Accepts an optional ?season=YYYY-YY query parameter. When a valid
    archive season is supplied, data is read from S3 instead of the live
    FPL API. Falls back to live data when the parameter is absent or invalid.
    """
    qs = parse_qs(urlparse(request.path).query)
    season = qs.get("season", [None])[0]
    if season not in ARCHIVE_SEASONS:
        season = None

    try:
        players = _get_archive_players(season) if season else _get_players()
    except Exception as exc:
        print(f"[ERROR] serve_players season={season}: {exc}", file=sys.stderr)
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


def _get_archive_players(season: str) -> list[dict]:
    """Return archived players list for a past season, using cache if available."""
    cache_key = f"players:{season}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    players = _fetch_and_process_archive(season)
    cache.set(cache_key, players, ttl=_ARCHIVE_CACHE_TTL)
    return players


def _fetch_and_process() -> list[dict]:
    """Fetch from the live FPL API and return a list of player dicts.

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


def _fetch_and_process_archive(season: str) -> list[dict]:
    """Read from S3 archive and return a list of player dicts for a past season."""
    loader = S3BootstrapLoader(S3_BUCKET, season)
    teams_data = loader.get_teams_data()
    elements_data = loader.get_elements_data()

    if elements_data is None:
        raise ValueError(f"S3 returned no elements data for season {season}")

    preprocessor = ElementsPreprocessor(elements_data, teams_data)
    df = preprocessor.preprocess_elements(["team"])
    df["now_cost"] = df["now_cost"] / 10

    available = [col for col in _OUTPUT_FIELDS if col in df.columns]
    return df[available].to_dict(orient="records")

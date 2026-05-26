"""
handlers/history_handler.py — GET /api/player/<player_id>/history

Returns a JSON array of per-gameweek stats for one player this season.
Used by the frontend to render the bar chart and line chart.

Security:
    player_id arrives as a string of digits (the router's digit-only pattern
    guarantees no letters, no minus sign, no decimal point). We still
    validate the range here because:
      - The router only guarantees the format, not the domain validity.
      - A player_id of 0 or 99999 are syntactically valid but semantically
        nonsense. We reject them with 400 before making an outbound request.
      - Defence in depth: two layers of validation are better than one.

Player ID range:
    FPL assigns IDs sequentially. As of the 2024/25 season there are ~750
    players in the game. We allow up to 2000 to give headroom for future
    seasons without needing to update this constant every year.

Cache TTL:
    5 minutes. Per-gameweek history updates during live gameweeks (roughly
    every 2 minutes during a match). 5 minutes balances freshness against
    API load. Outside of live gameweeks, the data is static between GWs.
"""

import sys
from urllib.parse import parse_qs, urlparse

from cache import cache
from handlers.base_handler import send_error, send_json
from utils.config import ARCHIVE_SEASONS, S3_BUCKET, base_url
from utils.loaders.bootstrap_static_loader import TeamsLoader
from utils.loaders.elements_summary_loader import HistoryLoader
from utils.loaders.s3_loader import S3BootstrapLoader, S3ElementSummaryLoader
from utils.preprocessors.elements_summary_preprocessors import HistoryPreprocessor

_CACHE_TTL = 300  # 5 minutes — live data updates during gameweeks
_ARCHIVE_CACHE_TTL = 86400  # 24 hours — archive never changes
_MAX_PLAYER_ID = 2000  # upper bound for valid FPL player IDs

# Fields sent to the frontend. The full history row has ~40 columns;
# we send only what the charts and tables need.
_OUTPUT_FIELDS = [
    "round",
    "opponent_team",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "saves",
    "bonus",
    "bps",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
    "transfers_balance",
    "selected",
    "transfers_in",
    "transfers_out",
]


def serve_history(request, player_id: str, **kwargs) -> None:
    """Handle GET /api/player/<player_id>/history.

    Parameters
    ----------
    request:
        Active BaseHTTPRequestHandler instance.
    player_id:
        String of digits from the URL path. Validated and converted to int here.
    """
    # --- Validate player_id range ----------------------------------------
    # The router guarantees player_id is a string of digits. Convert to int
    # and check the domain range. We return 400 (Bad Request) rather than
    # 404 because the path format is valid — the ID value is the problem.
    try:
        pid = int(player_id)
    except ValueError:
        # Should never happen given the router's \d+ pattern, but be explicit.
        send_error(request, 400, "Invalid player ID")
        return

    if pid <= 0 or pid > _MAX_PLAYER_ID:
        send_error(request, 400, f"Player ID must be between 1 and {_MAX_PLAYER_ID}")
        return

    qs = parse_qs(urlparse(request.path).query)
    season = qs.get("season", [None])[0]
    if season not in ARCHIVE_SEASONS:
        season = None

    try:
        history = _get_archive_history(pid, season) if season else _get_history(pid)
    except Exception as exc:
        print(f"[ERROR] serve_history pid={pid} season={season}: {exc}", file=sys.stderr)
        send_error(request, 502, "Failed to retrieve player history")
        return

    send_json(request, history)


def _get_history(player_id: int) -> list[dict]:
    """Return live history for player_id, using the cache if available."""
    cache_key = f"history:{player_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    history = _fetch_and_process(player_id)
    cache.set(cache_key, history, ttl=_CACHE_TTL)
    return history


def _get_archive_history(player_id: int, season: str) -> list[dict]:
    """Return archived history for player_id from S3, using the cache if available."""
    cache_key = f"history:{season}:{player_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    history = _fetch_and_process_archive(player_id, season)
    cache.set(cache_key, history, ttl=_ARCHIVE_CACHE_TTL)
    return history


def _fetch_and_process(player_id: int) -> list[dict]:
    """Fetch and preprocess live history for one player."""
    teams_loader = TeamsLoader(base_url)
    teams_data = teams_loader.get_teams_data()

    loader = HistoryLoader(base_url, player_id)
    df = loader.get_history_data()

    if df is None or df.empty:
        raise ValueError(f"No history data returned for player {player_id}")

    preprocessor = HistoryPreprocessor(df, teams_data)
    df = preprocessor.preprocess_history(["opponent_team"])
    df = _cast_float_cols(df)

    available = [col for col in _OUTPUT_FIELDS if col in df.columns]
    return df[available].to_dict(orient="records")


def _fetch_and_process_archive(player_id: int, season: str) -> list[dict]:
    """Read S3 archive history for one player in a past season."""
    bootstrap = S3BootstrapLoader(S3_BUCKET, season)
    teams_data = bootstrap.get_teams_data()

    loader = S3ElementSummaryLoader(S3_BUCKET, season, player_id)
    df = loader.get_history_data()

    if df is None or df.empty:
        raise ValueError(f"No archive history for player {player_id} season {season}")

    preprocessor = HistoryPreprocessor(df, teams_data)
    df = preprocessor.preprocess_history(["opponent_team"])
    df = _cast_float_cols(df)

    available = [col for col in _OUTPUT_FIELDS if col in df.columns]
    return df[available].to_dict(orient="records")


def _cast_float_cols(df):
    """Cast ICT/xG columns from string to float (FPL API returns them as strings)."""
    float_cols = [
        "influence",
        "creativity",
        "threat",
        "ict_index",
        "expected_goals",
        "expected_assists",
        "expected_goal_involvements",
        "expected_goals_conceded",
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df

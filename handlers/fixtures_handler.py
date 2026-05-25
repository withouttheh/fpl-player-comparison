"""
handlers/fixtures_handler.py — GET /api/player/<player_id>/fixtures

Returns a JSON array of upcoming fixtures for one player. Used by the
frontend to display the fixture difficulty row on each player card.

Security: identical player_id validation as history_handler.py.
See that module for the rationale.

Cache TTL:
    1 hour. The fixture schedule changes only when the Premier League
    reschedules matches (rare, and not during live play). 1 hour is
    conservative enough that users see changes within a reasonable time.

Fields returned:
    event (gameweek number), is_home, difficulty, opponent (short name).
    'difficulty' is FPL's Fixture Difficulty Rating (1–5).
"""

import sys

from cache import cache
from handlers.base_handler import send_json, send_error
from utils.config import base_url
from utils.loaders.bootstrap_static_loader import TeamsLoader
from utils.loaders.elements_summary_loader import FixturesLoader
from utils.preprocessors.elements_summary_preprocessors import FixturesPreprocessor


_CACHE_TTL = 3600       # 1 hour
_MAX_PLAYER_ID = 2000


def serve_fixtures(request, player_id: str, **kwargs) -> None:
    """Handle GET /api/player/<player_id>/fixtures."""
    try:
        pid = int(player_id)
    except ValueError:
        send_error(request, 400, "Invalid player ID")
        return

    if pid <= 0 or pid > _MAX_PLAYER_ID:
        send_error(request, 400, f"Player ID must be between 1 and {_MAX_PLAYER_ID}")
        return

    try:
        fixtures = _get_fixtures(pid)
    except Exception as exc:
        print(f"[ERROR] serve_fixtures pid={pid}: {exc}", file=sys.stderr)
        send_error(request, 502, "Failed to retrieve fixture data")
        return

    send_json(request, fixtures)


def _get_fixtures(player_id: int) -> list[dict]:
    cache_key = f"fixtures:{player_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    fixtures = _fetch_and_process(player_id)
    cache.set(cache_key, fixtures, ttl=_CACHE_TTL)
    return fixtures


def _fetch_and_process(player_id: int) -> list[dict]:
    teams_loader = TeamsLoader(base_url)
    teams_data = teams_loader.get_teams_data()

    loader = FixturesLoader(base_url, player_id)
    df = loader.get_fixtures_data()

    if df is None or df.empty:
        return []

    preprocessor = FixturesPreprocessor(df, teams_data)
    df = preprocessor.preprocess_fixtures(["team_h", "team_a"])

    # Derive a single 'opponent' column so the frontend doesn't need to
    # know which team is home/away — it only needs the opponent name.
    # We cannot do this without knowing which team the player belongs to,
    # so we send both team_h and team_a and let the frontend derive it.
    output_fields = ["event", "is_home", "difficulty", "team_h", "team_a"]
    available = [col for col in output_fields if col in df.columns]
    return df[available].to_dict(orient="records")

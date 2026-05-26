"""
handlers/seasons_handler.py — GET /api/seasons

Returns the list of seasons the frontend can display: the live FPL API
season plus any seasons archived in S3 by scripts/capture.py.

The frontend uses this to populate the season selector dropdown and to
know which ?season= values are valid for the other API endpoints.
"""

from handlers.base_handler import send_json
from utils.config import ARCHIVE_SEASONS


def serve_seasons(request, **kwargs) -> None:
    """Handle GET /api/seasons."""
    seasons = [{"id": "current", "label": "Live"}]
    for s in ARCHIVE_SEASONS:
        year, suffix = s.split("-")
        seasons.append({"id": s, "label": f"{year}/{suffix} Archive"})
    send_json(request, seasons)

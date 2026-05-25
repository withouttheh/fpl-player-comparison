"""
utils/loaders/base_loader.py — HTTP fetch layer for the FPL API.

Every outbound API call in this project goes through BaseLoader.load_data.
Centralising it here means timeout enforcement, error containment, and mock
mode are handled in one place — not scattered across every subclass.

Mock mode (FPL_MOCK=1):
    Set the environment variable FPL_MOCK=1 to run the server without any
    network access. load_data reads from data/ instead of calling the API.
    This is useful for local development and demos when you don't need
    live gameweek data.

    $ FPL_MOCK=1 python server.py

Why timeout=10?
    Without a timeout, a slow or unresponsive FPL API stalls the handling
    thread indefinitely. Since the server is multi-threaded, enough stalled
    threads will exhaust the pool and make the server unresponsive. 10s is
    generous enough for any normal API response but tight enough to fail fast.

Why return None on failure (not raise)?
    Callers (the handlers) need to convert errors to 502 responses. If we
    raised here, every handler would need a try/except just for the fetch.
    Returning None keeps that contract simple: check for None → return 502.
"""

import json
import os
import sys
from pathlib import Path

import requests

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class BaseLoader:
    """Base class for all FPL API loaders. Handles HTTP fetching and JSON parsing."""

    def __init__(self, base_url):
        self.base_url = base_url

    def load_data(self, endpoint):
        """GET {base_url}/{endpoint} and return parsed JSON, or None on failure.

        When FPL_MOCK=1 is set, reads from data/ instead of the network.
        """
        if os.getenv("FPL_MOCK"):
            return self._load_mock(endpoint)

        full_url = f"{self.base_url}/{endpoint}"
        try:
            r = requests.get(full_url, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] FPL API request failed for {endpoint}: {e}", file=sys.stderr)
            return None

    def _load_mock(self, endpoint):
        """Read from data/ instead of the network. Used when FPL_MOCK=1."""
        if "bootstrap-static" in endpoint:
            path = _DATA_DIR / "bootstrap_static.json"
        else:
            # element-summary/{id}/ and any other per-player endpoint
            path = _DATA_DIR / "element_summary.json"

        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            print(
                f"[ERROR] Mock data file not found: {path}\n"
                f"        Run: python server.py  (without FPL_MOCK) to fetch live data,\n"
                f"        or check that data/ contains bootstrap_static.json and element_summary.json.",
                file=sys.stderr,
            )
            return None

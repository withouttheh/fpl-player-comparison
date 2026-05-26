"""
tests/e2e/conftest.py — Pytest fixtures for end-to-end browser tests.

Starts the server with FPL_MOCK=1 before the test session and tears it
down afterwards. All e2e tests use this server automatically via the
`live_server_url` fixture.

Why FPL_MOCK=1?
    E2e tests must be deterministic and not depend on external services.
    Mock mode serves data from data/ so tests always see the same 12 players
    and 30 gameweeks regardless of FPL API availability.

Why a subprocess and not pytest-django/Flask test client?
    The app is a raw Python HTTP server — no framework test client exists.
    A real subprocess exercises the same code path a real user would hit,
    including ThreadedHTTPServer, routing, caching, and static file serving.
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PORT = 18000  # use a non-standard port so tests don't conflict with a dev server


@pytest.fixture(scope="session")
def live_server_url():
    """Start the server in mock mode, yield the base URL, then shut it down."""
    env = {**os.environ, "FPL_MOCK": "1"}
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=PROJECT_ROOT,
        env={**env, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for the server to be ready (up to 5s).
    url = f"http://127.0.0.1:{PORT}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{url}/", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("Server did not start within 5 seconds")

    yield url

    proc.terminate()
    proc.wait(timeout=5)

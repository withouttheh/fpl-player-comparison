"""
router.py — Maps incoming HTTP requests to handler functions.

Responsibilities:
    - Parse the raw request path (strip query string, normalise slashes)
    - Guard against malformed inputs before any handler sees them
    - Match the path against ROUTES and enforce the declared HTTP method
    - Call the handler with extracted path parameters

What the router does NOT do:
    - Validate business-logic inputs (e.g. valid player ID range) — handlers own that
    - Write response bodies beyond routing errors (404, 405, 400, 414)

Design notes:
    Routes store (module, "func_name") resolved via getattr() at dispatch time, not
    a direct function reference. This lets tests patch handler attributes and have
    the patch picked up at call time — a direct reference would bypass the patch.
"""

import re
import sys
from typing import NamedTuple
from urllib.parse import urlparse

import handlers.fixtures_handler as _fixtures
import handlers.history_handler as _history
import handlers.players_handler as _players
import handlers.static_handler as _static
from handlers.base_handler import send_error

_MAX_PATH_LENGTH = 512  # anything longer is a scanner probe, not a real request

GET = frozenset({"GET"})


class Route(NamedTuple):
    pattern: re.Pattern
    methods: frozenset
    module: object
    func: str


ROUTES: list[Route] = [
    Route(re.compile(r"^/api/players$"), GET, _players, "serve_players"),
    Route(re.compile(r"^/api/player/(?P<player_id>\d+)/history$"), GET, _history, "serve_history"),
    Route(
        re.compile(r"^/api/player/(?P<player_id>\d+)/fixtures$"), GET, _fixtures, "serve_fixtures"
    ),
    Route(re.compile(r"^/static/"), GET, _static, "serve_static"),
    Route(re.compile(r"^/$"), GET, _static, "serve_static"),
]


class Router:
    """Parses requests and dispatches them to handler functions.

    Instantiated once in server.py and shared across all request threads.
    All state is read-only after __init__, so no locking is needed.
    """

    def dispatch(self, request) -> None:
        """Entry point called by RequestHandler for every incoming request."""
        try:
            self._dispatch(request)
        except Exception as exc:
            print(f"[ROUTER UNHANDLED] {type(exc).__name__}: {exc}", file=sys.stderr)
            try:
                send_error(request, 500, "Internal server error")
            except Exception:
                pass  # nosec B110 — last resort; connection may already be dead

    def _dispatch(self, request) -> None:
        raw_path: str = request.path
        method: str = request.command.upper()

        if len(raw_path) > _MAX_PATH_LENGTH:
            send_error(request, 414, "URI too long")
            return

        path: str = urlparse(raw_path).path

        if "\x00" in path:
            send_error(request, 400, "Bad request")
            return

        # Collapse consecutive slashes — do NOT use os.path.normpath here as
        # that resolves '..' which belongs to the static handler, not the router.
        while "//" in path:
            path = path.replace("//", "/")

        for route in ROUTES:
            match = route.pattern.match(path)
            if match is None:
                continue

            if method not in route.methods:
                request.send_response(405)
                request.send_header("Allow", ", ".join(sorted(route.methods)))
                request.send_header("Content-Length", "0")
                request.end_headers()
                return

            getattr(route.module, route.func)(request, **match.groupdict())
            return

        send_error(request, 404, "Not found")

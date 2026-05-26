"""
server.py — Entry point. Creates the HTTP server and starts it.

This file does exactly three things:
  1. Defines a threaded server class
  2. Defines a thin request handler that delegates to the router
  3. Starts the server and keeps it alive until Ctrl-C

Nothing else belongs here. Business logic, routing, and response writing
live in router.py and handlers/. Keeping this file small means the entry
point is easy to read and reason about.
"""

import os
import socketserver
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from router import Router

# ---------------------------------------------------------------------------
# Threaded server
# ---------------------------------------------------------------------------


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in its own thread.

    Python's built-in HTTPServer processes one request at a time. If a request
    is waiting on a slow FPL API call, every other incoming request queues
    behind it. ThreadingMixIn fixes this by spawning a thread per request.

    Why ThreadingMixIn and not ForkingMixIn?
        ForkingMixIn creates a new OS process per request. Each process gets
        its own copy of memory, so the in-memory cache we define in cache.py
        is not shared — an update in one child is invisible to all others.
        ThreadingMixIn uses threads within a single process, so all threads
        share the same cache object. The GIL is not a concern here because
        our threads spend most of their time blocked on I/O (waiting for the
        FPL API to respond), not executing Python bytecode.

    Why daemon_threads = True?
        Non-daemon threads prevent the Python process from exiting until they
        finish. If a request thread is mid-way through a 10-second FPL API
        call when the user presses Ctrl-C, the server would hang for up to
        10 seconds waiting for that thread. Daemon threads are killed
        immediately when the main thread exits. Acceptable here because we
        have no cleanup to do per-request (no database transactions, no files
        to flush).

    Why allow_reuse_address = True?
        When a server shuts down, the OS keeps its port in TIME_WAIT state
        for ~60 seconds to absorb any packets still in transit from old
        connections. Without this flag, restarting the server within that
        window raises "OSError: [Errno 48] Address already in use". During
        development, where restarts happen constantly, this would be
        maddening. The flag tells the OS to allow binding to a port still in
        TIME_WAIT. Do not disable this without understanding the implications
        in a high-traffic production environment.
    """

    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

# Instantiate the router once, at import time, not per-request.
# Router.__init__ compiles all regex patterns. Doing this once and reusing
# the compiled patterns across all requests is significantly faster than
# recompiling on every request.
_router = Router()


class RequestHandler(BaseHTTPRequestHandler):
    """Minimal shim between Python's HTTP machinery and the router.

    Python's http.server dispatches requests by calling do_GET, do_POST, etc.
    Rather than putting any logic here, we delegate immediately to the router.
    This class is intentionally thin — if you find yourself adding business
    logic here, it belongs in a handler module instead.
    """

    def do_GET(self):
        _router.dispatch(self)

    def log_message(self, format, *args):
        """Write access logs to stderr in a readable format.

        Why override this?
            The default implementation writes to stderr in Apache Common Log
            Format, which includes the client address, date, request line, and
            status code. It's correct but verbose. We override to control the
            format — in a real deployment this would write structured JSON to
            a log aggregator rather than plain text to stderr.

        Why stderr and not stdout?
            stdout is for program output (data). stderr is for diagnostics
            (logs, errors). Keeping them separate means a process supervisor
            or log shipper can capture each stream independently.
        """
        print(f"  {self.log_date_time_string()}  {format % args}", file=sys.stderr)

    def log_error(self, format, *args):
        """Route HTTP-level errors (malformed requests etc.) to stderr."""
        print(f"  [ERROR]  {format % args}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = int(os.getenv("PORT", "8000"))


if __name__ == "__main__":
    """
    Why 127.0.0.1 and not 0.0.0.0?

        0.0.0.0 means "all interfaces" — the server would accept connections
        from any network the machine is on, including the public internet if
        the machine has a public IP address. During development, this would
        expose a server with no TLS, no rate limiting, and no authentication
        to the world.

        127.0.0.1 (loopback) only accepts connections originating on the same
        machine. A connection from another device cannot reach it at all.

        In production the correct pattern is:
          - A reverse proxy (Nginx, Caddy) binds to 0.0.0.0:443 and handles
            TLS termination, rate limiting, and logging.
          - The Python server binds to 127.0.0.1:8000 and only receives
            forwarded requests from the proxy.
          - The Python server never faces the public internet directly.
    """
    server = ThreadedHTTPServer((HOST, PORT), RequestHandler)
    mock = os.getenv("FPL_MOCK")
    mode = " [MOCK DATA — no FPL API calls]" if mock else ""
    print(f"Serving on http://{HOST}:{PORT}{mode}  (Ctrl-C to stop)", file=sys.stderr)

    try:
        # serve_forever() blocks, calling select() in a loop and dispatching
        # incoming connections to RequestHandler in new threads.
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl-C raises KeyboardInterrupt in the main thread.
        # serve_forever() does not catch it, so it propagates here.
        print("\nShutting down.", file=sys.stderr)
    finally:
        # server_close() releases the socket so the port can be reused
        # immediately (alongside allow_reuse_address). Always call this,
        # even if serve_forever() raised something other than KeyboardInterrupt.
        server.server_close()

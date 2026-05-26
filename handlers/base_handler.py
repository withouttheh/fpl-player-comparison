"""
handlers/base_handler.py — Shared HTTP response helpers.

Every handler in this project calls these functions to write responses.
Centralising response-writing here means:

  1. Security headers are applied to every response automatically.
     No individual handler can forget them.

  2. The Content-Type and Content-Length headers are always set correctly.
     Forgetting Content-Length causes HTTP/1.1 persistent connections to
     stall; forgetting Content-Type causes browsers to guess (sniff) the
     type, which is a security risk.

  3. The serialisation logic (JSON encoding, UTF-8) is in one place.
     If we need to change the encoding or add compression, there is one
     place to do it.

Why functions and not a class?
    Handler functions in this project receive the BaseHTTPRequestHandler
    instance as their first argument (called `request` by convention). A
    class wrapping `request` would add a layer of indirection without
    benefit. Functions with explicit parameters are easier to follow, easier
    to test (pass a mock), and make all dependencies visible in the signature.
"""

import json

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


def _send_security_headers(request) -> None:
    """Write security response headers that apply to every response.

    Called by every send_* function so that no handler can accidentally omit
    these. They are written before end_headers() is called.

    Headers applied:

    X-Content-Type-Options: nosniff
        Without this, a browser may try to guess the content type when the
        declared Content-Type seems wrong (MIME sniffing). An attacker who
        can upload content (not applicable here, but as a standing rule)
        could craft a response that the browser treats as a different type —
        for example, executing a text file as JavaScript.

    X-Frame-Options: DENY
        Prevents this page from being embedded in an <iframe> on any other
        site. Mitigates clickjacking: an attacker could overlay a transparent
        iframe of our app over their own page, tricking a user into clicking
        on our controls while thinking they are clicking on the attacker's UI.

    Content-Security-Policy (CSP):
        A fine-grained allowlist of where the browser may load resources from.
        Any resource not on the list is blocked, even if injected by an
        attacker.

        default-src 'self'
            Block all resources not explicitly listed below.

        script-src 'self' <cdn origins>
            JavaScript may only be loaded from this server or the two CDNs
            we use (D3.js from jsdelivr, Tailwind from tailwindcss.com).
            Inline scripts are blocked. This means even if an attacker
            injects <script>alert(1)</script> into the DOM, it won't run.

        style-src 'self' <cdn> 'unsafe-inline'
            Tailwind's play CDN uses inline style injection, so 'unsafe-inline'
            is required for styles. This is a known Tailwind CDN limitation.
            When we move to a compiled Tailwind build, 'unsafe-inline' can
            be removed.

        img-src 'self' data:
            Images may only come from this server or data: URIs (used by D3
            for embedded SVG content).

        connect-src 'self'
            fetch() calls may only go to this server. The browser cannot
            make AJAX requests to external origins from our scripts.

        frame-ancestors 'none'
            Redundant with X-Frame-Options but CSP is the modern standard.
            'none' means this page cannot be framed anywhere.

    Referrer-Policy: no-referrer
        The browser will not include the Referer header in any request
        originating from our page (navigation, resource loads, fetch() calls).
        This prevents the current page URL from being sent to third-party
        servers (e.g. the CDN would not receive the URL the user is viewing).
    """
    request.send_header("X-Content-Type-Options", "nosniff")
    request.send_header("X-Frame-Options", "DENY")
    request.send_header(
        "Content-Security-Policy",
        (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        ),
    )
    request.send_header("Referrer-Policy", "no-referrer")


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def send_json(request, data: object, status: int = 200) -> None:
    """Serialise data to JSON and write a complete HTTP response.

    Parameters
    ----------
    request:
        The active BaseHTTPRequestHandler instance.
    data:
        Any JSON-serialisable Python object (dict, list, str, int, etc.).
    status:
        HTTP status code. Defaults to 200.

    Design decisions:

    ensure_ascii=False
        By default, json.dumps() escapes non-ASCII characters (e.g. é → \\u00e9).
        Player names contain accented characters. ensure_ascii=False keeps them
        readable in the response body. The browser decodes UTF-8 correctly.

    Content-Length
        We encode the body to bytes before writing headers so we know the
        exact byte length. Setting Content-Length allows HTTP/1.1 persistent
        connections to work correctly — the client knows when the response
        body ends without needing the server to close the connection.

    Cache-Control: no-store
        API responses reflect live FPL data. We instruct the browser not to
        cache them at all — not in memory, not on disk. If the user changes
        the selected player, they must get fresh data, not a cached copy from
        a previous selection.
    """
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    request.send_response(status)
    request.send_header("Content-Type", "application/json; charset=utf-8")
    request.send_header("Content-Length", str(len(body)))
    request.send_header("Cache-Control", "no-store")
    _send_security_headers(request)
    request.end_headers()
    request.wfile.write(body)


def send_html(request, content: str, status: int = 200) -> None:
    """Write an HTML response.

    Used for serving index.html. Unlike static_handler (which reads from disk
    per request), this accepts pre-loaded content as a string. The index is
    small and read once at startup, so loading it into memory is fine.
    """
    body = content.encode("utf-8")

    request.send_response(status)
    request.send_header("Content-Type", "text/html; charset=utf-8")
    request.send_header("Content-Length", str(len(body)))
    _send_security_headers(request)
    request.end_headers()
    request.wfile.write(body)


def send_file(request, body: bytes, content_type: str, status: int = 200) -> None:
    """Write a raw bytes response with the given content type.

    Used by static_handler to serve files (JS, CSS, images) after reading
    them from disk. The caller is responsible for providing the correct
    content_type — it must be derived from the file extension using
    mimetypes.guess_type(), never from user-supplied input.

    Cache-Control for static assets:
        Static files (JS, CSS) change only when we redeploy. We tell the
        browser it can cache them for 1 hour (max-age=3600). This reduces
        page load time for returning visitors. In a production setup with
        cache-busted filenames (app.js?v=abc123), max-age could be much
        longer (a year). For now, 1 hour is a conservative safe default.
    """
    request.send_response(status)
    request.send_header("Content-Type", content_type)
    request.send_header("Content-Length", str(len(body)))
    request.send_header("Cache-Control", "max-age=3600")
    _send_security_headers(request)
    request.end_headers()
    request.wfile.write(body)


def send_error(request, status: int, message: str) -> None:
    """Write a plain-text error response.

    Why plain text?
        Error responses need to work without a functioning frontend. Plain
        text is the simplest format — it cannot be interpreted as HTML and
        cannot trigger script execution. A JSON error body would also be
        acceptable; plain text is used here for simplicity.

    Why not include the real exception message?
        Exception strings in Python routinely contain file paths, variable
        names, class names, and values — all information that helps an
        attacker build a mental model of the server's internals. We log the
        real exception to stderr (where the operator can see it) and send
        only a generic message to the client.

    Why no Cache-Control: no-store?
        Error responses should not be cached by the browser. A 404 that gets
        cached means future legitimate requests to the same URL appear broken
        even after the problem is fixed. no-store ensures the browser always
        re-requests.
    """
    body = message.encode("utf-8")

    request.send_response(status)
    request.send_header("Content-Type", "text/plain; charset=utf-8")
    request.send_header("Content-Length", str(len(body)))
    request.send_header("Cache-Control", "no-store")
    _send_security_headers(request)
    request.end_headers()
    request.wfile.write(body)

"""
handlers/static_handler.py — Serves files from the static/ directory.

This is the highest-risk handler in the application because it reads from
the filesystem based on a user-supplied path. The primary threat is path
traversal: a request for /static/../../server.py must never serve files
outside the static/ root.

Security model:
  1. Resolve the requested path to an absolute path using Path.resolve().
     resolve() expands all symlinks and '..' segments to a canonical path.
  2. Assert the resolved path is a descendant of STATIC_ROOT.resolve().
     is_relative_to() provides this check without string manipulation.
  3. Assert the resolved path is a regular file (not a directory, symlink, etc.).
  4. Only then open and read the file.

Why resolve() and not string manipulation?
    Strings like '/static/../server.py' look like path traversal when read
    literally but could pass naive string checks. resolve() asks the OS for
    the canonical real path, collapsing all '..' segments and symlinks.
    There is no way to escape STATIC_ROOT after resolve() is applied.

Why is_relative_to() and not startswith()?
    Path('/static-other/file').is_relative_to(Path('/static')) returns False.
    '/static-other/file'.startswith('/static') returns True — wrong.
    String prefix checks on paths are fundamentally unsafe.
"""

import mimetypes
import sys
from pathlib import Path

from handlers.base_handler import send_file, send_error


# Absolute path to the static directory.
# Resolved once at import time — all per-request paths are checked
# against this canonical root.
STATIC_ROOT: Path = (Path(__file__).parent.parent / "static").resolve()

# Default file served for the root path ('/').
INDEX_FILE: Path = STATIC_ROOT / "index.html"


def serve_static(request, **kwargs) -> None:
    """Serve a file from the static/ directory.

    Called by the router for:
      - GET /static/<anything>
      - GET /              (serves index.html)

    Parameters
    ----------
    request:
        Active BaseHTTPRequestHandler instance.
    **kwargs:
        Not used. Present for uniform handler signature compatibility.
    """
    from urllib.parse import urlparse, unquote

    raw_path: str = urlparse(request.path).path

    # --- Guard: null bytes -----------------------------------------------
    # The router rejects null bytes before dispatch, but the static handler
    # must also be safe if called directly (e.g. in tests or future refactors).
    # Path.resolve() raises ValueError on null bytes — we catch it explicitly
    # so the response is a clean 400, not an unhandled 500.
    if "\x00" in raw_path:
        send_error(request, 400, "Bad request")
        return

    # --- Resolve the file path ------------------------------------------

    if raw_path == "/" or raw_path == "":
        file_path = INDEX_FILE
    else:
        # Strip the leading /static/ prefix to get the relative component.
        # unquote() decodes percent-encoded characters (e.g. %20 → space).
        # We decode AFTER stripping the prefix so that an encoded slash
        # (%2F) in the filename portion is decoded to a literal slash —
        # which resolve() then collapses, making it impossible to escape
        # the static root via encoding tricks.
        relative = unquote(raw_path.lstrip("/").removeprefix("static/"))
        file_path = (STATIC_ROOT / relative).resolve()

    # --- Path traversal check -------------------------------------------
    # is_relative_to() returns True only if file_path is inside STATIC_ROOT.
    # An attacker-supplied path like /static/../../server.py resolves to
    # something outside STATIC_ROOT and is rejected here.
    if not file_path.is_relative_to(STATIC_ROOT):
        print(
            f"[SECURITY] Path traversal attempt blocked: {request.path!r}",
            file=sys.stderr,
        )
        send_error(request, 403, "Forbidden")
        return

    # --- File existence and type check ----------------------------------
    # Reject directories (no directory listing) and non-existent paths.
    if not file_path.exists() or not file_path.is_file():
        send_error(request, 404, "Not found")
        return

    # --- Read and serve -------------------------------------------------
    try:
        body = file_path.read_bytes()
    except OSError as exc:
        print(f"[ERROR] Could not read static file {file_path}: {exc}", file=sys.stderr)
        send_error(request, 500, "Internal server error")
        return

    # Derive the MIME type from the file extension.
    # guess_type() returns (type, encoding) — we only use type.
    # If the extension is unknown, fall back to application/octet-stream,
    # which tells the browser to treat the response as a download rather
    # than attempting to execute or render it. This is the safest default.
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type is None:
        content_type = "application/octet-stream"

    send_file(request, body, content_type)

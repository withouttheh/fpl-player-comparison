# handlers/

## Purpose
One Python module per route group. Each handler receives a validated, already-parsed
request object from the router and is responsible for exactly one thing: producing
a correct HTTP response.

Handlers have no knowledge of routing logic. The router guarantees that by the time
a handler is called, the path and method are valid and any path parameters have been
extracted and type-checked.

## Files

### `base_handler.py`
Parent class for all handlers. Provides shared response-writing helpers:
- `send_json(data, status=200)` — serialises to JSON, sets Content-Type, writes body
- `send_error(status, message)` — sends a plain-text error; NEVER includes a stack trace
- `send_html(content, status=200)` — sends HTML with correct Content-Type

Nothing in this file ever reads from the request body or touches the filesystem.

### `static_handler.py`
Serves files from the `static/` directory.

**This is the highest-risk handler in the application.**

Security responsibilities:
- **Path traversal prevention**: resolve the requested path with `Path.resolve()` and
  assert it is relative to the `static/` root before calling `open()`. A request for
  `/static/../../server.py` must return 403, not the file.
- **MIME type enforcement**: derive Content-Type from file extension using
  `mimetypes.guess_type()`. Never let the browser sniff types (`X-Content-Type-Options: nosniff`).
- **No directory listing**: if the resolved path is a directory, return 404.
- **File existence check**: return 404 (not 500) if the file does not exist.
- **Read-only**: never write to the filesystem.

Safe path resolution pattern (must be followed exactly):
```python
STATIC_ROOT = Path(__file__).parent.parent / "static"

def resolve_static_path(raw_path: str) -> Path | None:
    # Strip leading /static/ prefix, remove query strings
    relative = raw_path.lstrip("/").removeprefix("static/")
    resolved = (STATIC_ROOT / relative).resolve()
    if not resolved.is_relative_to(STATIC_ROOT.resolve()):
        return None   # path traversal attempt
    if not resolved.is_file():
        return None   # directory listing or missing file
    return resolved
```

### `players_handler.py`
Handles `GET /api/players`.

Returns a JSON array of all players with the fields the frontend needs:
`id`, `full_name`, `team`, `position`, `now_cost`, `total_points`,
`selected_by_percent`, `form`.

Security responsibilities:
- No user input beyond the URL path (which the router already validated).
- Validate that the FPL API response contains the expected keys before accessing them.
  If the FPL API changes its schema, return a 502 with a generic message — never
  let a KeyError or IndexError propagate to the client as a 500.
- Apply the in-memory cache (`cache.py`) — bootstrap-static data is cached for 1 hour.
  This prevents the FPL API from being hammered if the page is refreshed rapidly.

### `history_handler.py`
Handles `GET /api/player/<id>/history`.

Returns a JSON array of per-gameweek stats for one player this season.

Security responsibilities:
- **Player ID validation**: the `<id>` path parameter must be a positive integer.
  Reject non-integer values with 400 before making any outbound request.
  Reject values outside a plausible range (1–2000) with 400.
  Never interpolate an unvalidated string into the FPL API URL.
- Validate FPL response shape before returning — if `history` key is absent, return 502.
- Cache per player ID with a 5-minute TTL (history updates at most once per gameweek,
  but a short TTL is safer than a long one during a live gameweek).

### `fixtures_handler.py`
Handles `GET /api/player/<id>/fixtures`.

Returns a JSON array of upcoming fixtures for one player.

Security responsibilities:
- Same player ID validation as `history_handler.py`.
- Validate FPL response shape — if `fixtures` key is absent, return 502.
- Cache per player ID with a 1-hour TTL (fixtures change only when the schedule changes).

## Security rules that apply to ALL handlers

1. **Never expose internal state**: exceptions are caught at the handler level.
   The client receives a status code and a short generic message. No tracebacks,
   no file paths, no variable names.

2. **Always set Content-Type**: every response sets `Content-Type` explicitly.
   Browsers that sniff types can be tricked into executing content as a different
   type than intended.

3. **Set security headers on every response** (applied in `base_handler.py`):
   ```
   X-Content-Type-Options: nosniff
   X-Frame-Options: DENY
   Cache-Control: no-store   (for API responses)
   ```

4. **Method enforcement**: handlers only respond to the methods they declare.
   The router rejects undeclared methods with 405 before the handler is called.

5. **No eval, no exec, no dynamic imports**: handlers never evaluate user-supplied
   strings as code.

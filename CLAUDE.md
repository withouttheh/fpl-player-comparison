# FPL Analytics — Root

## What this is
A pure-Python web application (zero frameworks) for comparing Fantasy Premier League players
side by side. Data is fetched live from the official FPL API. Charts are rendered in the
browser with D3.js. Styling uses Tailwind CSS via CDN. There is no database.

An end-of-season capture script (`capture.py`) snapshots all FPL API data to S3 before
the API resets — preserving gameweek-by-gameweek history that is otherwise lost.

## How to run
```bash
source venv/bin/activate
python server.py                # live FPL API data → http://localhost:8000
FPL_MOCK=1 python server.py    # local fixture data (no internet required)
```

## Data capture (run once per season)
```bash
source venv/bin/activate
python capture.py --season 2025-26          # full run (~10 min, 920 files)
python capture.py --season 2025-26 --dry-run  # preview without uploading
```

Requires AWS credentials in `~/.aws/credentials` with write access to `s3://fpl-api-raw`.

## Architecture overview

```
Browser
  ├── Tailwind CSS (CDN)
  ├── D3.js (CDN)
  └── fetch() calls → JSON API

Pure Python HTTP server (stdlib only)
  server.py       ← starts TCPServer, owns the event loop
  router.py       ← maps request paths to handler functions
  cache.py        ← in-memory TTL cache for FPL API responses

  handlers/       ← one file per route group (static files, players, history, fixtures)
  static/         ← HTML, JS, CSS served to the browser
  utils/          ← FPL data layer: loaders + preprocessors (no HTTP server knowledge)

FPL API (external, read-only)
  https://fantasy.premierleague.com/api/

S3 data archive (write-once, end-of-season)
  s3://fpl-api-raw/fpl/{season}/
  capture.py      ← standalone script, no dependency on the server layer
```

## File index

| File / Dir | Purpose |
|---|---|
| `server.py` | Entry point. Creates `ThreadingHTTPServer`, registers the router, starts listening. |
| `router.py` | Parses request path, validates method, dispatches to the correct handler. |
| `cache.py` | Thread-safe in-memory TTL cache. Wraps FPL API calls so the API is not hit on every request. |
| `capture.py` | End-of-season S3 capture script. Fetches bootstrap-static, fixtures, live GW data, dream teams, and all 841 element summaries. Re-run safe. |
| `pyproject.toml` | Ruff, pytest, and bandit config — single source of truth for tooling. |
| `requirements.txt` | Pinned runtime deps for `pip install -r`. Dev deps via `pip install -e ".[dev]"`. |
| `handlers/` | HTTP request handlers — one module per route group. All four handlers built and tested. |
| `static/` | `index.html`, `css/styles.css`, `js/app.js` — player comparison UI with D3.js charts. |
| `utils/` | FPL data layer. No HTTP knowledge. Loaders + preprocessors. |
| `data/` | Minimal mock fixtures used when `FPL_MOCK=1`. Committed to repo. |
| `tests/` | 221 tests: 191 unit + 30 Playwright e2e. |

## Security model (overview)

The application has three trust boundaries:

1. **Browser → server**: All user input arrives as URL paths and query strings.
   Validated and sanitised at the router before any handler sees it.

2. **Server → FPL API**: Outbound read-only HTTP. We validate FPL responses before
   using them — never assume the shape is what we expect.

3. **Server → filesystem**: Static file serving. Path traversal is the primary risk.
   Resolved at the static handler — no user-supplied path ever reaches `open()`
   without being checked against the static root.

Stack traces and internal errors are never written to HTTP responses.
All errors return a plain status code and a generic message.

## Key invariants

- Router stores `(module, "func_name")` tuples resolved via `getattr` at dispatch — enables test patching without dependency injection
- Cache keys: `players`, `history:{id}`, `fixtures:{id}`
- Cache TTLs: 3600s (players, fixtures), 300s (history)
- Player ID range: 1–2000, validated at handler level
- `requests.get(..., timeout=10)` on every outbound call
- Security headers on every response (X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy)
- Path traversal blocked with `Path.resolve()` + `is_relative_to()` — never `startswith()`
- Error messages never forwarded to client

## Python version
3.10+ (uses `match` statements and `Path.is_relative_to`).

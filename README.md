# FPL Analytics

A pure-Python web application for comparing Fantasy Premier League players side by side.
No web framework — the server, router, cache, and security layer are all hand-built.
Charts are rendered in the browser with D3.js. Data comes from the official FPL API.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python server.py              # live FPL API data  → http://127.0.0.1:8000
FPL_MOCK=1 python server.py   # local fixture data → http://127.0.0.1:8000
```

`FPL_MOCK=1` reads from `data/` instead of calling the FPL API. No internet required.

## Architecture

```
Browser ──HTTP──► server.py (ThreadedHTTPServer)
                     │
                  router.py (regex dispatch, security guards)
                     │
          ┌──────────┼──────────────┐
          │          │              │
   /api/players  /api/player   /static/**
          │       /{id}/…           │
   players_    history_      static_handler.py
   handler.py  handler.py    (path-traversal safe)
   fixtures_
   handler.py
          │
       cache.py (TTL, thread-safe)
          │
   utils/loaders/   utils/preprocessors/
   (FPL API HTTP)   (type coercion, ID→name)
          │
    api.fantasy.premierleague.com
```

**No third-party web framework.** `http.server.BaseHTTPRequestHandler` + `socketserver.ThreadingMixIn` only.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/players` | Full player roster with team, position, cost |
| GET | `/api/player/{id}/history` | Gameweek-by-gameweek stats for one player |
| GET | `/api/player/{id}/fixtures` | Upcoming fixtures with FDR for one player |
| GET | `/static/**` | Static assets (HTML, CSS, JS) |
| GET | `/` | Serves `static/index.html` |

Player IDs are validated server-side: must be 1–2000. Outside that range → 400.

## Caching

| Data | Cache key | TTL |
|------|-----------|-----|
| Player roster | `players` | 1 hour |
| Per-player history | `history:{id}` | 5 minutes |
| Per-player fixtures | `fixtures:{id}` | 1 hour |

All caching is in-memory, thread-safe, and TTL-based. Cache is cleared on server restart.

## Security

- **Path traversal**: `Path.resolve()` + `is_relative_to()` on every static file request
- **Input validation**: player IDs validated at router (format) and handler (range) level
- **Request limits**: URLs > 512 bytes → 414, null bytes → 400
- **Error safety**: exception messages are never forwarded to the client (always 502 with a generic message)
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy` on every response
- **Timeouts**: `requests.get(..., timeout=10)` on every outbound FPL API call

## Running tests

```bash
source venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

pytest tests/ --ignore=tests/e2e -v      # unit tests only (fast, no browser)
pytest tests/e2e/ -v                     # e2e browser tests (requires server)
pytest tests/ -v                         # everything
```

221 tests: 191 unit (cache, router, handlers, loaders, preprocessors) + 30 Playwright e2e
(search dropdown, player selection, D3 chart rendering, fixture FDR display).

## End-of-season data capture

The FPL API replaces gameweek-by-gameweek history with season totals when the new season
starts. Run `capture.py` before that happens to archive the raw data to S3.

```bash
source venv/bin/activate
python capture.py --season 2025-26           # full run (~10 minutes)
python capture.py --season 2025-26 --dry-run # preview without uploading
```

**What gets captured:**

| File | Description |
|------|-------------|
| `fpl/2025-26/bootstrap_static.json` | All players, teams, GW metadata |
| `fpl/2025-26/fixtures.json` | Full season fixture list with scores |
| `fpl/2025-26/live/{gw}.json` | Final points + bonus per GW (38 files) |
| `fpl/2025-26/dream_team/{gw}.json` | Optimal XI per GW (38 files) |
| `fpl/2025-26/element_summary/{id}.json` | Per-player GW history (841 files) |

Re-runs are safe — files already in S3 are skipped.

**AWS setup:** Requires `~/.aws/credentials` with an IAM user that has `s3:PutObject`,
`s3:GetObject`, and `s3:ListBucket` on `arn:aws:s3:::fpl-api-raw` and
`arn:aws:s3:::fpl-api-raw/*`.

## Project layout

```
server.py                    # Entry point — ThreadedHTTPServer
router.py                    # URL dispatch, security guards
cache.py                     # Thread-safe TTL cache (module singleton)
capture.py                   # End-of-season S3 data capture (standalone script)
handlers/
  base_handler.py            # Shared send_json / send_error helpers
  players_handler.py         # GET /api/players
  history_handler.py         # GET /api/player/{id}/history
  fixtures_handler.py        # GET /api/player/{id}/fixtures
  static_handler.py          # GET /static/** and GET /
utils/
  config.py                  # FPL API base URL, column list, colour constants
  loaders/
    base_loader.py                  # requests.get wrapper with timeout + raise_for_status
    bootstrap_static_loader.py      # ElementsLoader + TeamsLoader (player roster, teams)
    elements_summary_loader.py      # FixturesLoader + HistoryLoader + HistoryPastLoader
  preprocessors/
    base_preprocessor.py            # Team ID → short name, full_name, position mapping
    bootstrap_static_preprocessors.py   # ElementsPreprocessor (players list → response shape)
    elements_summary_preprocessors.py   # HistoryPreprocessor + FixturesPreprocessor
static/
  index.html                 # Single-page app shell
  js/app.js                  # D3.js charts, search, GW range filter
  css/styles.css             # Chart-specific styles (Tailwind handles everything else)
data/
  bootstrap_static.json      # Mock FPL API response for FPL_MOCK=1 mode
  element_summary.json       # Mock per-player data for FPL_MOCK=1 mode
tests/
  fixtures/                  # Minimal JSON replicas of FPL API responses
  helpers.py                 # MockRequest, MockHTTPResponse, make_url_router
  test_cache.py
  test_router.py
  handlers/                  # One test file per handler
  utils/                     # One test file per loader/preprocessor
  e2e/                       # Playwright browser tests
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full request lifecycle and recommended file reading order.

## Data sources

All data comes from the official FPL API (no API key required):

| Endpoint | What it provides |
|----------|-----------------|
| `/bootstrap-static/` | Player roster, team list, element types |
| `/element-summary/{id}/` | Per-player fixtures, this-season history, past-season history |
| `/fixtures/` | Full season fixture list |
| `/event/{gw}/live/` | Live and final GW points |
| `/dream-team/{gw}/` | Optimal XI per gameweek |

## Dependencies

Runtime: `requests`, `pandas`, `boto3`

Development: `pytest`, `pytest-playwright`, `ruff`, `bandit`

```bash
pip install -r requirements.txt          # runtime only
pip install -e ".[dev]"                  # runtime + dev tools
```

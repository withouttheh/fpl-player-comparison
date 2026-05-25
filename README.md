[![CI](https://github.com/withouttheh/fpl-player-comparison/actions/workflows/ci.yml/badge.svg)](https://github.com/withouttheh/fpl-player-comparison/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

# FPL Analytics

Compare any two Fantasy Premier League players side by side — gameweek by gameweek, stat by stat.

Built with no web framework. The HTTP server, router, TTL cache, and security layer are all hand-written in pure Python so every layer is understandable and auditable. Charts render in the browser with D3.js.

## Features

- **Player search** — autocomplete across all ~841 players, filter by name or team
- **Side-by-side comparison** — bar chart (per gameweek) and cumulative line chart for any stat
- **24 stats** — goals, assists, clean sheets, xG, xA, ICT index, bonus, minutes, and more
- **GW range filter** — zoom into any gameweek window, charts update instantly
- **Fixture difficulty** — upcoming fixtures colour-coded by FDR (1–5) for both players
- **Offline mode** — `FPL_MOCK=1` runs against local fixture data, no internet required
- **End-of-season archive** — `scripts/capture.py` snapshots the full FPL API to S3 before history is lost

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python server.py              # live FPL API data  → http://127.0.0.1:8000
FPL_MOCK=1 python server.py   # local fixture data → http://127.0.0.1:8000
```

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

- **XSS prevention**: all API-sourced strings escaped via `escapeHTML()` before DOM insertion; FDR values clamped to 1–5 before use as CSS class suffixes
- **Path traversal**: `Path.resolve()` + `is_relative_to()` on every static file request — no `startswith()` hacks
- **Input validation**: player IDs validated at router (format) and handler (range) level
- **Request limits**: URLs > 512 bytes → 414, null bytes → 400
- **Error safety**: exception messages never forwarded to client (always generic 502)
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy` on every response
- **Timeouts**: `requests.get(..., timeout=10)` on every outbound FPL API call
- **Static analysis**: bandit reports 0 issues across the codebase

## Running tests

```bash
source venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

pytest tests/ --ignore=tests/e2e -v      # unit tests only (fast, no browser)
pytest tests/e2e/ -v                     # e2e browser tests (requires server)
pytest tests/ -v                         # everything
```

221 tests: 191 unit (cache, router, handlers, loaders, preprocessors) + 30 Playwright e2e (search dropdown, player selection, D3 chart rendering, fixture FDR display).

## End-of-season data capture

The FPL API replaces gameweek-by-gameweek history with season totals when the new season starts. Run `scripts/capture.py` once at end of season to archive the raw data to S3 before it is lost.

```bash
source venv/bin/activate
python scripts/capture.py --season 2025-26           # full run (~10 minutes, ~920 files)
python scripts/capture.py --season 2025-26 --dry-run # preview without uploading
```

Re-runs are safe — files already in S3 are skipped automatically.

**What gets captured per season:**

| S3 path | Description |
|---------|-------------|
| `fpl/{season}/bootstrap_static.json` | All players, teams, GW metadata |
| `fpl/{season}/fixtures.json` | Full season fixture list with scores |
| `fpl/{season}/live/{1..38}.json` | Final points + bonus per GW |
| `fpl/{season}/dream_team/{1..38}.json` | Optimal XI per GW |
| `fpl/{season}/element_summary/{id}.json` | Per-player GW history (~841 files) |

**IAM policy** (attach to a dedicated IAM user, not the bucket):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"],
    "Resource": ["arn:aws:s3:::YOUR-BUCKET", "arn:aws:s3:::YOUR-BUCKET/*"]
  }]
}
```

Credentials go in `~/.aws/credentials` — never in this repository.

## Project layout

```
server.py                    # Entry point — ThreadedHTTPServer
router.py                    # URL dispatch, security guards
cache.py                     # Thread-safe TTL cache (module singleton)
scripts/
  capture.py                 # End-of-season S3 data capture (standalone)
handlers/
  base_handler.py            # Shared send_json / send_error / security headers
  players_handler.py         # GET /api/players
  history_handler.py         # GET /api/player/{id}/history
  fixtures_handler.py        # GET /api/player/{id}/fixtures
  static_handler.py          # GET /static/** and GET /
utils/
  config.py                  # FPL API base URL, column list, colour constants
  loaders/
    base_loader.py                  # requests.get wrapper with timeout + raise_for_status
    bootstrap_static_loader.py      # ElementsLoader + TeamsLoader
    elements_summary_loader.py      # FixturesLoader + HistoryLoader + HistoryPastLoader
  preprocessors/
    base_preprocessor.py            # Team ID → short name, full_name, position mapping
    bootstrap_static_preprocessors.py
    elements_summary_preprocessors.py
static/
  index.html                 # Single-page app shell
  js/app.js                  # D3.js charts, search autocomplete, GW range filter
  css/styles.css             # Chart-specific styles (Tailwind handles everything else)
data/
  bootstrap_static.json      # Mock FPL API response for FPL_MOCK=1
  element_summary.json       # Mock per-player data for FPL_MOCK=1
tests/
  fixtures/                  # Minimal JSON replicas of FPL API responses
  helpers.py                 # MockRequest, MockHTTPResponse, make_url_router
  test_cache.py / test_router.py
  handlers/                  # One test file per handler
  utils/                     # One test file per loader and preprocessor
  e2e/                       # Playwright browser tests (Chromium)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full request lifecycle and recommended reading order.

## Data sources

All data comes from the official FPL API — no API key required.

| Endpoint | Provides |
|----------|---------|
| `/bootstrap-static/` | Player roster, teams, GW metadata |
| `/element-summary/{id}/` | Per-player GW history, fixtures, past season totals |
| `/fixtures/` | Full season fixture list |
| `/event/{gw}/live/` | Live and final GW points |
| `/dream-team/{gw}/` | Optimal XI per gameweek |

## Dependencies

| | Packages |
|--|---------|
| Runtime | `requests`, `pandas`, `boto3` |
| Dev | `pytest`, `pytest-playwright`, `ruff`, `bandit` |

```bash
pip install -r requirements.txt   # runtime only
pip install -e ".[dev]"           # runtime + dev tools
```

## License

MIT — see [LICENSE](LICENSE).

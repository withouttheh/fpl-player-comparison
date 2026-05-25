# Architecture & Reading Guide

This document explains what the codebase does, how data moves through it, and
the order to read the files if you want to understand it properly. It also
explains how developers generally approach an unfamiliar codebase — because
that skill matters more than knowing any single project.

---

## How developers figure out a codebase

There is a standard playbook. In roughly this order:

**1. Find the entry point.**
Every program starts somewhere. For a web server it is usually `main()`, `app.py`,
`server.py`, or `wsgi.py`. For a CLI it is `__main__.py`. For a library it is
`__init__.py`. Start there and follow execution forward.

**2. Trace one complete request or operation end-to-end.**
Don't try to understand everything at once. Pick one concrete thing —
"what happens when the browser asks for the player list?" — and follow it
through every function and file until you have the full picture. One complete
path teaches you more than skimming ten files.

**3. Read the tests before the implementation.**
Tests are executable specifications. A well-written test tells you:
- What a function is supposed to do
- What inputs are valid
- What the edge cases are
- What security properties are enforced
Reading `test_router.py` tells you everything the router is expected to handle
without having to infer it from the code.

**4. Read base/parent classes before subclasses.**
`BaseLoader` is simpler than `HistoryLoader`. `BasePreprocessor` is simpler than
`ElementsPreprocessor`. Understanding the parent first means subclasses only
add a small delta, not a complete puzzle.

**5. Read the config and constants.**
`config.py`, `.env` files, and settings files tell you what values the system
depends on, which services it connects to, and what the boundaries are.
They are usually small and reveal a lot about what the system does.

**6. Use grep to trace data.**
When you encounter a term you don't understand — a field name, a function call,
a variable — grep for it across the codebase. `grep -r "player_id" .` shows
every file that touches that concept and gives you a map of the data's journey.

**7. Read git log.**
`git log --oneline` shows you the history of decisions. Commit messages explain
*why* things changed, not just what changed. This is where intent lives.

**8. Trust the tests, verify the comments.**
Comments can go stale. Tests fail loudly when they are wrong. When a comment
and a test disagree, trust the test.

---

## What this codebase is

A pure-Python HTTP server (no frameworks) that serves a web app for comparing
two Fantasy Premier League players side by side. It fetches live data from the
official FPL API, caches it in memory, and returns JSON to a browser frontend
that renders charts with D3.js.

**Tech stack:**
- Python stdlib only for the server (http.server, socketserver, threading, re, urllib)
- `pandas` for data wrangling in the data layer
- `requests` for outbound FPL API calls
- `boto3` for end-of-season S3 data capture
- D3.js + Tailwind CSS in the browser

---

## The complete data flow

This is what happens when a browser requests the player list.
Every other request follows the same path with minor variations.

```
Browser
  └── GET /api/players
        │
        ▼
server.py — RequestHandler.do_GET()
        │   Python's http.server calls this for every GET request.
        │   It does nothing except hand off to the router.
        │
        ▼
router.py — Router.dispatch()
        │   1. Check path length (414 if too long)
        │   2. urlparse() to strip query string
        │   3. Check for null bytes (400 if found)
        │   4. Collapse double slashes
        │   5. Match path against ROUTES regex patterns
        │   6. Verify HTTP method (405 if wrong method)
        │   7. Extract path params via match.groupdict()
        │   8. Resolve handler: getattr(module, func_name)
        │   9. Call handler(request, **params)
        │
        ▼
handlers/players_handler.py — serve_players()
        │   1. Check cache.get("players")
        │      ├── Cache hit  → skip to serialisation
        │      └── Cache miss → fetch from FPL API
        │
        │   On cache miss:
        │   2. TeamsLoader(base_url).get_teams_data()
        │   3. ElementsLoader(base_url).get_elements_data()
        │   4. ElementsPreprocessor.preprocess_elements()
        │   5. Divide now_cost by 10
        │   6. Select output columns
        │   7. cache.set("players", result, ttl=3600)
        │
        ▼
handlers/base_handler.py — send_json()
        │   1. json.dumps(data, ensure_ascii=False).encode("utf-8")
        │   2. send_response(200)
        │   3. Set Content-Type, Content-Length, Cache-Control
        │   4. Set security headers (X-Content-Type-Options, X-Frame-Options,
        │      Content-Security-Policy, Referrer-Policy)
        │   5. end_headers()
        │   6. wfile.write(body)
        │
        ▼
Browser receives JSON array of player objects
```

### The FPL API layer (zoomed in)

When `players_handler` needs fresh data:

```
ElementsLoader(base_url)
    │
    └── inherits BootstrapStaticLoader
            │
            └── inherits BaseLoader
                    │
                    └── requests.get(
                            "https://fantasy.premierleague.com/api/bootstrap-static/",
                            timeout=10
                        )
                        │
                        └── returns raw JSON dict
                                │
                        ElementsLoader.get_elements_data()
                                │
                                └── pd.DataFrame(data["elements"])
                                        │
                        ElementsPreprocessor(df, teams_df)
                                │
                                ├── create_full_name()        first + last name
                                ├── map_element_type_to_position()  1→GK etc.
                                └── replace_team_ids_with_names()   42→"LIV"
                                        │
                                        └── clean DataFrame ready for JSON
```

### The cache layer (zoomed in)

```
cache.get("players")
    │
    ├── key not in _store          → None (miss)
    ├── time.monotonic() >= expiry → None (expired, entry removed)
    └── entry valid                → return value (hit)

cache.set("players", data, ttl=3600)
    │
    └── _store["players"] = (data, time.monotonic() + 3600)
        held under RLock so concurrent threads don't corrupt the dict
```

---

## File reading order

Read in this order. Each file is explained with what to look for.

### Phase 1: Orientation (10 minutes)

**1. `README.md`**
The public face. What the app does, how to run it, what it depends on.
Tells you the shape of the thing before you look at any code.

**2. `CLAUDE.md`**
Internal context. Architecture overview, file index, security model summary,
known issues. Written for developers, not users.

**3. `utils/config.py`**
Small file. Tells you the FPL API base URL and what columns the API returns.
After this you know what the external dependency is and what data it exposes.

### Phase 2: The server layer (20 minutes)

**4. `server.py`**
The entry point. Read it to understand:
- How Python's HTTPServer works
- Why ThreadingMixIn (shared memory for cache)
- Why daemon_threads and allow_reuse_address
- Why 127.0.0.1 and not 0.0.0.0
- The `finally: server.server_close()` pattern

**5. `router.py`**
Read it to understand:
- How ROUTES is structured and why (module, "func_name") not a direct reference
- How urlparse separates path from query string
- Each security guard and why it exists (null bytes, length, method enforcement)
- Why named regex groups (?P<player_id>) make dispatch clean

**6. `cache.py`**
Read it to understand:
- Why time.monotonic() not time.time()
- Why RLock (re-entrant) not Lock
- Why a module-level singleton (Python import caching)
- Lazy expiry on read vs background sweeper

### Phase 3: The handler layer (20 minutes)

**7. `handlers/base_handler.py`**
Read this before any specific handler. It is the vocabulary everything else uses.
Pay attention to:
- Why every function calls `_send_security_headers()`
- What each security header does and why
- Why `ensure_ascii=False` in json.dumps
- Why Content-Length must always be set
- Why errors return plain text without exception messages

**8. `handlers/static_handler.py`**
The most security-critical file in the project. Read it slowly.
Pay attention to:
- `STATIC_ROOT.resolve()` — why resolve() and not just the raw path
- `is_relative_to()` — why not `startswith()`
- `unquote()` — why decode after stripping the prefix, not before
- `mimetypes.guess_type()` — why derive type from extension, not from request
- The fallback to `application/octet-stream`

**9. `handlers/players_handler.py`**
The simplest API handler. Read it to see the pattern:
cache check → fetch → preprocess → serialise.
Note `_OUTPUT_FIELDS` — why we select a subset of columns, not the whole DataFrame.

**10. `handlers/history_handler.py`**
Same pattern as players but with a path parameter.
Pay attention to:
- Why we validate `player_id` range here even though the router already checked format
- Why we use `int(player_id)` defensively even though `\d+` guarantees digits
- The cache key format `"history:{player_id}"` (namespaced to avoid collisions)
- Float casting for ICT/xG columns (FPL API returns these as strings)

**11. `handlers/fixtures_handler.py`**
Same pattern as history. Read it to confirm the pattern is consistent,
then note the different TTL (1 hour vs 5 minutes) and why.

### Phase 4: The data layer (20 minutes)

**12. `utils/loaders/base_loader.py`**
Small. Understand:
- Why `timeout=10` is non-negotiable
- Why `raise_for_status()` before parsing JSON
- Why errors return `None` not raise (the handler decides what to do with failure)

**13. `utils/loaders/bootstrap_static_loader.py`**
The inheritance chain: `BaseLoader → BootstrapStaticLoader → ElementsLoader/TeamsLoader`.
One HTTP call, two classes that extract different sections of the response.

**14. `utils/loaders/elements_summary_loader.py`**
Per-player data. One player ID → three sections (fixtures, history, history_past).
Three classes, each extracting one section.

**15. `utils/preprocessors/base_preprocessor.py`**
Small. The shared transforms. Read this before the subclasses or they won't make sense.

**16. `utils/preprocessors/bootstrap_static_preprocessors.py`**
One class, three method calls. Cross-reference with base_preprocessor to see
exactly what each method does.

**17. `utils/preprocessors/elements_summary_preprocessors.py`**
Three classes for fixtures, history, and past history.
Note that `HistoryPastPreprocessor` takes no teams_data (FPL past history
uses team names directly, not IDs).

### Phase 5: The tests (20 minutes)

**18. `tests/test_cache.py`**
Read the test names before the code. Each name is a specification statement.
Look at `TestTTLCacheExpiry` — this is where the `>=` vs `>` boundary was caught.
Look at `TestTTLCacheThreadSafety` — concurrent stress tests with real threads.

**19. `tests/test_router.py`**
Look at `TestRouterSecurityGuards` first. These are the attacks the router defends against.
Then `TestRouterNotFound` — all the malformed player IDs (letters, floats, negatives).
Then `TestRouterPathNormalisation` — and the comment explaining why `//api/players`
gives a 404 (it is a protocol-relative URL, not a double-slash path).

---

## Layer map

```
┌─────────────────────────────────────────────────────────┐
│  Browser (D3.js + Tailwind CSS)                          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│  server.py           Transport layer                      │
│  router.py           Routing + security guards            │
│  handlers/           Request → Response                   │
│    base_handler.py   Shared response helpers              │
│    static_handler.py Filesystem → browser                 │
│    players_handler.py                                     │
│    history_handler.py  FPL data → JSON                   │
│    fixtures_handler.py                                    │
└──────────────────────┬──────────────────────────────────┘
                       │ function calls
┌──────────────────────▼──────────────────────────────────┐
│  cache.py            In-memory TTL cache (cross-cutting)  │
└──────────────────────┬──────────────────────────────────┘
                       │ on cache miss
┌──────────────────────▼──────────────────────────────────┐
│  utils/loaders/      FPL API → raw DataFrames             │
│  utils/preprocessors/ raw DataFrames → clean DataFrames  │
│  utils/config.py     Constants                            │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (outbound, read-only)
┌──────────────────────▼──────────────────────────────────┐
│  FPL API             External dependency                  │
│  fantasy.premierleague.com/api/                          │
└──────────────────────┬──────────────────────────────────┘
                       │ capture.py (end-of-season, one-shot)
┌──────────────────────▼──────────────────────────────────┐
│  S3                  Long-term raw data archive           │
│  s3://fpl-api-raw/fpl/2025-26/                          │
└─────────────────────────────────────────────────────────┘
```

---

## S3 data pipeline

At end of season, `capture.py` snapshots the entire FPL API to S3 before the API resets.
This is a standalone script — it has no dependency on the server layer.

```
capture.py
    │
    ├── GET /bootstrap-static/        → s3://fpl-api-raw/fpl/2025-26/bootstrap_static.json
    ├── GET /fixtures/                → s3://fpl-api-raw/fpl/2025-26/fixtures.json
    ├── GET /event/{1..38}/live/      → s3://fpl-api-raw/fpl/2025-26/live/{gw}.json
    ├── GET /dream-team/{1..38}/      → s3://fpl-api-raw/fpl/2025-26/dream_team/{gw}.json
    └── GET /element-summary/{id}/   → s3://fpl-api-raw/fpl/2025-26/element_summary/{id}.json
              × 841 players
```

Re-runs are safe: `s3.head_object` checks each key before fetching. Already-uploaded
files are skipped so a partial run can be resumed without re-uploading.

---

## Key patterns used (and where to find them)

| Pattern | Where | Why |
|---|---|---|
| Inheritance for shared behaviour | `BaseLoader`, `BasePreprocessor` | Don't repeat HTTP fetch logic or team-mapping logic in every class |
| Module-level singletons | `cache.py` | Python imports once per process — all threads share the same object automatically |
| (module, "func_name") late binding | `router.py` ROUTES | Allows test patches to intercept handler calls without dependency injection |
| Fake clock in tests | `tests/test_cache.py` | Tests must not sleep — patch `time.monotonic` to control time |
| Security headers in one place | `handlers/base_handler.py` | No handler can forget them |
| `Path.resolve() + is_relative_to()` | `handlers/static_handler.py` | The only safe way to check path traversal |
| `timeout=10` on every HTTP call | `utils/loaders/base_loader.py` | Prevents thread starvation when FPL API is slow |

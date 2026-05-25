# tests/

## Purpose
Test suite for the application. Uses `pytest`. Tests are organised to mirror
the source tree — one test module per source module.

## Structure

```
tests/
  fixtures/
    bootstrap_static.json       ✓ minimal FPL bootstrap (2 teams, 2 players)
    element_summary.json        ✓ 2 upcoming fixtures, 2 gameweeks of history
  helpers.py                    ✓ MockRequest, MockHTTPResponse, make_url_router
  handlers/
    test_static_handler.py      ✓ path traversal, MIME types, 404 on directory (23 tests)
    test_players_handler.py     ✓ JSON shape, cache hit/miss, FPL API failure → 502 (22 tests)
    test_history_handler.py     ✓ player ID validation, valid range, FPL failure → 502 (26 tests)
    test_fixtures_handler.py    ✓ same as history (19 tests)
  utils/
    loaders/
      test_base_loader.py       ← planned: timeout enforcement, error on non-200
      test_bootstrap_loader.py  ← planned: missing keys raise ValueError
      test_elements_loader.py   ← planned: missing keys, empty response
    preprocessors/
      test_base_preprocessor.py      ← planned: team mapping, full_name, position mapping
      test_elements_preprocessor.py  ← planned
      test_history_preprocessor.py   ← planned
  test_router.py                ✓ path parsing, method rejection, unknown paths → 404 (44 tests)
  test_cache.py                 ✓ TTL expiry, thread safety, cache miss calls through (17 tests)
```

Total: **137 tests** (as of last run). All passing.

## Priority order

Test security-critical paths first:

1. **Path traversal** (`test_static_handler.py`) — the highest-risk handler.
   Must test: `../../`, `%2e%2e%2f` (URL-encoded), absolute paths, null bytes,
   paths ending in `/` (directory listing).

2. **Player ID validation** (`test_history_handler.py`, `test_fixtures_handler.py`).
   Must test: letters, negative integers, floats, empty string, very large integers,
   SQL-like strings, path separators.

3. **FPL API failure handling** — all handlers must return 502 (not 500, not a traceback)
   when the loader returns `None` or raises.

4. **Cache behaviour** (`test_cache.py`) — TTL expiry must be testable without
   actually sleeping; use a fake clock via `unittest.mock.patch`.

## Rules

- Every test file starts by importing only from the project source — no relative
  imports that break when run from a different working directory.
- Tests never make real HTTP requests to the FPL API. Use `unittest.mock.patch`
  on `requests.get` to return fixture data.
- Fixture data (sample FPL API JSON responses) lives in `tests/fixtures/` as `.json`
  files, not inline in test code. This makes it easy to update when the FPL API
  schema changes.
- Tests run with `pytest` from the project root:
  ```bash
  source venv/bin/activate
  pytest tests/
  ```

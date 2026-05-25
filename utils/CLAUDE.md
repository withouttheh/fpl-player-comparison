# utils/

## Purpose
The FPL data layer. Handles all communication with the FPL API and all data
transformation. Has no knowledge of HTTP servers, request handling, or the browser.
Can be tested in isolation and reused independently of the web layer.

## Subdirectories

### `loaders/`
Responsible for making HTTP requests to the FPL API and returning raw DataFrames.
See `loaders/CLAUDE.md`.

### `preprocessors/`
Responsible for transforming raw DataFrames — resolving team IDs to names,
adding computed columns, filtering. No network calls. See `preprocessors/CLAUDE.md`.

## Files

### `config.py`
Global constants:
- `base_url` — FPL API base URL (`https://fantasy.premierleague.com/api`)
- `elem_cols` — the full list of columns in the elements response
- `colors` — FPL brand colours (green/purple)
- `fdr` — Fixture Difficulty Rating colour map (1–5)

**Security note**: `config.py` contains no secrets. The FPL API requires no
authentication. If that ever changes, secrets must come from environment variables,
not from this file.

## Data flow

```
Handler calls cache.py
  └── Cache miss → loader fetches from FPL API → preprocessor transforms → cached
  └── Cache hit  → preprocessor transforms (if needed) → returned to handler
Handler serialises DataFrame columns to JSON dict
Handler sends JSON response
```

## Security rules

1. **No user input enters this layer.** Handlers validate and sanitise all user
   input before passing anything to utils. A player ID passed to a loader must
   already be a confirmed integer in a valid range — utils does not re-validate.

2. **FPL API responses are validated before use.** Loaders check that expected
   keys exist before constructing DataFrames. A missing key raises a descriptive
   exception that the handler catches and converts to a 502 — it does not propagate
   as an unhandled crash.

3. **No credentials stored here.** `config.py` contains only public constants.

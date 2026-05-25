# utils/loaders/

## Purpose
All outbound HTTP communication with the FPL API lives here.
Each loader class fetches one section of the API and returns a raw pandas DataFrame.
No data transformation beyond DataFrame construction happens in this layer.

## File index

### `base_loader.py`
`BaseLoader` — parent for all loaders.

Core method: `load_data(endpoint) -> dict | None`
- Constructs the full URL as `{base_url}/{endpoint}`
- Makes a GET request via `requests`
- Raises on HTTP errors (`raise_for_status`)
- Returns parsed JSON dict, or `None` on any network/HTTP failure

Security responsibilities:
- **Timeout on every request**: every `requests.get()` call must pass `timeout=10`.
  Without a timeout, a slow or unresponsive FPL API stalls the server thread
  indefinitely, eventually exhausting the thread pool.
- **No user input in URLs**: `load_data` receives an endpoint string that is
  constructed by the loader subclass, never by user input. The handler layer
  validates player IDs before they reach the loader.
- **Error containment**: network exceptions are caught and logged to stderr.
  `None` is returned — the handler converts `None` to a 502. Stack traces
  never reach the HTTP response.

```python
# Correct pattern — always use timeout
r = requests.get(full_url, timeout=10)
```

### `bootstrap_static_loader.py`
Loads `GET /bootstrap-static/` — the full player roster and team list for the current season.

- `BootstrapStaticLoader` — fetches the endpoint once in `__init__`, stores raw JSON
- `ElementsLoader(BootstrapStaticLoader)` — extracts `data['elements']` → DataFrame
- `TeamsLoader(BootstrapStaticLoader)` — extracts `data['teams']` → DataFrame

Response validation:
```python
# Both keys must be present before constructing DataFrames
if 'elements' not in self.data:
    raise ValueError("FPL API response missing 'elements' key")
if 'teams' not in self.data:
    raise ValueError("FPL API response missing 'teams' key")
```

Cache TTL (set by `cache.py` caller): **1 hour**.
Bootstrap-static changes only when the FPL team processes transfers or updates
player data — at most a few times per day outside of deadline windows.

### `elements_summary_loader.py`
Loads `GET /element-summary/{element_id}/` — per-player data.

- `ElementsSummaryLoader` — fetches the endpoint for one player ID, stores raw JSON
- `FixturesLoader` — extracts `data['fixtures']` → DataFrame (upcoming fixtures)
- `HistoryLoader` — extracts `data['history']` → DataFrame (this season, per gameweek)
- `HistoryPastLoader` — extracts `data['history_past']` → DataFrame (past seasons)

**The element_id must be a validated integer before this loader is instantiated.**
This is enforced by the handler layer, not here — but it is documented here because
it is the contract this loader relies on.

Response validation:
```python
if self.data is None:
    raise ValueError(f"Failed to fetch element-summary for id {element_id}")
for key in ('fixtures', 'history', 'history_past'):
    if key not in self.data:
        raise ValueError(f"FPL API response missing '{key}' key")
```

Cache TTL:
- `FixturesLoader`: **1 hour** (fixture schedule rarely changes mid-day)
- `HistoryLoader`: **5 minutes** (updates during live gameweeks)
- `HistoryPastLoader`: **24 hours** (historical data never changes in-season)

## Security rules

1. **Always pass `timeout=10` to `requests.get()`**.
   This is the single most important rule in this file. No exceptions.

2. **Validate response keys before DataFrame construction**.
   `pd.DataFrame(None)` or `pd.DataFrame({})` produces an empty frame with no error —
   which then causes a confusing failure later. Fail loudly here with a descriptive
   exception so the handler can return a clear 502.

3. **No user input in endpoint strings**.
   `element_id` arrives as a validated integer. Loaders cast it to `int()` internally
   as a defensive measure even though the handler already validated it.

4. **Log errors to stderr, not stdout**.
   `server.py` may redirect stdout. Errors must go to stderr so they are always visible.

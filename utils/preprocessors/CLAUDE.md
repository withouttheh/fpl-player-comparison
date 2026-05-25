# utils/preprocessors/

## Purpose
Transforms raw DataFrames produced by the loaders into shapes the handlers
can serialise and send to the browser. No network calls. No user input.
No side effects beyond mutating the DataFrame passed in.

## File index

### `base_preprocessor.py`
`BasePreprocessor` — shared transforms used by all subclasses.

Methods:
- `_build_team_mapping()` — builds a `{team_id: short_name}` dict from `teams_data`
- `replace_team_ids_with_names(column_names)` — maps integer team IDs to short names in-place
- `map_element_type_to_position()` — maps `element_type` int (1–4) to GK/DEF/MID/FWD string
- `create_full_name()` — concatenates `first_name` + `second_name` into `full_name`

All methods mutate `self.data` in-place and return it.
The team mapping is built once in `__init__` and reused across all column replacements.

### `bootstrap_static_preprocessors.py`
`ElementsPreprocessor(BasePreprocessor)` — prepares the player roster DataFrame.

`preprocess_elements(team_columns)`:
1. `create_full_name()` — adds `full_name`
2. `map_element_type_to_position()` — adds `position`
3. `replace_team_ids_with_names(team_columns)` — resolves team IDs in `['team']`

Output columns used by the frontend: `id`, `full_name`, `team`, `position`,
`now_cost`, `total_points`, `selected_by_percent`, `form`.

### `elements_summary_preprocessors.py`
Three preprocessors for per-player data from `element-summary/{id}/`:

`FixturesPreprocessor(BasePreprocessor)` — `preprocess_fixtures(column_names)`
- Resolves team IDs in `team_h` and `team_a` to short names
- Output used by the frontend to show upcoming fixtures with FDR colour coding

`HistoryPreprocessor(BasePreprocessor)` — `preprocess_history(column_names)`
- Resolves team ID in `opponent_team` to short name
- Output used by the frontend for per-gameweek stat charts

`HistoryPastPreprocessor(BasePreprocessor)` — no team mapping needed
- Past season data uses team names directly (FPL API behaviour)
- Currently no transformation — placeholder for future per-season aggregation

## Security rules

1. **No user input processed here.** Preprocessors receive DataFrames from loaders.
   The shape of those DataFrames is determined by the FPL API response, not by the user.

2. **Validate column existence before access.** If `replace_team_ids_with_names`
   is called with a column name that does not exist in the DataFrame, it must raise
   a descriptive `KeyError`, not silently return corrupt data. This surfaces FPL API
   schema changes immediately rather than sending wrong data to the browser.

3. **Do not modify the original teams_data DataFrame.** `_build_team_mapping` reads
   from it; it must not write to it. Use it as a lookup only.

4. **Float conversion for ICT/xG fields.** The FPL API returns `influence`,
   `creativity`, `threat`, `ict_index`, `expected_goals`, `expected_assists`,
   `expected_goal_involvements`, `expected_goals_conceded` as strings, not floats.
   These must be explicitly cast to float before any arithmetic or chart rendering.
   This is done in the preprocessor, not in the handler or the frontend.

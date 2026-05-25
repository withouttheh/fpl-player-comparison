# /update-docs

Update all documentation to reflect the current state of the codebase.

Run through each of the following checks and make the necessary edits. Work through them in order — later steps build on earlier ones.

## 1. README.md

Read `README.md` and compare it against the actual project structure:

- Run `find . -name "*.py" -not -path "./venv/*" -not -path "./__pycache__/*" | sort` to see what files exist
- Check that the **Project layout** section lists every real module (add missing ones, remove deleted ones)
- Check that the **API endpoints** table matches `router.py` — compare against the ROUTES list
- Check that the **Caching** table TTL values match the `_CACHE_TTL` constants in each handler
- Check that the **Requirements** section doesn't mention packages that no longer exist in `requirements.txt`
- Check the **Running tests** section — run `pytest tests/ --collect-only -q 2>/dev/null | tail -1` and update the test count

## 2. ARCHITECTURE.md

Read `ARCHITECTURE.md` and verify:

- The ASCII request lifecycle diagram matches the actual call chain in `server.py → router.py → handlers/`
- The numbered file reading order still makes sense (no files listed that don't exist)
- Any layer descriptions still match what the code does

## 3. Directory CLAUDE.md files

For each directory that has a `CLAUDE.md`, read it and check:

- The module list is current (no phantom files, no missing files)
- Any documented invariants still hold (e.g. cache key format, TTL values, output field lists)
- Any "planned" items that are now complete should be updated

Directories to check:
- `.` (root `CLAUDE.md`)
- `handlers/CLAUDE.md`
- `utils/CLAUDE.md`
- `utils/loaders/CLAUDE.md`
- `utils/preprocessors/CLAUDE.md`
- `tests/CLAUDE.md`
- `static/CLAUDE.md`

## 4. Handler output fields

For each handler, verify the docs match the code:

```bash
grep "_OUTPUT_FIELDS" handlers/*.py
grep "_CACHE_TTL" handlers/*.py
grep "_CACHE_KEY" handlers/*.py
grep "_MAX_PLAYER_ID" handlers/*.py
```

If any documented values differ from the constants in code, update the docs to match the code (the code is the source of truth).

## 5. Test count

After any edits, run:

```bash
pytest tests/ -q 2>&1 | tail -3
```

Update the test count in README.md if it changed.

## Done

Report a brief summary of what changed (by file) and what was already up-to-date.
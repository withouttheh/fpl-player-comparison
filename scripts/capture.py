"""
capture.py — Snapshot raw FPL API data to S3 at end of season.

The FPL API replaces per-gameweek history with season totals when the new
season starts. This script captures the raw JSON before that happens.

S3 layout:
    fpl-api-raw/
      fpl/2025-26/
        bootstrap_static.json        # all players, teams, GW metadata
        fixtures.json                # full season fixture list with scores
        element_summary/
          1.json                     # per-player GW history + past seasons
          2.json
          ...
        live/
          1.json                     # final points + bonus for GW1
          2.json
          ...
        dream_team/
          1.json                     # optimal XI for GW1
          2.json
          ...

Re-runs are safe: files already in S3 are skipped.

Usage:
    python capture.py                  # full run
    python capture.py --dry-run        # print what would upload, fetch nothing
    python capture.py --season 2025-26 # override season label (recommended)
"""

import argparse
import json
import time
import sys

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FPL_BASE      = "https://fantasy.premierleague.com/api"
BUCKET        = "fpl-api-raw"
REQUEST_DELAY = 0.5   # seconds between FPL API calls — be polite
TIMEOUT       = 10    # seconds per request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fpl_get(path: str) -> dict | list | None:
    url = f"{FPL_BASE}/{path}"
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] fetch failed {url}: {exc}", file=sys.stderr)
        return None


def s3_key_exists(s3, key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def s3_put(s3, key: str, data: dict | list, dry_run: bool) -> bool:
    if dry_run:
        print(f"  [DRY] would upload → s3://{BUCKET}/{key}")
        return True
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(data, separators=(",", ":")),
            ContentType="application/json",
        )
        return True
    except (BotoCoreError, ClientError) as exc:
        print(f"  [ERROR] upload failed {key}: {exc}", file=sys.stderr)
        return False


def capture_one(s3, label: str, fpl_path: str, s3_key: str, dry_run: bool) -> str:
    """Fetch one endpoint and upload. Returns 'ok', 'skipped', or 'failed'."""
    if s3_key_exists(s3, s3_key) and not dry_run:
        return "skipped"
    data = fpl_get(fpl_path)
    if data is None:
        return "failed"
    return "ok" if s3_put(s3, s3_key, data, dry_run) else "failed"


def detect_season(events: list[dict]) -> str:
    # Derive from the deadline_time of the last finished GW, not GW1 —
    # GW1 may already show next season's date once the API resets.
    finished = sorted([e for e in events if e.get("finished")], key=lambda e: e["id"])
    if not finished:
        return "unknown"
    last = finished[-1]
    if last.get("deadline_time"):
        year = int(last["deadline_time"][:4])
        # GW38 deadline is typically in May — that's the end of the season
        # that started in August the previous year.
        return f"{year - 1}-{str(year)[2:]}"
    return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Capture FPL season data to S3")
    parser.add_argument("--season",  default=None, help="Season label, e.g. 2025-26")
    parser.add_argument("--dry-run", action="store_true", help="Print actions, upload nothing")
    args = parser.parse_args()

    s3 = boto3.client("s3")
    totals = {"ok": 0, "skipped": 0, "failed": 0}

    def log(result: str, label: str) -> None:
        totals[result] += 1
        if result != "skipped":
            print(result)
        elif totals["skipped"] % 50 == 0:
            print(f"  (skipped {totals['skipped']} already in S3…)")

    # ── Step 1: bootstrap-static ─────────────────────────────────────────────
    print("Fetching bootstrap-static…", end=" ", flush=True)
    bootstrap = fpl_get("bootstrap-static/")
    if bootstrap is None:
        print("Fatal: could not fetch bootstrap-static. Aborting.", file=sys.stderr)
        sys.exit(1)

    season = args.season or detect_season(bootstrap.get("events", []))
    print(f"ok\nSeason: {season}\n")

    bs_key = f"fpl/{season}/bootstrap_static.json"
    if s3_key_exists(s3, bs_key) and not args.dry_run:
        print("bootstrap_static already in S3, skipping.")
        totals["skipped"] += 1
    else:
        ok = s3_put(s3, bs_key, bootstrap, args.dry_run)
        print(f"bootstrap_static → {'ok' if ok else 'FAILED'}")
        totals["ok" if ok else "failed"] += 1

    # ── Step 2: full fixture list ─────────────────────────────────────────────
    print("\nFetching fixtures…", end=" ", flush=True)
    result = capture_one(s3, "fixtures", "fixtures/", f"fpl/{season}/fixtures.json", args.dry_run)
    print(result)
    totals[result] += 1
    time.sleep(REQUEST_DELAY)

    # ── Step 3: per-GW live data (final bonus + points) ───────────────────────
    finished_gws = sorted(
        [e["id"] for e in bootstrap.get("events", []) if e.get("finished")]
    )
    print(f"\nFetching live data for {len(finished_gws)} finished GWs…")
    for gw in finished_gws:
        key = f"fpl/{season}/live/{gw}.json"
        print(f"  GW{gw:02d} live…", end=" ", flush=True)
        result = capture_one(s3, f"live/gw{gw}", f"event/{gw}/live/", key, args.dry_run)
        log(result, f"live/{gw}")
        time.sleep(REQUEST_DELAY)

    # ── Step 4: per-GW dream team ─────────────────────────────────────────────
    print(f"\nFetching dream teams for {len(finished_gws)} GWs…")
    for gw in finished_gws:
        key = f"fpl/{season}/dream_team/{gw}.json"
        print(f"  GW{gw:02d} dream team…", end=" ", flush=True)
        result = capture_one(s3, f"dream_team/gw{gw}", f"dream-team/{gw}/", key, args.dry_run)
        log(result, f"dream_team/{gw}")
        time.sleep(REQUEST_DELAY)

    # ── Step 5: element summaries (largest step) ──────────────────────────────
    player_ids = [p["id"] for p in bootstrap.get("elements", [])]
    total = len(player_ids)
    print(f"\nFetching element summaries for {total} players…")

    for i, pid in enumerate(player_ids, 1):
        key = f"fpl/{season}/element_summary/{pid}.json"
        print(f"  [{i:3d}/{total}] player {pid}…", end=" ", flush=True)
        result = capture_one(s3, f"player {pid}", f"element-summary/{pid}/", key, args.dry_run)
        log(result, f"element_summary/{pid}")
        time.sleep(REQUEST_DELAY)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─' * 40}")
    print(f"uploaded={totals['ok']}  skipped={totals['skipped']}  failed={totals['failed']}")
    if totals["failed"]:
        print(f"Re-run to retry failed files — already-uploaded files will be skipped.")
        sys.exit(1)
    else:
        print("All done.")


if __name__ == "__main__":
    main()

"""
utils/loaders/s3_loader.py — Reads FPL archive data from S3.

Used when a historical season is requested (?season=2025-26). Data was
written to S3 by scripts/capture.py before the FPL API reset for the new
season.

S3 key layout:
    fpl/{season}/bootstrap_static.json
    fpl/{season}/element_summary/{id}.json

Mock mode (FPL_MOCK=1):
    Reads from data/ instead of S3 — same mock files used by BaseLoader.
    Allows the archive endpoints to be tested without AWS credentials.

AWS credentials:
    On EC2, attach an IAM role with s3:GetObject on the bucket.
    Locally, credentials in ~/.aws/credentials are picked up automatically
    by boto3. No credentials should ever be hardcoded here.
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _s3_get_json(bucket: str, key: str):
    """GET a JSON object from S3. Returns None on any failure."""
    try:
        import boto3

        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())
    except Exception as exc:
        print(f"[ERROR] S3 get s3://{bucket}/{key}: {exc}", file=sys.stderr)
        return None


def _mock_get_json(filename: str):
    """Read a JSON file from data/. Used when FPL_MOCK=1."""
    path = _DATA_DIR / filename
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"[ERROR] Mock file not found: {path}", file=sys.stderr)
        return None


class S3BootstrapLoader:
    """Reads bootstrap-static data from S3 for a given season.

    Provides the same interface as ElementsLoader / TeamsLoader so the
    existing preprocessors can be reused without modification.
    """

    def __init__(self, bucket: str, season: str):
        self.bucket = bucket
        self.season = season
        self._data = None  # lazily loaded, then cached in-object

    def _load(self):
        if self._data is not None:
            return self._data
        if os.getenv("FPL_MOCK"):
            self._data = _mock_get_json("bootstrap_static.json")
        else:
            self._data = _s3_get_json(self.bucket, f"fpl/{self.season}/bootstrap_static.json")
        return self._data

    def get_elements_data(self):
        data = self._load()
        if not data or "elements" not in data:
            return None
        return pd.DataFrame(data["elements"])

    def get_teams_data(self):
        data = self._load()
        if not data or "teams" not in data:
            return None
        return pd.DataFrame(data["teams"])


class S3ElementSummaryLoader:
    """Reads element-summary/{id} data from S3 for a given season.

    Provides the same interface as HistoryLoader / FixturesLoader so the
    existing preprocessors can be reused without modification.
    """

    def __init__(self, bucket: str, season: str, element_id: int):
        self.bucket = bucket
        self.season = season
        self.element_id = element_id
        self._data = None

    def _load(self):
        if self._data is not None:
            return self._data
        if os.getenv("FPL_MOCK"):
            self._data = _mock_get_json("element_summary.json")
        else:
            self._data = _s3_get_json(
                self.bucket,
                f"fpl/{self.season}/element_summary/{self.element_id}.json",
            )
        return self._data

    def get_history_data(self):
        data = self._load()
        if not data or "history" not in data:
            raise KeyError(f"'history' key missing in S3 element_summary/{self.element_id}")
        return pd.DataFrame(data["history"])

    def get_fixtures_data(self):
        """Always empty — completed seasons have no upcoming fixtures."""
        return pd.DataFrame()

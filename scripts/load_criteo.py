"""Load Criteo Attribution 1/2 dataset into an Axiom experiment.

Usage:
    python scripts/load_criteo.py --experiment-id <uuid> [--sample 50000]

The Criteo dataset must be downloaded separately:
    https://ailab.criteo.com/criteo-attribution-modeling-bidding-dataset/

Expected CSV columns (Criteo Attribution 1/2 format):
    timestamp, uid, campaign, conversion, conversion_id, attribution,
    click_pos, click_nb, time_since_last_click, cost, cpo, ...

The script maps Criteo's `attribution` field (0/1) to variant and
`conversion` (0/1) to outcome, making it a proportion experiment.

The `uid` becomes the `subject_id`. Each uid is assigned deterministically
to variant 0 (control) or variant 1 (treatment) based on whether the
Criteo `attribution` value is 0 or 1.

Extra numeric columns are uploaded as covariates and will be used by the
HTE and segment ML modules when the experiment is analyzed.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pandas as pd
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Criteo dataset into Axiom")
    parser.add_argument(
        "--experiment-id",
        required=True,
        help="UUID of the target Axiom experiment",
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the Criteo CSV file",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=50_000,
        help="Maximum rows to upload (default: 50,000)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Axiom API base URL (default: http://localhost:8000)",
    )
    return parser.parse_args()


COVARIATE_COLS = [
    "click_pos",
    "click_nb",
    "time_since_last_click",
    "cost",
    "cpo",
]


def load_and_transform(csv_path: str, sample: int) -> pd.DataFrame:
    """Read the Criteo CSV and reshape into Axiom's upload format."""
    path = Path(csv_path)
    if not path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {csv_path} …")
    df = pd.read_csv(
        csv_path,
        sep="\t",  # Criteo uses tab-separated values
        low_memory=False,
    )
    print(f"  Loaded {len(df):,} rows with columns: {list(df.columns)}")

    # Required columns check
    required = {"uid", "attribution", "conversion"}
    missing = required - set(df.columns)
    if missing:
        # Try comma-separated fallback
        df = pd.read_csv(csv_path, low_memory=False)
        missing = required - set(df.columns)
        if missing:
            print(f"ERROR: missing required columns: {sorted(missing)}", file=sys.stderr)
            print(f"  Found: {list(df.columns)}", file=sys.stderr)
            sys.exit(1)

    # Map to Axiom columns
    df = df.rename(columns={"uid": "subject_id", "attribution": "variant", "conversion": "outcome"})

    # Deduplicate: one row per subject (keep first occurrence)
    df = df.drop_duplicates(subset=["subject_id"])

    # Keep only valid variant values
    df = df[df["variant"].isin([0, 1])]

    # Ensure outcome is numeric
    df["outcome"] = pd.to_numeric(df["outcome"], errors="coerce")
    df = df.dropna(subset=["outcome"])

    # Balance classes: equal control and treatment rows
    ctrl = df[df["variant"] == 0]
    trt = df[df["variant"] == 1]
    n_each = min(len(ctrl), len(trt), sample // 2)
    df = pd.concat([ctrl.head(n_each), trt.head(n_each)], ignore_index=True)

    # Keep subject_id, variant, outcome plus any available covariate columns
    keep = ["subject_id", "variant", "outcome"]
    available_covariates = [c for c in COVARIATE_COLS if c in df.columns]
    keep += available_covariates
    df = df[keep]

    # Coerce covariate columns to numeric, drop rows where coercion fails
    for col in available_covariates:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=available_covariates)

    print(f"  Prepared {len(df):,} rows ({len(df[df.variant==0]):,} control, {len(df[df.variant==1]):,} treatment)")
    if available_covariates:
        print(f"  Covariate columns: {available_covariates}")
    return df


def upload(df: pd.DataFrame, experiment_id: str, api_url: str) -> None:
    """POST the prepared DataFrame to the Axiom upload-data endpoint."""
    url = f"{api_url}/api/v1/experiments/{experiment_id}/upload-data"
    print(f"Uploading to {url} …")

    csv_bytes = df.to_csv(index=False).encode()
    resp = requests.post(
        url,
        files={"file": ("criteo.csv", io.BytesIO(csv_bytes), "text/csv")},
        timeout=120,
    )

    if resp.status_code == 200:
        body = resp.json()
        data = body.get("data", {})
        print("Upload complete:")
        print(f"  rows_accepted : {data.get('rows_accepted'):,}")
        print(f"  rows_rejected : {data.get('rows_rejected'):,}")
        for w in data.get("warnings", []):
            print(f"  WARNING: {w}")
    else:
        print(f"ERROR: HTTP {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()
    df = load_and_transform(args.csv, args.sample)
    upload(df, args.experiment_id, args.api_url)
    print("Done.")


if __name__ == "__main__":
    main()

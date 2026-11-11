"""Pilot download of ACS 1-year PUMS person files for two states.

Pilot states: Arizona (FIPS 04, expanded Medicaid in 2014) and Texas (FIPS 48,
did not expand). The full expansion state list is still to be verified against
KFF or the CMS tracker before any analysis; the pilot is only for testing the
pipeline.

No API key is needed: PUMS files are downloaded from census.gov, not the API.

Outputs:
    data/raw/pums/{year}/csv_p{abbr}.zip      raw zip, cached and never overwritten
    data/raw/pums/MANIFEST.csv                sha256, URL, and download time per file
    data/interim/pums_person_pilot.parquet    selected columns, all pilot states and years

Run from the repository root:
    python scripts/pull_acs_pums_pilot.py
"""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/"
YEARS = range(2008, 2020)  # 2008-2019; 2020 is excluded (no standard 1-year release)
PILOT_STATES = {"AZ": "04", "TX": "48"}

RAW_DIR = Path("data/raw/pums")
INTERIM_DIR = Path("data/interim")
MANIFEST = RAW_DIR / "MANIFEST.csv"
OUTPUT = INTERIM_DIR / "pums_person_pilot.parquet"

# HICOV: health insurance coverage (1 = covered, 2 = not covered).
# POVPIP: income-to-poverty ratio, in percent (0-501).
# ST: state FIPS. AGEP: age. PWGTP and PWGTP1-80: person and replicate weights.
REQUIRED_COLUMNS = ["ST", "AGEP", "HICOV", "POVPIP", "PWGTP"]
# Replicate weights are needed for design-based standard errors. Some early years
# (2008 among them) do not include them, so their absence is recorded, not fatal.
REPLICATE_COLUMNS = [f"PWGTP{i}" for i in range(1, 81)]
KEEP_COLUMNS = REQUIRED_COLUMNS + REPLICATE_COLUMNS


def zip_url(year: int, abbr: str) -> str:
    return BASE_URL.format(year=year) + f"csv_p{abbr.lower()}.zip"


def raw_path(year: int, abbr: str) -> Path:
    return RAW_DIR / str(year) / f"csv_p{abbr.lower()}.zip"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(year: int, abbr: str) -> Path:
    """Download one state-year zip unless it is already cached."""
    dest = raw_path(year, abbr)
    if dest.exists():
        return dest

    url = zip_url(year, abbr)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[download] {url}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)

    record_manifest(dest, url)
    return dest


def record_manifest(path: Path, url: str) -> None:
    """Append one row per downloaded file so the pull can be reproduced and audited."""
    write_header = not MANIFEST.exists()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["path", "url", "sha256", "bytes", "downloaded_utc"])
        writer.writerow(
            [
                str(path),
                url,
                sha256_of(path),
                path.stat().st_size,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ]
        )


PERSON_MEMBER = re.compile(r"(psam_p|ss\d{2}p)[a-z0-9]*\.csv$", re.IGNORECASE)


def person_members(zf: zipfile.ZipFile) -> list[str]:
    """Person-file CSVs inside a zip. Naming changed across years (psam_p04.csv,
    ss08paz.csv, etc.), and some years split the file into a and b parts."""
    members = sorted(n for n in zf.namelist() if PERSON_MEMBER.search(n))
    if not members:
        raise FileNotFoundError(f"no person CSV found in {zf.filename}: {zf.namelist()}")
    return members


def read_person_file(zip_path: Path, year: int) -> pd.DataFrame:
    """Read every person part in a zip and keep the columns the design needs."""
    parts = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in person_members(zf):
            with zf.open(member) as f:
                parts.append(pd.read_csv(f, usecols=lambda c: c in KEEP_COLUMNS, dtype={"ST": str}))

    df = pd.concat(parts, ignore_index=True)
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_required:
        raise KeyError(f"{year} {zip_path.name} is missing columns: {missing_required}")

    missing_replicate = [c for c in REPLICATE_COLUMNS if c not in df.columns]
    if missing_replicate:
        print(f"[warn] {year} {zip_path.name}: no replicate weights; standard errors "
              "for this year need a different method")
        for c in missing_replicate:
            df[c] = pd.NA

    df = df[KEEP_COLUMNS].copy()

    # Some years store blank spaces in numeric fields, which makes pandas read the
    # column as text. Coerce to numbers and report how many values became missing.
    for col in ["AGEP", "HICOV", "POVPIP"] + REPLICATE_COLUMNS + ["PWGTP"]:
        before_missing = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        new_missing = int(df[col].isna().sum() - before_missing)
        if new_missing:
            print(f"[clean] {year} {col}: {new_missing} non-numeric values set to missing")

    df.insert(0, "year", year)
    df["has_replicate_weights"] = not missing_replicate
    return df


def main() -> None:
    frames = []
    for year in YEARS:
        for abbr, fips in PILOT_STATES.items():
            zip_path = download(year, abbr)
            frames.append(read_person_file(zip_path, year))
            print(f"[read] {year} {abbr}: {len(frames[-1])} person records")

    combined = pd.concat(frames, ignore_index=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(OUTPUT, index=False)
    print(f"[done] wrote {len(combined)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()

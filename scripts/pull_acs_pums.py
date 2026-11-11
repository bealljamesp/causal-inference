"""Download ACS 1-year PUMS person files for all 50 states and DC, 2008-2019.

Design choices:
- One parquet file per state-year in data/interim/pums_person/. Each file is written
  before its raw zip is deleted, so the run is resumable and never holds the full
  national file in memory.
- Raw zips are deleted after extraction (KEEP_RAW = False). MANIFEST.csv keeps the
  URL and sha256 of every download, so a deleted file can be re-downloaded and
  checked against the record.
- Years without replicate weights are kept and flagged, not dropped.
- All numeric columns are float64 so partitions from different years share one schema.
- No API key is needed: PUMS files are downloaded from census.gov.

Run from the repository root:
    python scripts/pull_acs_pums.py
"""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/"
YEARS = range(2008, 2020)  # 2008-2019; 2020 has no standard 1-year release

# 50 states and DC, as postal abbreviation -> state FIPS.
STATES = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}

RAW_DIR = Path("data/raw/pums")
PART_DIR = Path("data/interim/pums_person")
MANIFEST = RAW_DIR / "MANIFEST.csv"
FAILURES = Path("data/interim/pums_failures.csv")
KEEP_RAW = False

# HICOV: health insurance coverage (1 = covered, 2 = not covered).
# POVPIP: income-to-poverty ratio, percent. ST: state FIPS. AGEP: age.
# PWGTP and PWGTP1-80: person weight and replicate weights.
REQUIRED_COLUMNS = ["ST", "AGEP", "HICOV", "POVPIP", "PWGTP"]
REPLICATE_COLUMNS = [f"PWGTP{i}" for i in range(1, 81)]
NUMERIC_COLUMNS = ["AGEP", "HICOV", "POVPIP", "PWGTP"] + REPLICATE_COLUMNS
KEEP_COLUMNS = REQUIRED_COLUMNS + REPLICATE_COLUMNS

PERSON_MEMBER = re.compile(r"(psam_p|ss\d{2}p)[a-z0-9]*\.csv$", re.IGNORECASE)


def zip_url(year: int, abbr: str) -> str:
    return BASE_URL.format(year=year) + f"csv_p{abbr.lower()}.zip"


def raw_path(year: int, abbr: str) -> Path:
    return RAW_DIR / str(year) / f"csv_p{abbr.lower()}.zip"


def part_path(year: int, abbr: str) -> Path:
    return PART_DIR / f"{year}_{abbr}.parquet"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_manifest(path: Path, url: str) -> None:
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


def download(year: int, abbr: str) -> Path:
    dest = raw_path(year, abbr)
    if dest.exists():
        return dest
    url = zip_url(year, abbr)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    record_manifest(dest, url)
    return dest


def person_members(zf: zipfile.ZipFile) -> list[str]:
    members = sorted(n for n in zf.namelist() if PERSON_MEMBER.search(n))
    if not members:
        raise FileNotFoundError(f"no person CSV in {zf.filename}: {zf.namelist()}")
    return members


def read_person_file(zip_path: Path, year: int, abbr: str, fips: str) -> pd.DataFrame:
    parts = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in person_members(zf):
            with zf.open(member) as f:
                parts.append(
                    pd.read_csv(f, usecols=lambda c: c in KEEP_COLUMNS, dtype={"ST": str})
                )
    df = pd.concat(parts, ignore_index=True)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"{year} {abbr}: missing required columns {missing}")

    # Guard against a mislabeled file: every row should belong to this state.
    st_values = set(pd.to_numeric(df["ST"], errors="coerce").dropna().astype(int))
    if st_values != {int(fips)}:
        raise ValueError(f"{year} {abbr}: ST values {sorted(st_values)} != {fips}")

    replicate_missing = [c for c in REPLICATE_COLUMNS if c not in df.columns]
    for c in replicate_missing:
        df[c] = np.nan

    for c in NUMERIC_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")

    df = df[KEEP_COLUMNS].copy()
    df.insert(0, "state", abbr)
    df.insert(0, "year", np.int16(year))
    df["has_replicate_weights"] = not replicate_missing
    return df


def process_state_year(year: int, abbr: str, fips: str) -> str:
    part = part_path(year, abbr)
    if part.exists():
        return "skipped"

    zip_path = download(year, abbr)
    df = read_person_file(zip_path, year, abbr, fips)

    part.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(part, index=False)

    if not KEEP_RAW:
        zip_path.unlink()
    return f"{len(df)} rows"


def main() -> None:
    failures = []
    total = len(YEARS) * len(STATES)
    done = 0
    for year in YEARS:
        for abbr, fips in STATES.items():
            done += 1
            try:
                status = process_state_year(year, abbr, fips)
                print(f"[{done}/{total}] {year} {abbr}: {status}", flush=True)
            except Exception as exc:  # keep going; report all failures at the end
                failures.append((year, abbr, repr(exc)))
                print(f"[{done}/{total}] {year} {abbr}: FAILED {exc!r}", flush=True)

    if failures:
        FAILURES.parent.mkdir(parents=True, exist_ok=True)
        with FAILURES.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["year", "state", "error"])
            writer.writerows(failures)
        print(f"[done] {len(failures)} failures written to {FAILURES}")
    else:
        print(f"[done] all {total} state-years written to {PART_DIR}")


if __name__ == "__main__":
    main()

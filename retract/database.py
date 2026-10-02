"""Load and validate the Retraction Watch snapshot."""

import csv
import hashlib
import io
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .model import Citation, Notice, extract_year, normalize_doi

DATABASE_URL = (
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
)
NATURES = {"Retraction", "Correction", "Expression of concern", "Reinstatement"}
REQUIRED = {
    "Record ID",
    "Title",
    "Author",
    "Journal",
    "OriginalPaperDate",
    "OriginalPaperDOI",
    "RetractionNature",
    "RetractionDate",
}


def session():
    client = requests.Session()
    client.headers["User-Agent"] = (
        "recite-retract/3 (https://github.com/recite/retract)"
    )
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"GET"},
        respect_retry_after_header=True,
    )
    client.mount("https://", HTTPAdapter(max_retries=retry))
    return client


def load_database(path: Path | None = None):
    if path is None:
        with session() as client:
            response = client.get(DATABASE_URL, timeout=(10, 60))
            response.raise_for_status()
            data = response.content
    else:
        data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if not REQUIRED.issubset(reader.fieldnames or []):
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        raise ValueError(f"Database is missing columns: {missing}")
    notices, seen = [], set()
    for i, row in enumerate(reader, 2):
        if None in row or any(row[k] is None for k in REQUIRED):
            raise ValueError(f"Malformed database row {i}")
        nature = row["RetractionNature"].strip()
        record_id = row["Record ID"].strip()
        if nature not in NATURES or not record_id or record_id in seen:
            raise ValueError(
                f"Unknown notice type or missing/duplicate record ID at row {i}"
            )
        seen.add(record_id)
        notices.append(
            Notice(
                record_id,
                Citation(
                    "Retraction Watch",
                    record_id,
                    row["Title"],
                    row["Author"],
                    row["Journal"],
                    extract_year(row["OriginalPaperDate"]),
                    normalize_doi(row["OriginalPaperDOI"]),
                ),
                nature,
                row["RetractionDate"],
                normalize_doi(row.get("RetractionDOI", "")),
                row.get("URLS", ""),
            )
        )
    if not notices:
        raise ValueError("The database contains no records")
    return notices, {
        "url": DATABASE_URL,
        "sha256": hashlib.sha256(data).hexdigest(),
        "records": len(notices),
    }

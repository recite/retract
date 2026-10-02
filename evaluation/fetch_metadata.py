"""Acquire public metadata in bounded, resumable Crossref batches."""

import argparse
import json
import random
import time
from pathlib import Path

from retract.database import load_database, session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    notices, _ = load_database(args.database)
    dois = sorted(
        {
            n.citation.doi
            for n in notices
            if n.citation.doi and "," not in n.citation.doi
        }
    )
    random.Random(20261001).shuffle(dois)
    chosen = dois[:2000]
    selection = args.cache / "selection.json"
    if selection.exists() and json.loads(selection.read_text()) != chosen:
        raise ValueError("Cache belongs to a different DOI selection")
    selection.write_text(json.dumps(chosen))
    select = "DOI,title,author,container-title,published"
    with session() as client:
        for i in range(0, len(chosen), 40):
            output = args.cache / f"positive-{i // 40:03}.json"
            if output.exists():
                continue
            response = client.get(
                "https://api.crossref.org/works",
                params={
                    "filter": ",".join("doi:" + doi for doi in chosen[i : i + 40]),
                    "rows": 40,
                    "select": select,
                },
                timeout=(10, 60),
            )
            response.raise_for_status()
            output.write_text(json.dumps(response.json()["message"]["items"]))
            time.sleep(0.3)
        for i in range(10):
            output = args.cache / f"negative-{i:03}.json"
            if output.exists():
                continue
            response = client.get(
                "https://api.crossref.org/works",
                params={
                    "sample": 100,
                    "filter": "type:journal-article",
                    "select": select,
                },
                timeout=(10, 60),
            )
            response.raise_for_status()
            output.write_text(json.dumps(response.json()["message"]["items"]))
            time.sleep(0.3)


if __name__ == "__main__":
    main()

"""Build a DOI-labelled Crossref and Retraction Watch corpus."""

import argparse
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from retract.database import load_database
from retract.model import Citation, normalize_doi


def split_for(doi):
    bucket = int(hashlib.sha256(doi.encode()).hexdigest()[:8], 16) % 10
    return "train" if bucket < 4 else "validation" if bucket < 7 else "test"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--crossref-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/data"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    notices, provenance = load_database(args.database)
    targets = {n.citation.doi for n in notices if n.citation.doi}
    queries = {}
    for file in sorted(args.crossref_cache.glob("*.json")):
        if file.name == "selection.json":
            continue
        for item in json.loads(file.read_text()):
            doi = normalize_doi(item.get("DOI", ""))
            if not doi or not item.get("title"):
                continue
            authors = "; ".join(
                ", ".join(filter(None, [a.get("family"), a.get("given")]))
                for a in item.get("author", [])
            )
            dates = item.get("published", {}).get("date-parts", [[]])[0]
            citation = Citation(
                "Crossref",
                doi,
                item["title"][0],
                authors,
                (item.get("container-title") or [""])[0],
                str(dates[0]) if dates else "",
                "",
            )
            queries[doi] = {
                "doi_label": doi,
                "in_database": doi in targets,
                "split": split_for(doi),
                "citation": asdict(citation),
            }
    for name, records in [
        ("queries", [queries[k] for k in sorted(queries)]),
        ("notices", [asdict(n) for n in notices]),
    ]:
        data = "".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records
        ).encode()
        (args.output / f"{name}.jsonl.gz").write_bytes(gzip.compress(data, mtime=0))
    provenance.update(
        {
            "queries": len(queries),
            "label": "normalized DOI equality",
            "crossref": "https://api.crossref.org/works",
            "split": "sha256(DOI), 40% train / 30% validation / 30% test",
            "sampling": "2000 seeded DOI selections from Retraction Watch; "
            "1000 Crossref random journal articles",
            "seed": 20261001,
        }
    )
    (args.output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()

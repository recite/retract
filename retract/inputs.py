"""Read citation files without losing parser failures or source locations."""

import json
from pathlib import Path

import bibtexparser

from .model import Citation, extract_year, normalize_doi

DEFAULT_EXCLUDES = {".git", ".venv", "venv", "node_modules", "renv", "build", "dist"}


def read_bib(path: Path, source: str):
    library = bibtexparser.parse_string(path.read_text(encoding="utf-8-sig"))
    errors = [
        f"{source}:{block.start_line + 1}: {type(block).__name__}: "
        f"{block.error or 'malformed bibliography block'}"
        for block in library.failed_blocks
    ]
    citations = []
    for entry in library.entries:
        fields = {field.key.casefold(): field.value for field in entry.fields}
        raw_doi = fields.get("doi", "")
        doi = normalize_doi(raw_doi or fields.get("url", ""))
        if raw_doi and not doi:
            errors.append(f"{source}:{entry.key}: invalid DOI {raw_doi!r}")
        citations.append(
            Citation(
                source,
                entry.key,
                fields.get("title", ""),
                fields.get("author", ""),
                fields.get("journal", fields.get("journaltitle", "")),
                extract_year(fields.get("year", fields.get("date", ""))),
                doi,
            )
        )
    return citations, errors


def read_csl(path: Path, source: str):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("CSL-JSON must be an array of citation objects")
    citations, errors = [], []
    for i, entry in enumerate(data):
        try:
            if not isinstance(entry, dict):
                raise ValueError("citation must be an object")
            authors = "; ".join(
                a.get("literal")
                or ", ".join(filter(None, [a.get("family"), a.get("given")]))
                for a in entry.get("author", [])
            )
            date = entry.get("issued", {}).get("date-parts", [[]])[0]
            raw_doi = entry.get("DOI", "")
            if raw_doi and not normalize_doi(raw_doi):
                errors.append(f"{source}:{i + 1}: invalid DOI {raw_doi!r}")
            citations.append(
                Citation(
                    source,
                    str(entry.get("id", i + 1)),
                    entry.get("title", ""),
                    authors,
                    entry.get("container-title", ""),
                    extract_year(str(date[0])) if date else "",
                    normalize_doi(raw_doi or entry.get("URL", "")),
                )
            )
        except (TypeError, AttributeError, IndexError, ValueError) as exc:
            errors.append(f"{source}:{i + 1}: invalid CSL entry: {exc}")
    return citations, errors


def read_citations(root: Path, patterns: list[str], excludes: list[str]):
    if not root.is_dir():
        raise ValueError(f"Scan root is not a directory: {root}")
    files = set()
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError("Input patterns must stay inside the scan root")
        files.update(p for p in root.glob(pattern) if p.is_file())
    citations, errors, scanned = [], [], []
    for path in sorted(files):
        relative = path.relative_to(root)
        if DEFAULT_EXCLUDES.intersection(relative.parts) or any(
            relative.match(e) for e in excludes
        ):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            errors.append(f"{relative}: symlink or path outside scan root")
            continue
        scanned.append(relative.as_posix())
        try:
            reader = (
                read_bib if path.suffix.casefold() in {".bib", ".bibtex"} else read_csl
            )
            entries, failures = reader(path, relative.as_posix())
            citations.extend(entries)
            errors.extend(failures)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            errors.append(f"{relative}: {exc}")
    return citations, errors, scanned

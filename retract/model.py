"""Shared records for file importers, the notice database, and matching."""

import html
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import unquote

from pylatexenc.latex2text import LatexNodes2Text


@lru_cache(maxsize=200000)
def normalize_text(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    if "\\" in value or "{" in value:
        value = LatexNodes2Text().latex_to_text(value)
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", value).replace("_", " ").split())


def normalize_doi(value: str) -> str:
    value = html.unescape(value).strip().strip("{}")
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
    value = unquote(value).replace("\\_", "_").casefold()
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


def extract_year(value: str) -> str:
    match = re.search(r"\b([12]\d{3})\b", value)
    return match.group(1) if match else ""


@dataclass(frozen=True)
class Citation:
    source: str
    key: str
    title: str = ""
    authors: str = ""
    journal: str = ""
    year: str = ""
    doi: str = ""

    @property
    def metadata_usable(self):
        return bool(
            len(normalize_text(self.title)) >= 12
            and self.year
            and (normalize_text(self.authors) or normalize_text(self.journal))
        )


@dataclass(frozen=True)
class Notice:
    record_id: str
    citation: Citation
    nature: str
    date: str
    notice_doi: str = ""
    url: str = ""


@dataclass(frozen=True)
class Finding:
    citation: Citation
    notice: Notice
    method: str
    title_score: float
    status: str

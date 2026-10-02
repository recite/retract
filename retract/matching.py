"""Retrieve title candidates and report uncalibrated match evidence."""

import re
from collections import defaultdict
from datetime import datetime

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer

from .model import Finding, normalize_text


def title_text(value):
    value = re.sub(
        r"^(?:retracted(?: article)?|retraction(?: note)?|withdrawn|correction|"
        r"expression of concern)\s*[:\-–]\s*",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(r"\[(?:retracted|withdrawn)\]", "", value, flags=re.I)
    return normalize_text(value)


def author_tokens(value):
    return set(normalize_text(value).split()) - {"and", "et", "al"}


def supporting_evidence(left, right):
    la, ra = author_tokens(left.authors), author_tokens(right.authors)
    author = len(la & ra) / min(len(la), len(ra)) if la and ra else 0.0
    lj, rj = normalize_text(left.journal), normalize_text(right.journal)
    journal = fuzz.ratio(lj, rj) / 100 if lj and rj else 0.0
    year = abs(int(left.year) - int(right.year)) if left.year and right.year else None
    return author, journal, year


class Matcher:
    def __init__(self, notices):
        self.notices = notices
        self.by_doi = defaultdict(list)
        self.groups = defaultdict(list)
        for notice in notices:
            if notice.citation.doi:
                self.by_doi[notice.citation.doi].append(notice)
            identity = notice.citation.doi or "record:" + notice.record_id
            self.groups[(identity, title_text(notice.citation.title))].append(notice)
        self.keys = [key for key in self.groups if key[1]]
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            dtype=np.float32,
            max_features=200000,
            sublinear_tf=True,
        )
        self.matrix = (
            self.vectorizer.fit_transform([key[1] for key in self.keys])
            if self.keys
            else None
        )

    def candidates(self, citation, limit=10):
        title = title_text(citation.title)
        if not title or self.matrix is None:
            return []
        query = self.vectorizer.transform([title])
        scores = (self.matrix @ query.T).toarray().ravel()
        indices = np.flatnonzero(scores > 0)
        if len(indices) > limit:
            cutoff = np.partition(scores[indices], -limit)[-limit]
            indices = indices[scores[indices] >= cutoff]
        indices = sorted(indices, key=lambda i: (-float(scores[i]), self.keys[i]))[
            :limit
        ]
        candidates = []
        for i in indices:
            notice = self.groups[self.keys[i]][0]
            author, journal, year = supporting_evidence(citation, notice.citation)
            candidates.append(
                {
                    "notice": notice,
                    "notices": self.groups[self.keys[i]],
                    "cosine": float(scores[i]),
                    "ratio": fuzz.ratio(title, self.keys[i][1]) / 100,
                    "exact": title == self.keys[i][1],
                    "author": author,
                    "journal": journal,
                    "year_gap": year,
                }
            )
        return candidates

    def match(self, citation, policy):
        if citation.doi in self.by_doi:
            matches = self.by_doi[citation.doi]
            return [
                Finding(citation, n, "doi", 1.0, notice_status(n, matches))
                for n in matches
            ]
        if not citation.metadata_usable:
            return []
        candidates = self.candidates(citation)
        candidates = [
            c
            for c in candidates
            if not (
                citation.doi
                and c["notice"].citation.doi
                and citation.doi != c["notice"].citation.doi
            )
        ]
        selected = select_candidate(candidates, policy)
        if selected is None:
            return []
        matches = (
            self.by_doi[selected["notice"].citation.doi]
            if selected["notice"].citation.doi
            else selected["notices"]
        )
        return [
            Finding(
                citation,
                n,
                "metadata",
                round(selected[policy["method"]], 6),
                "possible",
            )
            for n in matches
        ]


def select_candidate(candidates, policy):
    method = policy["method"]
    eligible = [
        c
        for c in candidates
        if c["year_gap"] is not None
        and c["year_gap"] <= policy["year_gap"]
        and (c["author"] >= policy["author"] or c["journal"] >= policy["journal"])
    ]
    eligible.sort(key=lambda c: (-float(c[method]), c["notice"].record_id))
    if not eligible or eligible[0][method] < policy["threshold"]:
        return None
    best = eligible[0]
    identity = best["notice"].citation.doi or best["notice"].record_id
    others = [
        c
        for c in eligible[1:]
        if (c["notice"].citation.doi or c["notice"].record_id) != identity
    ]
    if others and best[method] - others[0][method] < policy["margin"]:
        return None
    return best


def notice_status(notice, related):
    if notice.nature != "Retraction":
        return "other_notice"
    reinstatements = [n for n in related if n.nature == "Reinstatement"]
    if not reinstatements:
        return "confirmed_retraction"
    try:
        retraction_date = datetime.strptime(notice.date.split()[0], "%m/%d/%Y")
        dates = [
            datetime.strptime(n.date.split()[0], "%m/%d/%Y") for n in reinstatements
        ]
    except (ValueError, IndexError):
        return "status_uncertain"
    return "reinstated" if max(dates) >= retraction_date else "confirmed_retraction"

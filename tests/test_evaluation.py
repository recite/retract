import json
from dataclasses import replace
from pathlib import Path

from evaluation.benchmark import choose, load_lines, metrics
from evaluation.build_dataset import split_for
from retract.matching import select_candidate
from retract.model import Citation, Notice

ROOT = Path(__file__).parents[1]


def test_doi_groups_are_disjoint_and_masked():
    queries = load_lines(ROOT / "evaluation/data/queries.jsonl.gz")
    assert len({q["doi_label"] for q in queries}) == len(queries)
    assert all(q["split"] == split_for(q["doi_label"]) for q in queries)
    assert all(not q["citation"]["doi"] for q in queries)


def test_production_decisions_match_frozen_heldout_evaluation():
    policy = json.loads((ROOT / "retract/policy.json").read_text())
    rows = load_lines(ROOT / "evaluation/results.predictions.jsonl.gz")
    test = [r for r in rows if r["split"] == "test"]
    expected = json.loads((ROOT / "evaluation/results.json").read_text())["test"]
    assert metrics(test, policy) == expected
    for row in test:
        candidates = []
        for candidate in row["candidates"]:
            notice = Notice(
                candidate["identity"],
                Citation("fixture", "x", doi=candidate["identity"]),
                "Retraction",
                "1/1/2020",
            )
            candidates.append({**candidate, "notice": notice})
        result = select_candidate(candidates, policy) if row["usable"] else None
        assert (result["notice"].citation.doi if result else None) == (
            choose(row["candidates"], policy) if row["usable"] else None
        )


def test_labels_and_source_keys_do_not_change_candidate_features():
    from retract.matching import Matcher

    citation = Citation(
        "x",
        "10.1234/leaked-label",
        "A very specific scientific title",
        "Smith",
        "Journal",
        "2020",
    )
    notice = Notice("1", citation, "Retraction", "1/1/2024")
    index = Matcher([notice])
    assert index.candidates(citation) == index.candidates(
        replace(citation, key="hidden", doi="10.1234/hidden")
    )

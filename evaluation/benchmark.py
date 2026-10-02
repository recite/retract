"""Tune on train/validation DOI groups, then evaluate the frozen choice once on test."""

import argparse
import gzip
import hashlib
import itertools
import json
import time
from pathlib import Path

from retract.matching import Matcher
from retract.model import Citation, Notice


def load_lines(path):
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle]


def choose(candidates, policy):
    eligible = [
        c
        for c in candidates
        if c["year_gap"] is not None
        and c["year_gap"] <= policy["year_gap"]
        and (c["author"] >= policy["author"] or c["journal"] >= policy["journal"])
    ]
    eligible.sort(key=lambda c: (-float(c[policy["method"]]), c["identity"]))
    if not eligible or eligible[0][policy["method"]] < policy["threshold"]:
        return None
    best = eligible[0]
    other = next((c for c in eligible[1:] if c["identity"] != best["identity"]), None)
    if other and best[policy["method"]] - other[policy["method"]] < policy["margin"]:
        return None
    return best["identity"]


def metrics(rows, policy):
    tp = fp = fn = tn = 0
    for row in rows:
        predicted = choose(row["candidates"], policy) if row["usable"] else None
        positive = row["in_database"]
        correct = predicted == row["doi_label"]
        tp += int(positive and correct)
        fp += int(predicted is not None and not correct)
        fn += int(positive and not correct)
        tn += int(not positive and predicted is None)
    return {
        "queries": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("evaluation/data"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results.json"))
    parser.add_argument(
        "--policy-output", type=Path, default=Path("retract/policy.json")
    )
    args = parser.parse_args()
    queries = load_lines(args.data / "queries.jsonl.gz")
    notices = [
        Notice(**{**r, "citation": Citation(**r["citation"])})
        for r in load_lines(args.data / "notices.jsonl.gz")
    ]
    start = time.perf_counter()
    index = Matcher(notices)
    rows = []
    for i, row in enumerate(queries):
        citation = Citation(**row["citation"])
        assert not citation.doi
        candidates = index.candidates(citation)
        features = []
        for candidate in candidates:
            features.append(
                {k: v for k, v in candidate.items() if k not in {"notice", "notices"}}
            )
            features[-1]["identity"] = (
                candidate["notice"].citation.doi or candidate["notice"].record_id
            )
        rows.append(
            {
                **{k: v for k, v in row.items() if k != "citation"},
                "usable": citation.metadata_usable,
                "candidates": features,
            }
        )
        if i % 250 == 0:
            print(f"Candidates {i}/{len(queries)}", flush=True)
    partitions = {
        name: [r for r in rows if r["split"] == name]
        for name in ["train", "validation", "test"]
    }
    comparisons = {}
    for method in ["exact", "ratio", "cosine"]:
        thresholds = [1.0] if method == "exact" else [0.85, 0.9, 0.93, 0.95, 0.97, 0.99]
        configurations = []
        for threshold, margin, year_gap, author, journal in itertools.product(
            thresholds, [0.02, 0.05, 0.1], [0, 1], [0.5, 0.75], [0.9, 0.97]
        ):
            policy = dict(
                method=method,
                threshold=threshold,
                margin=margin,
                year_gap=year_gap,
                author=author,
                journal=journal,
            )
            training = metrics(partitions["train"], policy)
            if training["fp"] == 0 and training["tp"]:
                configurations.append((policy, training))
        configurations.sort(
            key=lambda x: (-x[1]["tp"], -x[0]["threshold"], -x[0]["margin"])
        )
        viable = []
        for policy, training in configurations:
            validation = metrics(partitions["validation"], policy)
            if validation["fp"] == 0:
                viable.append((policy, training, validation))
        if viable:
            viable.sort(
                key=lambda x: (
                    -x[2]["tp"],
                    -x[1]["tp"],
                    -x[0]["threshold"],
                    -x[0]["margin"],
                )
            )
            policy, training, validation = viable[0]
            comparisons[method] = {
                "policy": policy,
                "train": training,
                "validation": validation,
            }
    if not comparisons:
        raise SystemExit("No policy met the zero-false-link development criterion")
    chosen = max(
        comparisons, key=lambda method: comparisons[method]["validation"]["tp"]
    )
    policy = comparisons[chosen]["policy"]
    result = {
        "selected": chosen,
        "development": comparisons,
        "test": metrics(partitions["test"], policy),
        "retrieval_recall_at_10": sum(
            any(c["identity"] == r["doi_label"] for c in r["candidates"])
            for r in rows
            if r["in_database"]
        )
        / sum(r["in_database"] for r in rows),
        "seconds": time.perf_counter() - start,
        "query_sha256": hashlib.sha256(
            (args.data / "queries.jsonl.gz").read_bytes()
        ).hexdigest(),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.policy_output.write_text(json.dumps(policy, indent=2) + "\n")
    args.output.with_suffix(".predictions.jsonl.gz").write_bytes(
        gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode(), mtime=0)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Command-line and GitHub Action entry point."""

import argparse
import json
import os
import sys
from importlib.resources import files
from pathlib import Path

from .database import load_database
from .inputs import read_citations
from .matching import Matcher
from .reporting import badge, make_report, summary, sync_issue


def boolean(value):
    if value.casefold() not in {"true", "false"}:
        raise argparse.ArgumentTypeError("Expected true or false")
    return value.casefold() == "true"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check bibliography citations against Retraction Watch."
    )
    parser.add_argument(
        "--scan-root", type=Path, default=Path(os.getenv("GITHUB_WORKSPACE", "."))
    )
    parser.add_argument("--paths", default="**/*.bib\n**/*.bibtex\n**/*.csl.json")
    parser.add_argument("--exclude", default="")
    parser.add_argument("--database", type=Path)
    parser.add_argument("--report", type=Path, default=Path("retraction-report.json"))
    parser.add_argument("--badge", type=Path)
    parser.add_argument("--create-issue", type=boolean, default=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-retraction", type=boolean, default=False)
    args = parser.parse_args(argv)
    errors, citations, scanned, findings, database = [], [], [], [], None
    try:
        citations, errors, scanned = read_citations(
            args.scan_root, args.paths.splitlines(), args.exclude.splitlines()
        )
        if citations:
            notices, database = load_database(args.database)
            index = Matcher(notices)
            policy = json.loads(files("retract").joinpath("policy.json").read_text())
            for citation in citations:
                findings.extend(index.match(citation, policy))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    report = make_report(citations, findings, errors, scanned, database)
    notification_failed = False
    if args.create_issue and not args.dry_run:
        try:
            report["issue_action"] = sync_issue(
                report,
                os.getenv("GITHUB_REPOSITORY", ""),
                os.getenv("GITHUB_TOKEN", ""),
            )
        except Exception as exc:
            report["notification_error"] = str(exc)
            notification_failed = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if args.badge:
        args.badge.parent.mkdir(parents=True, exist_ok=True)
        args.badge.write_text(json.dumps(badge(report), indent=2) + "\n")
    rendered = summary(report)
    print(rendered)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as handle:
            handle.write(rendered)
    confirmed = sum(f["status"] == "confirmed_retraction" for f in report["findings"])
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
            handle.write(f"status={report['status']}\nconfirmed-count={confirmed}\n")
    if report["status"] in {"incomplete", "no_input"} or notification_failed:
        return 2
    return 1 if args.fail_on_retraction and confirmed else 0


if __name__ == "__main__":
    sys.exit(main())

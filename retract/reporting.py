"""Structured results, safe Markdown, and idempotent issue synchronization."""

import hashlib
import html
import json
import re
from dataclasses import asdict
from urllib.parse import quote

from .database import session

MARKER = "<!-- recite-retract:v3 -->"
ISSUE_TITLE = "Bibliography notices requiring review"


def make_report(citations, findings, errors, files, database):
    uncheckable = [asdict(c) for c in citations if not c.doi and not c.metadata_usable]
    status = "findings" if findings else "no_matches"
    if errors or uncheckable:
        status = "incomplete"
    elif not citations:
        status = "no_input"
    records = sorted(
        (asdict(f) for f in findings),
        key=lambda f: (
            f["citation"]["source"],
            f["citation"]["key"],
            f["notice"]["record_id"],
            f["method"],
        ),
    )
    return {
        "schema_version": 1,
        "status": status,
        "database": database,
        "coverage": {
            "files": files,
            "citations": len(citations),
            "with_doi": sum(bool(c.doi) for c in citations),
            "metadata_usable": sum(c.metadata_usable for c in citations),
            "uncheckable": uncheckable,
        },
        "findings": records,
        "errors": sorted(errors),
    }


def safe_text(value):
    value = html.escape(str(value)).replace("\n", " ").replace("\r", " ")
    value = re.sub(r"([\\`*_\[\]{}|])", r"\\\1", value)
    return value.replace("@", "&#64;")


def summary(report):
    coverage = report["coverage"]
    lines = [
        "## Bibliography check",
        "",
        f"Result: **{report['status'].replace('_', ' ')}**.",
        "",
        f"Read {coverage['citations']} citations in {len(coverage['files'])} files; "
        f"{coverage['with_doi']} have valid DOIs and "
        f"{len(coverage['uncheckable'])} lack enough identifying metadata.",
        "",
        "Metadata matches are candidates for human review. No matches does not "
        "establish that a work has never been retracted.",
    ]
    for finding in report["findings"]:
        c, notice = finding["citation"], finding["notice"]
        lines.extend(
            [
                "",
                f"- **{safe_text(notice['nature'])}**; "
                f"{safe_text(finding['status'])}; match: {finding['method']}.",
                f"  {safe_text(c['source'])} — {safe_text(c['key'])}: "
                f"{safe_text(c['title'])}",
                f"  Database record {safe_text(notice['record_id'])}, "
                f"notice date {safe_text(notice['date'])}.",
            ]
        )
        doi = notice["notice_doi"] or notice["citation"]["doi"]
        if doi:
            lines.append(f"  [Notice/source](https://doi.org/{quote(doi, safe='/')})")
        elif notice["url"]:
            url = notice["url"].split(";")[0].strip()
            if url.startswith("https://"):
                lines.append(f"  [Source]({quote(url, safe=':/?=&%')})")
    if report["errors"]:
        lines.extend(
            ["", "### Scan errors"] + [f"- {safe_text(e)}" for e in report["errors"]]
        )
    if report.get("notification_error"):
        lines.extend(
            [
                "",
                "Issue synchronization failed: "
                + safe_text(report["notification_error"]),
            ]
        )
    return "\n".join(lines) + "\n"


def badge(report):
    status = report["status"]
    return {
        "schemaVersion": 1,
        "label": "bibliography check",
        "message": status.replace("_", " "),
        "color": {
            "no_matches": "brightgreen",
            "findings": "orange",
            "incomplete": "yellow",
            "no_input": "lightgrey",
        }[status],
    }


def sync_issue(report, repository, token):
    if not token or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Issue synchronization requires a token and owner/repository")
    if report["status"] in {"incomplete", "no_input"}:
        return "skipped_incomplete"
    fingerprint = hashlib.sha256(
        json.dumps(report["findings"], sort_keys=True).encode()
    ).hexdigest()
    stamp = f"<!-- result-sha256:{fingerprint} -->"
    body = f"{MARKER}\n{stamp}\n{summary(report)}"
    if len(body) > 60000:
        raise ValueError(
            "Issue report exceeds 60,000 characters; use the JSON artifact"
        )
    url = f"https://api.github.com/repos/{repository}/issues"
    with session() as client:
        client.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )
        existing = None
        page = 1
        while True:
            response = client.get(
                url,
                params={"state": "all", "per_page": 100, "page": page},
                timeout=(10, 30),
            )
            response.raise_for_status()
            issues = response.json()
            for issue in issues:
                if "pull_request" not in issue and MARKER in (issue.get("body") or ""):
                    existing = issue
                    break
            if existing or len(issues) < 100:
                break
            page += 1
        if not report["findings"]:
            if existing and existing["state"] == "open":
                response = client.patch(
                    f"{url}/{existing['number']}",
                    json={"state": "closed", "body": body},
                    timeout=(10, 30),
                )
                response.raise_for_status()
                return "closed"
            return "unchanged"
        if existing:
            if stamp in (existing.get("body") or ""):
                return "unchanged" if existing["state"] == "open" else "dismissed"
            response = client.patch(
                f"{url}/{existing['number']}",
                json={"body": body, "state": "open"},
                timeout=(10, 30),
            )
            response.raise_for_status()
            return "updated"
        response = client.post(
            url, json={"title": ISSUE_TITLE, "body": body}, timeout=(10, 30)
        )
        response.raise_for_status()
        return "created"

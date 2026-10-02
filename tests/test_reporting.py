import hashlib
import json
from unittest.mock import MagicMock

import pytest

from retract.model import Citation, Finding, Notice
from retract.reporting import MARKER, make_report, safe_text, sync_issue


@pytest.fixture
def report():
    c = Citation(
        "references.bib",
        "smith",
        "A long real title",
        "Smith",
        "Journal",
        "2020",
        "10.1234/example",
    )
    n = Notice("1", c, "Retraction", "1/1/2024")
    return make_report(
        [c],
        [Finding(c, n, "doi", 1.0, "confirmed_retraction")],
        [],
        ["references.bib"],
        {},
    )


@pytest.fixture
def client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("retract.reporting.session", lambda: client)
    client.__enter__.return_value = client
    client.get.return_value.json.return_value = []
    return client


def managed_issue(report, state="open"):
    fingerprint = hashlib.sha256(
        json.dumps(report["findings"], sort_keys=True).encode()
    ).hexdigest()
    return {
        "number": 1,
        "state": state,
        "body": MARKER + f"\n<!-- result-sha256:{fingerprint} -->",
    }


def test_create(report, client):
    assert sync_issue(report, "owner/repo", "test") == "created"
    client.post.assert_called_once()


@pytest.mark.parametrize(
    "state,expected", [("open", "unchanged"), ("closed", "dismissed")]
)
def test_unchanged_issue_and_dismissal(report, client, state, expected):
    client.get.return_value.json.return_value = [managed_issue(report, state)]
    assert sync_issue(report, "owner/repo", "test") == expected
    client.patch.assert_not_called()
    client.post.assert_not_called()


def test_new_findings_reopen(report, client):
    client.get.return_value.json.return_value = [
        {"number": 1, "state": "closed", "body": MARKER}
    ]
    assert sync_issue(report, "owner/repo", "test") == "updated"
    assert client.patch.call_args.kwargs["json"]["state"] == "open"


def test_complete_clean_scan_closes(report, client):
    client.get.return_value.json.return_value = [managed_issue(report)]
    report["findings"] = []
    report["status"] = "no_matches"
    assert sync_issue(report, "owner/repo", "test") == "closed"


def test_incomplete_scan_does_not_close(report, client):
    report["status"] = "incomplete"
    assert sync_issue(report, "owner/repo", "test") == "skipped_incomplete"
    client.get.assert_not_called()


def test_pull_requests_are_not_issues(report, client):
    item = managed_issue(report)
    item["pull_request"] = {}
    client.get.return_value.json.return_value = [item]
    assert sync_issue(report, "owner/repo", "test") == "created"


def test_escaping():
    escaped = safe_text("@all <script> [bad](url)\nheading")
    assert "@all" not in escaped and "<script>" not in escaped
    assert "\n" not in escaped and r"\[bad\]" in escaped

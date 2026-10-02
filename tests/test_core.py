import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

import pytest

from retract.cli import main
from retract.database import load_database
from retract.inputs import read_bib, read_citations, read_csl
from retract.matching import Matcher, notice_status, title_text
from retract.model import Citation, normalize_doi, normalize_text
from retract.reporting import make_report

FIXTURES = Path(__file__).parent / "fixtures"
POLICY = json.loads(files("retract").joinpath("policy.json").read_text())


@pytest.fixture
def notices():
    return load_database(FIXTURES / "notices.csv")[0]


@pytest.mark.parametrize(
    "value",
    [
        "10.1234/ABC",
        "https://doi.org/10.1234/ABC",
        "http://dx.doi.org/10.1234/ABC",
        "doi: 10.1234/ABC",
    ],
)
def test_doi_normalization(value):
    assert normalize_doi(value) == "10.1234/abc"


@pytest.mark.parametrize("value", ["unavailable", "", "garbage", "10.1234/a b"])
def test_invalid_doi(value):
    assert not normalize_doi(value)


def test_unicode_and_latex():
    assert normalize_text("政治知識") != normalize_text("経済成長")
    assert normalize_text(r"{M\"uller}") == "muller"
    assert (
        title_text("Correction of biased measurements")
        == "correction of biased measurements"
    )
    assert title_text("RETRACTED: An actual title") == "an actual title"


def test_bibtex_macros_and_biblatex(tmp_path):
    path = tmp_path / "refs.bib"
    path.write_text(
        '@string{test="A Journal"}\n@online{x,title={A real long title},'
        "author={Smith},date={2020-04-01},journaltitle=test,month=July,address=chicago}"
    )
    citations, errors = read_bib(path, "refs.bib")
    assert not errors
    assert citations[0].year == "2020"
    assert citations[0].journal == "A Journal"


def test_malformed_entry_is_reported(tmp_path):
    path = tmp_path / "bad.bib"
    path.write_text("@article{broken,title={Unclosed")
    citations, errors = read_bib(path, "bad.bib")
    assert not citations
    assert errors and "bad.bib:1" in errors[0]


def test_duplicate_key_is_reported(tmp_path):
    path = tmp_path / "refs.bib"
    path.write_text("@article{x,title={one}}\n@article{x,title={two}}")
    _, errors = read_bib(path, "refs.bib")
    assert errors


def test_csl_json(tmp_path):
    path = tmp_path / "refs.csl.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "x",
                    "title": "An article",
                    "DOI": "10.1234/ABC",
                    "author": [{"family": "Smith", "given": "Jane"}],
                    "issued": {"date-parts": [[2020]]},
                }
            ]
        )
    )
    citations, errors = read_csl(path, path.name)
    assert not errors
    assert citations[0].doi == "10.1234/abc"
    assert citations[0].authors == "Smith, Jane"


def test_explicit_root_and_excludes(tmp_path):
    (tmp_path / "refs.bib").write_bytes((FIXTURES / "sample.bib").read_bytes())
    (tmp_path / "renv").mkdir()
    (tmp_path / "renv" / "ignored.bib").write_text("bad")
    citations, errors, scanned = read_citations(tmp_path, ["**/*.bib"], [])
    assert len(citations) == 1 and not errors
    assert scanned == ["refs.bib"]
    assert not read_citations(tmp_path, ["**/*.bib"], ["refs.bib"])[0]
    with pytest.raises(ValueError):
        read_citations(tmp_path, ["../*.bib"], [])


@pytest.mark.parametrize("field", ["title", "container-title", "DOI", "URL"])
@pytest.mark.parametrize("value", [None, ["unexpected"]])
def test_malformed_csl_preserves_valid_neighbors(tmp_path, field, value):
    path = tmp_path / "refs.csl.json"
    path.write_text(json.dumps([{field: value}, {"id": "valid", "DOI": "10.1234/abc"}]))
    report_path = tmp_path / "report.json"
    assert (
        main(
            [
                "--scan-root",
                str(tmp_path),
                "--database",
                str(FIXTURES / "notices.csv"),
                "--report",
                str(report_path),
            ]
        )
        == 2
    )
    report = json.loads(report_path.read_text())
    assert report["status"] == "incomplete"
    assert report["coverage"]["citations"] == 1
    assert report["errors"] == [
        f"refs.csl.json:1: invalid CSL entry: {field} must be a string"
    ]


def test_database_schema_fails_closed(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Unexpected\n1\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_database(path)


def test_notice_types_remain_distinct(notices):
    index = Matcher(notices)
    findings = index.match(notices[1].citation, POLICY)
    assert findings[0].notice.nature == "Correction"
    assert findings[0].status == "other_notice"
    assert index.match(notices[0].citation, POLICY)[0].status == "confirmed_retraction"


def test_reinstatement_status(notices):
    retraction = notices[0]
    reinstatement = replace(
        retraction, record_id="3", nature="Reinstatement", date="1/2/2024"
    )
    assert notice_status(retraction, [retraction, reinstatement]) == "reinstated"
    assert (
        notice_status(retraction, [replace(reinstatement, date="unknown")])
        == "status_uncertain"
    )
    assert (
        notice_status(retraction, [replace(reinstatement, date="1/1/2023")])
        == "confirmed_retraction"
    )


def test_metadata_and_doi_conflicts(notices):
    index = Matcher(notices)
    citation = replace(notices[0].citation, doi="")
    assert index.match(citation, POLICY)[0].status == "possible"
    assert not index.match(replace(citation, doi="10.1234/another"), POLICY)


@pytest.mark.parametrize("date", ["", "   "])
def test_blank_reinstatement_dates_preserve_findings(notices, date):
    retraction = notices[0]
    reinstatement = replace(
        retraction, record_id="3", nature="Reinstatement", date=date
    )
    findings = Matcher([retraction, reinstatement]).match(retraction.citation, POLICY)
    assert [f.status for f in findings] == ["status_uncertain", "other_notice"]
    assert (
        notice_status(replace(retraction, date=date), [reinstatement])
        == "status_uncertain"
    )


def test_metadata_match_preserves_same_doi_notice_history(notices):
    retraction = notices[0]
    reinstatement = replace(
        retraction,
        record_id="3",
        nature="Reinstatement",
        date="1/2/2024",
        citation=replace(
            retraction.citation, title="A differently titled reinstatement"
        ),
    )
    findings = Matcher([retraction, reinstatement]).match(
        replace(retraction.citation, doi=""), POLICY
    )
    assert [f.notice.nature for f in findings] == ["Retraction", "Reinstatement"]
    assert all(f.status == "possible" for f in findings)


@pytest.mark.parametrize(
    "citation",
    [
        Citation("x", "x"),
        Citation("x", "x", "Political knowledge", "Smith", "Journal", ""),
        Citation("x", "x", "", "Smith", "Journal", "2020"),
    ],
)
def test_missing_metadata_does_not_match(notices, citation):
    assert not Matcher(notices).match(citation, POLICY)


def test_ambiguous_identical_titles_abstain(notices):
    twin = replace(
        notices[0],
        record_id="99",
        citation=replace(notices[0].citation, doi="10.1234/twin"),
    )
    assert not Matcher([notices[0], twin]).match(replace(twin.citation, doi=""), POLICY)


def test_short_substring_does_not_match(notices):
    citation = Citation(
        "x",
        "x",
        "political knowledge",
        "Jane Smith",
        "Journal of Example Research",
        "2020",
    )
    assert not Matcher(notices).match(citation, POLICY)


def test_no_input_and_incomplete_reports():
    assert make_report([], [], [], [], None)["status"] == "no_input"
    assert make_report([], [], ["parse failed"], [], None)["status"] == "incomplete"
    assert (
        make_report([Citation("x", "x")], [], [], ["x"], None)["status"] == "incomplete"
    )


def test_cli_dry_run_writes_reports_and_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "retract.cli.sync_issue", lambda *a: pytest.fail("Dry run wrote an issue")
    )
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    report = tmp_path / "report.json"
    code = main(
        [
            "--scan-root",
            str(FIXTURES),
            "--paths",
            "sample.bib",
            "--database",
            str(FIXTURES / "notices.csv"),
            "--report",
            str(report),
            "--dry-run",
            "--create-issue",
            "true",
        ]
    )
    assert code == 0
    assert (
        json.loads(report.read_text())["findings"][0]["status"]
        == "confirmed_retraction"
    )
    assert "confirmed-count=1" in output.read_text()


def test_cli_fail_on_retraction(tmp_path):
    assert (
        main(
            [
                "--scan-root",
                str(FIXTURES),
                "--paths",
                "sample.bib",
                "--database",
                str(FIXTURES / "notices.csv"),
                "--report",
                str(tmp_path / "report.json"),
                "--fail-on-retraction",
                "true",
            ]
        )
        == 1
    )


def test_cli_no_input_does_not_download(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "retract.cli.load_database",
        lambda *a: pytest.fail("No-input scan must not download"),
    )
    assert (
        main(["--scan-root", str(tmp_path), "--report", str(tmp_path / "report.json")])
        == 2
    )

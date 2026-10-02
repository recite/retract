# retract

[![Tests](https://github.com/recite/retract/actions/workflows/check.yml/badge.svg)](https://github.com/recite/retract/actions/workflows/check.yml)
[![Release](https://img.shields.io/github/v/release/recite/retract)](https://github.com/recite/retract/releases)

Check bibliography files against [Retraction Watch](https://gitlab.com/crossref/retraction-watch-data). The action reports retractions, corrections, expressions of concern, and reinstatements with the bibliography filename, citation key, notice date, and supporting links. Exact DOI matches and possible metadata matches are separate.

## GitHub Action

```yaml
name: Check bibliography notices
on:
  schedule:
    - cron: '43 6 8 1,4,7,10 *'
  workflow_dispatch:
permissions:
  contents: read
  issues: write
concurrency:
  group: retraction-check
  cancel-in-progress: false
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v7.0.1
        with:
          persist-credentials: false
      - uses: recite/retract@v3
      - uses: actions/upload-artifact@v7.0.1
        if: always()
        with:
          name: retraction-report
          path: retraction-report.json
```

This runs quarterly and on demand. GitHub can [disable schedules in public repositories after 60 days without activity](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). A quarterly schedule alone therefore does not guarantee monitoring of dormant papers. Pin the action to a reviewed commit SHA when immutable execution is required.

| Input | Default | Meaning |
| --- | --- | --- |
| `github-token` | `${{ github.token }}` | Requires `issues: write` when synchronizing issues. |
| `paths` | `**/*.bib`, `**/*.bibtex`, `**/*.csl.json` | Newline-separated glob patterns within the checkout. |
| `exclude` | Empty | Newline-separated path exclusion patterns. |
| `create-issue` | `true` | Set to `false` for reports without GitHub writes. |
| `fail-on-retraction` | `false` | Fail on confirmed active retractions found by DOI. |
| `report-path` | `retraction-report.json` | JSON output path. |

The scanner excludes `.git`, virtual environments, `renv`, `node_modules`, `build`, and `dist`. It rejects files reached through links outside the checkout. Scope `paths` to the manuscript bibliography if historical drafts, example files, or unused references should not be checked. It checks entries in the selected bibliography files, not whether the manuscript actually cites them.

Outputs are `status` and `confirmed-count`. The latter counts citation/notice pairs, so one work cited in multiple files can contribute more than once.

## Results and coverage

- `findings`: at least one notice matched. This includes corrections and possible matches, not just retractions.
- `no_matches`: the selected citations were processed and no notices matched. Database coverage is incomplete; this does not prove that every work is unretracted.
- `incomplete`: parsing, retrieval, schema validation, or identification failed for some input. Entries without a valid DOI need a title of at least 12 normalized characters, a year, and an author or journal to be considered checkable.
- `no_input`: no citation entries were found.

Incomplete and empty scans exit with code 2. They produce reports but do not change GitHub issues. A missing notification permission also exits with code 2 and records `notification_error` in JSON. `fail-on-retraction` produces exit code 1 only for a confirmed active retraction; possible metadata matches never cause that exit code.

Reports contain source paths and citation keys, coverage counts, uncheckable entries, parser errors, notice types and dates, matching methods and scores, and the database SHA-256. If both a retraction and a later reinstatement have the same DOI, the older retraction is marked reinstated. Ambiguous reinstatement dates are marked uncertain. Metadata matches remain possible matches regardless of notice type.

## Matching

The scanner normalizes DOI prefixes, Unicode, HTML markup, and LaTeX accents. Exact normalized DOI agreement takes precedence. Conflicting valid DOIs are not overridden by metadata similarity.

For citations without a database DOI match, character TF–IDF retrieves ten title candidates. The selected rule requires whole-title similarity of at least 0.85, publication years within one year, author-token overlap of at least 0.5 or journal similarity of at least 0.9, and a 0.1 score margin over the next eligible article. Scores are similarities, not calibrated probabilities. The rule was selected using DOI-labelled development data, not hand-picked from the test results.

In the frozen held-out evaluation, it recovered 576 of 614 matching articles (93.8% recall), made no false links among 917 queries, and rejected all 303 background articles. A separate stress test removed the correct candidates and produced two wrong-DOI links in 614 queries. Similar versions can have different DOIs, so metadata-only results require review. These sample results do not establish population precision, especially when retractions are rare. See the [evaluation protocol, dataset, and results](evaluation/README.md).

## Issue behavior

A complete scan maintains one issue marked `<!-- recite-retract:v3 -->`. Unchanged findings cause no write. Closing that issue dismisses the current findings; unchanged findings stay dismissed. Changed findings reopen the issue. A complete scan with no findings closes an open managed issue. Incomplete scans never remove prior alerts.

JSON reports and the Actions summary are the primary outputs. Badge generation is optional in the CLI, and the action never commits badges or changes bibliography files.

## Local use

Python 3.11 or newer is required.

```sh
python -m pip install .
retract-check --scan-root /path/to/paper --dry-run --report report.json
retract-check --paths 'ms/*.bib' --database retraction_watch.csv --dry-run
```

The CLI defaults to report-only behavior. Use `--create-issue true` with `GITHUB_TOKEN` and `GITHUB_REPOSITORY=owner/repository` to synchronize issues. `--dry-run` overrides that flag. A local database file makes scans reproducible and avoids a download. `--badge badge.json` writes a Shields endpoint file without publishing it.

## Formats and repository services

BibTeX/BibLaTeX and CSL-JSON importers produce the same citation records. Name CSL files `*.csl.json` or explicitly select them with `--paths`. Arbitrary JSON files are not discovered automatically.

Zenodo stores record metadata and files; its exported citation describes the deposited item, not automatically its reference list. A future Zenodo adapter should read uploaded bibliography files and explicit references or `cites` relationships. It should not interpret every related identifier as a citation. Remote Zenodo, RIS, CFF, and PDF-reference extraction are not implemented in v3.

## Migration from v2

Use `github-token` in place of `github_token`, or omit it to use the workflow token. Grant `issues: write`. Replace `check_retractions.py` invocations with `retract-check`. Install from `pyproject.toml`; there is no separate runtime requirements list.

Review old v2 issues manually: v3 does not modify issues that lack its ownership marker. Old badge files are not maintained. Consumers should upload the JSON report with `if: always()` so incomplete scans remain inspectable.

## Development

```sh
python -m pip install -e '.[dev]'
make check
make ci-docker
make docker-test
make benchmark
```

`make check` runs Black, isort, flake8, and offline tests. `make ci-docker` runs those checks in a standard Python image. `make docker-test` builds the actual action image and exercises it with networking disabled. The benchmark uses frozen public metadata and does not contact GitHub or Crossref.

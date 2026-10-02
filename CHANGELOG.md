# Changelog

## 3.0.0

- Distinguish retractions, corrections, expressions of concern, and reinstatements.
- Separate confirmed DOI matches from possible metadata matches.
- Normalize DOI URLs and preserve Unicode and LaTeX text.
- Read BibTeX/BibLaTeX and CSL-JSON with explicit parser failures and coverage reporting.
- Retrieve candidates with character TF–IDF and use a rule selected on DOI-labelled development data. Ship the frozen evaluation corpus and held-out results.
- Write JSON reports and Actions summaries. Empty and incomplete scans cannot report a clean result or close existing alerts.
- Update a managed issue only when findings change; respect dismissal of unchanged findings.
- Add an offline CLI, tests, packaging checks, and container tests with current workflow actions.
- Remove the old Python entry point, `github_token` input, and automatic badge commits. See the README for migration.

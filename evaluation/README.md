# DOI-labelled metadata matching

This evaluation asks whether a citation's text identifies the same DOI as a Retraction Watch record. DOI agreement supplies identity labels. Notice type is evaluated separately: a matching DOI is not proof that the notice is a retraction.

## Corpus and provenance

`data/notices.jsonl.gz` contains the metadata fields used by the scanner from the September 30, 2026 Retraction Watch snapshot: 72,831 notices. `data/queries.jsonl.gz` contains 2,967 independently retrieved Crossref metadata records. Each query has an oracle DOI label and a citation with its DOI field removed. Source DOIs in citation keys are provenance only; the matcher reads only title, authors, journal, and year.

The acquisition selected 2,000 normalized Retraction Watch DOIs using seed 20261001 and requested their Crossref metadata in batches of 40. Ten Crossref random samples of 100 journal articles supplied background examples. After missing metadata and duplicate DOI records were removed, the corpus contained 1,968 queries whose DOI appeared in the database and 999 background queries. The random Crossref responses are frozen in the distributed query file; rerunning acquisition samples a new background corpus. No private bibliography contents are included.

A DOI's SHA-256 determines its partition: 40% training, 30% validation, 30% test. Repeated DOI records cannot cross partitions. The full public notice catalog is the retrieval target, just as it is at deployment; fitting its unsupervised TF–IDF index does not use held-out query text or labels. DOI aliases and separate versions remain different identities under this protocol, which can overstate some apparent errors and does not resolve work-level equivalence.

## Selection and held-out test

We compared normalized exact titles, whole-title string similarity, and character TF–IDF cosine similarity. All methods used TF–IDF retrieval against the full notice catalog and the same available year, author, and journal evidence. Each query has ten retrieved candidates, including near-title wrong-DOI negatives; a true candidate is not injected if retrieval misses it.

Thresholds, corroboration requirements, year tolerance, and ambiguity margins were searched on the development partitions. Policies had to make zero wrong links in training and validation; among those, validation recall selected the winner. Test labels were not used to choose the policy. The selected policy is in `retract/policy.json`.

| Decision rule | Validation correct links | Validation false links | Validation recall |
| --- | ---: | ---: | ---: |
| Exact normalized title | 452 | 0 | 75.8% |
| Whole-title similarity | 565 | 0 | 94.8% |
| TF–IDF cosine | 564 | 0 | 94.6% |

The selected whole-title rule produced 576 correct links, zero false links, 38 missed matching queries, and 303 correctly rejected background queries on the 917-query test set. Recall was 93.8%. Zero observed false links does not establish perfect precision or a low deployment false-alert rate; the benchmark contains many more positives than a typical paper's bibliography. Top-ten retrieval contained the correct DOI for 99.3% of all positive queries; the remaining misses cannot be repaired by changing the final decision threshold alone.

After selection, a harder stress test removed every correct-DOI candidate from positive queries. The unchanged policy produced 5 wrong links in 758 training queries, 5 in 596 validation queries, and 2 in 614 test queries. This challenge measures rejection when the true record is unavailable. It exposed similar versions, errata, and related articles. It was not used to retune the policy; metadata findings remain explicitly provisional.

This is a cross-source metadata benchmark, not a representative sample of messy human-authored bibliographies. Separate regression fixtures cover accents, malformed entries, missing fields, and short or ambiguous titles. Local parser checks also used the user's bibliographies without adding their contents to this repository. A later matching change must use a new untouched test cohort if it is informed by these published test errors.

## Reproduction

```sh
python -m pip install -e '.[dev]'
make benchmark
```

The benchmark rebuilds the index, regenerates candidates, selects the policy using development labels, and writes `results.json` and `results.predictions.jsonl.gz`. It includes failed retrievals and uncheckable queries in recall denominators. Runtime is machine-specific. To audit the frozen decision alone, run the tests in `tests/test_evaluation.py`.

The raw-data rebuild accepts a local Retraction Watch CSV and cached Crossref responses:

```sh
python -m evaluation.fetch_metadata --database retraction_watch.csv --cache /tmp/crossref
python -m evaluation.build_dataset --database retraction_watch.csv --crossref-cache /tmp/crossref
```

`data/provenance.json` records the original CSV hash and sampling procedure. Source documentation: [Crossref REST API](https://github.com/CrossRef/rest-api-doc), [Retraction Watch fields](https://gitlab.com/crossref/retraction-watch-data/-/raw/main/README.md). Bibliographic metadata is attributed to those sources. The evaluation files contain no abstracts or full article text.

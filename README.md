## retract: Get Notified When Cited Articles Are Retracted

A Github Action that opens an issue when a retracted article is discovered in a .bib file in the repository.

The action uses data from [RetractionWatch](https://gitlab.com/crossref/retraction-watch-data) to look for retracted articles based on DOI or similarity to title, author, journal, and year. It triggers when a .bib file is updated.

Here's a [sample issue](https://github.com/recite/retract/issues/1) opened by the action for this [sample.bib](https://github.com/recite/retract/blob/main/sample.bib) file.

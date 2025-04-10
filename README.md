## retract: Get Notified When Cited Articles Are Retracted

![GitHub release (latest by date)](https://img.shields.io/github/v/release/recite/retract)
![GitHub Marketplace](https://img.shields.io/badge/GitHub%20Marketplace-retract)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Github Action that opens an issue when a retracted article is discovered in a .bib file in the repository. (You can run it on a regular cadence. The default is to check if .bib is updated or every three months.)

The action uses data from [RetractionWatch](https://gitlab.com/crossref/retraction-watch-data) to look for retracted articles based on DOI or similarity to title, author, journal, and year. It triggers when a .bib file is updated.

Here's a [sample issue](https://github.com/recite/retract/issues/1) opened by the action for this [sample.bib](https://github.com/recite/retract/blob/main/sample.bib) file.

Here's a [repository](https://github.com/soodoku/adult/) that uses this action. (Just copy the action and you are gtg.)

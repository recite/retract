import os
import re
import requests
import bibtexparser
import pandas as pd
from fuzzywuzzy import fuzz
from github import Github

# URLs and tokens
RETRACTION_DB_URL = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "unknown/repo")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Load retraction database
def load_retraction_db():
    """
    Fetch and load the latest Retraction Watch database efficiently.
    
    Returns:
        A set of DOIs for fast lookup and a list of metadata records for fuzzy matching.
    """
    print("Fetching latest Retraction Watch database...")
    df_iter = pd.read_csv(RETRACTION_DB_URL, low_memory=False, iterator=True, chunksize=50000)
    doi_set = set()
    metadata_records = []

    for chunk in df_iter:
        if "OriginalPaperDOI" in chunk.columns:
            chunk_dois = chunk["OriginalPaperDOI"].dropna().astype(str).str.strip().str.lower()
            doi_set.update(chunk_dois)

        if all(col in chunk.columns for col in ["Author", "Title", "Journal", "OriginalPaperDate"]):
            chunk_metadata = chunk[["Author", "Title", "Journal", "OriginalPaperDate"]].fillna("").astype(str)
            for _, row in chunk_metadata.iterrows():
                normalized_title = normalize_text(row["Title"])
                normalized_authors = normalize_text(row["Author"])
                normalized_journal = normalize_text(row["Journal"])
                normalized_year = extract_year(row["OriginalPaperDate"])

                metadata_records.append((normalized_title, normalized_authors, normalized_journal, normalized_year))

    print(f"Loaded {len(doi_set)} retracted DOIs and {len(metadata_records)} metadata records for fuzzy matching.")
    return doi_set, metadata_records

# Normalize text using regex (remove special characters, lowercase)
def normalize_text(text):
    return re.sub(r"[^a-zA-Z0-9\s]", "", text).strip().lower()

# Extract year from date string
def extract_year(date_str):
    match = re.search(r"\b(19|20)\d{2}\b", date_str)  # Match years from 1900-2099
    return match.group(0) if match else ""

# Extract DOIs and metadata from .bib files
def extract_data_from_bib():
    dois = set()
    metadata_entries = []
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".bib"):
                print(f"Scanning {file} for DOIs and metadata...")
                with open(os.path.join(root, file), "r", encoding="utf-8") as bibfile:
                    bib_database = bibtexparser.load(bibfile)
                    for entry in bib_database.entries:
                        doi = entry.get("doi") or entry.get("DOI")
                        if doi:
                            dois.add(doi.strip().lower())

                        # Extract metadata for fuzzy matching
                        title = normalize_text(entry.get("title", ""))
                        authors = normalize_text(entry.get("author", ""))
                        journal = normalize_text(entry.get("journal", ""))
                        year = extract_year(entry.get("year", ""))

                        metadata_entries.append((title, authors, journal, year))
    return dois, metadata_entries

# Perform fuzzy matching across title, authors, journal, and year
def fuzzy_match(metadata_entries, retraction_metadata, threshold=85):
    matched_titles = []
    for bib_title, bib_authors, bib_journal, bib_year in metadata_entries:
        for ret_title, ret_authors, ret_journal, ret_year in retraction_metadata:
            title_score = fuzz.partial_ratio(bib_title, ret_title)
            author_score = fuzz.partial_ratio(bib_authors, ret_authors)
            journal_score = fuzz.partial_ratio(bib_journal, ret_journal)
            year_match = (bib_year == ret_year)  # Exact year match

            # Strong match if title + (author OR journal) + year
            if title_score >= threshold and (author_score >= threshold or journal_score >= threshold) and year_match:
                print(f"⚠️ Strong retraction match: {bib_title} ~ {ret_title} (Title: {title_score}, Author: {author_score}, Journal: {journal_score})")
                matched_titles.append(bib_title)
    return matched_titles

# Open GitHub Issue for detected retractions
def create_github_issue(retracted_dois, fuzzy_matches):
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set, skipping issue creation.")
        return

    repo = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)
    issue_title = "⚠️ Retracted Articles Detected in .bib Files"
    issue_body = "### Retracted Articles Found\n"

    if retracted_dois:
        issue_body += "\n**DOI Matches:**\n"
        issue_body += "\n".join([f"- [DOI: {doi}](https://doi.org/{doi})" for doi in retracted_dois])

    if fuzzy_matches:
        issue_body += "\n\n**Fuzzy Matches (Possible Retractions):**\n"
        issue_body += "\n".join([f"- {title}" for title in fuzzy_matches])

    existing_issues = repo.get_issues(state="open")
    for issue in existing_issues:
        if issue.title == issue_title:
            print("Retracted articles issue already exists. Updating issue.")
            issue.edit(body=issue_body)
            return

    repo.create_issue(title=issue_title, body=issue_body)

def main():
    retracted_dois, retraction_metadata = load_retraction_db()
    extracted_dois, metadata_entries = extract_data_from_bib()

    # DOI-based matches
    retracted_dois_found = extracted_dois.intersection(retracted_dois)

    # Fuzzy matching
    fuzzy_matches_found = fuzzy_match(metadata_entries, retraction_metadata)

    if retracted_dois_found or fuzzy_matches_found:
        print(f"Found {len(retracted_dois_found)} retracted DOIs and {len(fuzzy_matches_found)} fuzzy matches.")
        create_github_issue(retracted_dois_found, fuzzy_matches_found)
    else:
        print("No retracted articles found.")

if __name__ == "__main__":
    main()


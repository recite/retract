import os
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
    print("Fetching latest Retraction Watch database...")
    df_iter = pd.read_csv(RETRACTION_DB_URL, low_memory=False, iterator=True, chunksize=50000)
    doi_set = set()
    metadata_records = []

    for chunk in df_iter:
        if "OriginalPaperDOI" in chunk.columns:
            chunk_dois = chunk["OriginalPaperDOI"].dropna().astype(str).str.strip().str.lower()
            doi_set.update(chunk_dois)

        # Store metadata for fuzzy matching
        if all(col in chunk.columns for col in ["Author", "Year", "Journal", "Title", "Volume", "Issue", "Pages"]):
            chunk_metadata = chunk[["Author", "Year", "Journal", "Title", "Volume", "Issue", "Pages"]].fillna("").astype(str)
            for _, row in chunk_metadata.iterrows():
                synthetic_string = generate_synthetic_string(row)
                metadata_records.append((synthetic_string, row["Title"]))

    print(f"Loaded {len(doi_set)} retracted DOIs and {len(metadata_records)} metadata records for fuzzy matching.")
    return doi_set, metadata_records

# Generate a synthetic string for fuzzy matching
def generate_synthetic_string(entry):
    return f"{entry['Author']} {entry['Year']} {entry['Journal']} {entry['Title']} {entry['Volume']} {entry['Issue']} {entry['Pages']}".strip().lower()

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
                        author = entry.get("author", "")
                        year = entry.get("year", "")
                        journal = entry.get("journal", "")
                        title = entry.get("title", "")
                        volume = entry.get("volume", "")
                        issue = entry.get("issue", "")
                        pages = entry.get("pages", "")
                        synthetic_string = generate_synthetic_string({
                            "Author": author, "Year": year, "Journal": journal,
                            "Title": title, "Volume": volume, "Issue": issue, "Pages": pages
                        })
                        metadata_entries.append((synthetic_string, title))
    return dois, metadata_entries

# Perform fuzzy matching
def fuzzy_match(metadata_entries, retraction_metadata, threshold=90):
    matched_titles = []
    for bib_string, bib_title in metadata_entries:
        for ret_string, ret_title in retraction_metadata:
            similarity = fuzz.partial_ratio(bib_string, ret_string)
            if similarity >= threshold:
                print(f"⚠️ Possible retraction match: {bib_title} ~ {ret_title} (Score: {similarity})")
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

    # Check if an issue already exists
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

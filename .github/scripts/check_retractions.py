import os
import requests
import bibtexparser
import pandas as pd
from github import Github

# URL of the latest retraction database
RETRACTION_DB_URL = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"

# GitHub repository info (set automatically by GitHub Actions)
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "unknown/repo")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Load retraction database
def load_retraction_db():
    print("Fetching latest Retraction Watch database...")
    df = pd.read_csv(RETRACTION_DB_URL, low_memory=False)
    return set(df["OriginalPaperDOI"].dropna().astype(str))

# Extract DOIs from .bib files
def extract_dois_from_bib():
    dois = set()
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".bib"):
                print(f"Scanning {file} for DOIs...")
                with open(os.path.join(root, file), "r", encoding="utf-8") as bibfile:
                    bib_database = bibtexparser.load(bibfile)
                    for entry in bib_database.entries:
                        doi = entry.get("doi") or entry.get("DOI")
                        if doi:
                            dois.add(doi.strip().lower())
    return dois

# Open GitHub Issue for retracted articles
def create_github_issue(retracted_dois):
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set, skipping issue creation.")
        return

    print(f"Creating GitHub issue for {len(retracted_dois)} retracted articles.")
    repo = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)
    issue_title = "⚠️ Retracted Articles Detected in .bib Files"
    issue_body = "The following articles in your `.bib` files have been retracted:\n\n"
    issue_body += "\n".join([f"- [DOI: {doi}](https://doi.org/{doi})" for doi in retracted_dois])

    # Check if an issue already exists
    existing_issues = repo.get_issues(state="open")
    for issue in existing_issues:
        if issue.title == issue_title:
            print("Retracted articles issue already exists. Updating issue.")
            issue.edit(body=issue_body)
            return

    # Create a new issue if none exists
    repo.create_issue(title=issue_title, body=issue_body)

def main():
    retraction_db = load_retraction_db()
    extracted_dois = extract_dois_from_bib()

    retracted_dois = extracted_dois.intersection(retraction_db)
    if retracted_dois:
        print(f"Found {len(retracted_dois)} retracted articles.")
        create_github_issue(retracted_dois)
    else:
        print("No retracted articles found.")

if __name__ == "__main__":
    main()

"""
discover.py
Searches Google for company career boards (Greenhouse + Ashby) matching your
target roles, extracts board tokens from the result URLs, validates them, and
merges newly-found valid ones into config/companies.json.

This is what makes the pipeline cover "all companies hiring for this kind of
role" instead of a fixed hand-picked list - run it on its own schedule
(the included GitHub Actions workflow runs it every 6 hours, well within the
free Google Custom Search quota of 100 queries/day).

Usage:
    python src/discover.py
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from google_search import search  # noqa: E402
from greenhouse_client import validate_board_token  # noqa: E402
from ashby_client import validate_board_name  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPANIES_PATH = os.path.join(ROOT, "config", "companies.json")
DISCOVERY_LOG_PATH = os.path.join(ROOT, "data", "discovered_companies.json")

# Kept small and broad to stay well within the free 100 queries/day quota
# (this list x 2 ATS = queries per run; default workflow runs 4x/day)
DISCOVERY_KEYWORDS = [
    "backend engineer",
    "software engineer AI",
    "machine learning engineer",
    "distributed systems engineer",
]

GREENHOUSE_URL_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)")
ASHBY_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)")


def find_tokens(urls: list[str], pattern: re.Pattern) -> set[str]:
    found = set()
    for url in urls:
        match = pattern.search(url)
        if match:
            found.add(match.group(1).lower())
    return found


def main():
    with open(COMPANIES_PATH) as f:
        companies = json.load(f)

    known_gh = set(companies.get("greenhouse", []))
    known_ashby = set(companies.get("ashby", []))

    candidate_gh, candidate_ashby = set(), set()
    for keyword in DISCOVERY_KEYWORDS:
        gh_urls = search(f"(site:boards.greenhouse.io OR site:job-boards.greenhouse.io) {keyword}")
        candidate_gh |= find_tokens(gh_urls, GREENHOUSE_URL_RE)

        ashby_urls = search(f"site:jobs.ashbyhq.com {keyword}")
        candidate_ashby |= find_tokens(ashby_urls, ASHBY_URL_RE)

    new_gh_candidates = candidate_gh - known_gh
    new_ashby_candidates = candidate_ashby - known_ashby

    added_gh = [t for t in new_gh_candidates if validate_board_token(t)]
    added_ashby = [t for t in new_ashby_candidates if validate_board_name(t)]

    if added_gh or added_ashby:
        companies["greenhouse"] = sorted(known_gh | set(added_gh))
        companies["ashby"] = sorted(known_ashby | set(added_ashby))
        with open(COMPANIES_PATH, "w") as f:
            json.dump(companies, f, indent=2)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "added_greenhouse": added_gh,
        "added_ashby": added_ashby,
        "rejected_invalid": list((new_gh_candidates - set(added_gh)) | (new_ashby_candidates - set(added_ashby))),
    }
    history = []
    if os.path.exists(DISCOVERY_LOG_PATH):
        with open(DISCOVERY_LOG_PATH) as f:
            history = json.load(f)
    history.append(log_entry)
    os.makedirs(os.path.dirname(DISCOVERY_LOG_PATH), exist_ok=True)
    with open(DISCOVERY_LOG_PATH, "w") as f:
        json.dump(history, f, indent=2)

    print(f"Added {len(added_gh)} new Greenhouse boards: {added_gh}")
    print(f"Added {len(added_ashby)} new Ashby boards: {added_ashby}")


if __name__ == "__main__":
    main()

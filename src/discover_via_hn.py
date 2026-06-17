"""
discover_via_hn.py
Fully free - no API keys, no signups, no cost. Finds new Greenhouse/Ashby
company boards by scanning the monthly "Ask HN: Who is hiring?" thread and
its comments, via the public Algolia HN Search API (hn.algolia.com/api/v1,
no auth required, officially documented, widely used).

These threads are dense with real companies posting real roles with direct
ATS links, and skew toward tech/startups - a good fit for this use case.

Usage:
    python src/discover_via_hn.py
"""
import json
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from greenhouse_client import validate_board_token  # noqa: E402
from ashby_client import validate_board_name  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPANIES_PATH = os.path.join(ROOT, "config", "companies.json")
DISCOVERY_LOG_PATH = os.path.join(ROOT, "data", "discovered_companies.json")

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
TIMEOUT = 30

GREENHOUSE_URL_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/?#\s)\"'>]+)")
ASHBY_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/?#\s)\"'>]+)")

# Only consider comments that mention at least one of these, so we don't pull in
# sales/marketing/design-only postings that happen to be in the same thread
ROLE_SIGNAL_WORDS = ["backend", " ai ", "ai/", "/ai", "llm", "machine learning",
                      "distributed systems", "software engineer", "ml engineer"]


def find_latest_hiring_thread_id() -> str | None:
    params = {"query": "Who is hiring", "tags": "story", "hitsPerPage": 5}
    resp = requests.get(ALGOLIA_SEARCH_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    for hit in resp.json().get("hits", []):
        if hit.get("title", "").startswith("Ask HN: Who is hiring?"):
            return hit["objectID"]
    return None


def extract_texts_from_tree(node: dict) -> list[str]:
    texts = []
    if node.get("text"):
        texts.append(node["text"])
    for child in node.get("children", []) or []:
        texts.extend(extract_texts_from_tree(child))
    return texts


def fetch_comment_texts(item_id: str) -> list[str]:
    resp = requests.get(ALGOLIA_ITEM_URL.format(id=item_id), timeout=TIMEOUT)
    resp.raise_for_status()
    return extract_texts_from_tree(resp.json())


def find_tokens(texts: list[str], pattern: re.Pattern) -> set[str]:
    found = set()
    for text in texts:
        for match in pattern.finditer(text):
            found.add(match.group(1).lower().rstrip(".,;:"))
    return found


def main():
    with open(COMPANIES_PATH) as f:
        companies = json.load(f)
    known_gh = set(companies.get("greenhouse", []))
    known_ashby = set(companies.get("ashby", []))

    thread_id = find_latest_hiring_thread_id()
    if not thread_id:
        print("[discover_via_hn] Could not find a current 'Who is hiring?' thread.")
        return
    print(f"[discover_via_hn] Using thread {thread_id}")

    comment_texts = fetch_comment_texts(thread_id)
    relevant_texts = [t for t in comment_texts if any(w in t.lower() for w in ROLE_SIGNAL_WORDS)]
    print(f"[discover_via_hn] {len(comment_texts)} comments total, {len(relevant_texts)} mention a relevant role/skill.")

    candidate_gh = find_tokens(relevant_texts, GREENHOUSE_URL_RE) - known_gh
    candidate_ashby = find_tokens(relevant_texts, ASHBY_URL_RE) - known_ashby

    added_gh = [t for t in candidate_gh if validate_board_token(t)]
    added_ashby = [t for t in candidate_ashby if validate_board_name(t)]

    if added_gh or added_ashby:
        companies["greenhouse"] = sorted(known_gh | set(added_gh))
        companies["ashby"] = sorted(known_ashby | set(added_ashby))
        with open(COMPANIES_PATH, "w") as f:
            json.dump(companies, f, indent=2)

    log_entry = {
        "thread_id": thread_id,
        "added_greenhouse": added_gh,
        "added_ashby": added_ashby,
        "rejected_invalid": list((candidate_gh - set(added_gh)) | (candidate_ashby - set(added_ashby))),
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

"""
google_search.py
Thin wrapper around the Google Custom Search JSON API.
Free tier: 100 queries/day. Needs GOOGLE_API_KEY and GOOGLE_CSE_ID env vars.
Setup: see README.md "Setting up auto-discovery" section.
"""
import os
import requests

ENDPOINT = "https://www.googleapis.com/customsearch/v1"
TIMEOUT = 15


def search(query: str, num_results: int = 10) -> list[str]:
    """Returns a list of result URLs for the given query, or [] on failure/quota exhaustion."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        print("[google_search] GOOGLE_API_KEY / GOOGLE_CSE_ID not set - skipping discovery search.")
        return []

    params = {"key": api_key, "cx": cse_id, "q": query, "num": min(num_results, 10)}
    try:
        resp = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
        if resp.status_code == 429:
            print("[google_search] Quota exhausted for today.")
            return []
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [item["link"] for item in items if "link" in item]
    except requests.RequestException as e:
        print(f"[google_search] Error searching '{query}': {e}")
        return []

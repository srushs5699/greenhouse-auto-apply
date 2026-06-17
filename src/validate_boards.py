"""
validate_boards.py
Run this standalone to check which entries in config/companies.json are real,
reachable boards (Greenhouse and Ashby both have their own token namespace).
Invalid ones get written to data/invalid_boards.json so you know what to fix.

Usage:
    python src/validate_boards.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from greenhouse_client import validate_board_token as validate_greenhouse  # noqa: E402
from ashby_client import validate_board_name as validate_ashby  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPANIES_PATH = os.path.join(ROOT, "config", "companies.json")
INVALID_OUTPUT_PATH = os.path.join(ROOT, "data", "invalid_boards.json")


def check_list(tokens, validator):
    valid, invalid = [], []
    for token in tokens:
        ok = validator(token)
        print(f"  {'OK   ' if ok else 'FAIL '} {token}")
        (valid if ok else invalid).append(token)
    return valid, invalid


def main():
    with open(COMPANIES_PATH) as f:
        companies = json.load(f)

    print("Greenhouse:")
    gh_valid, gh_invalid = check_list(companies.get("greenhouse", []), validate_greenhouse)

    print("\nAshby:")
    ashby_valid, ashby_invalid = check_list(companies.get("ashby", []), validate_ashby)

    total = len(companies.get("greenhouse", [])) + len(companies.get("ashby", []))
    total_valid = len(gh_valid) + len(ashby_valid)

    os.makedirs(os.path.dirname(INVALID_OUTPUT_PATH), exist_ok=True)
    with open(INVALID_OUTPUT_PATH, "w") as f:
        json.dump({"invalid_greenhouse": gh_invalid, "invalid_ashby": ashby_invalid}, f, indent=2)

    print(f"\n{total_valid}/{total} boards valid.")
    if gh_invalid or ashby_invalid:
        print(f"Invalid tokens written to {INVALID_OUTPUT_PATH}.")
        print("Remove or fix these in config/companies.json.")


if __name__ == "__main__":
    main()

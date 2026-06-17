"""
validate_boards.py
Run this standalone to check which entries in config/companies.json are real,
reachable Greenhouse boards. Invalid ones (wrong slug, company moved off Greenhouse,
etc.) get written to data/invalid_boards.json so you know what to fix or remove.

Usage:
    python src/validate_boards.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from greenhouse_client import validate_board_token  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPANIES_PATH = os.path.join(ROOT, "config", "companies.json")
INVALID_OUTPUT_PATH = os.path.join(ROOT, "data", "invalid_boards.json")


def main():
    with open(COMPANIES_PATH) as f:
        companies = json.load(f)["companies"]

    valid, invalid = [], []
    for token in companies:
        ok = validate_board_token(token)
        print(f"{'OK   ' if ok else 'FAIL '} {token}")
        (valid if ok else invalid).append(token)

    os.makedirs(os.path.dirname(INVALID_OUTPUT_PATH), exist_ok=True)
    with open(INVALID_OUTPUT_PATH, "w") as f:
        json.dump({"invalid_tokens": invalid}, f, indent=2)

    print(f"\n{len(valid)}/{len(companies)} boards valid.")
    if invalid:
        print(f"Invalid tokens written to {INVALID_OUTPUT_PATH}: {invalid}")
        print("Remove or fix these in config/companies.json.")


if __name__ == "__main__":
    main()

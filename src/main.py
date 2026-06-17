"""
main.py
Entry point - run hourly (via cron, Task Scheduler, or GitHub Actions).

Usage:
    python src/main.py            # uses dry_run setting from config
    python src/main.py --live     # forces real submission regardless of config
    python src/main.py --dry-run  # forces dry-run regardless of config
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from greenhouse_client import fetch_jobs  # noqa: E402
from matcher import filter_jobs  # noqa: E402
from state import already_processed, record  # noqa: E402
from form_filler import apply_to_job  # noqa: E402
from notifier import send_summary_email  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_json(relative_path: str) -> dict:
    with open(os.path.join(ROOT, relative_path)) as f:
        return json.load(f)


def main(dry_run_override: bool | None):
    profile = load_json("config/candidate_profile.json")
    companies = load_json("config/companies.json")["companies"]
    targeting = profile["targeting"]

    dry_run = dry_run_override if dry_run_override is not None else profile.get("dry_run", True)
    print(f"[main] Running with dry_run={dry_run}")

    new_matches = []
    for board_token in companies:
        jobs = fetch_jobs(board_token)
        if jobs is None:
            print(f"[main] Skipping '{board_token}' - board did not resolve. Run validate_boards.py.")
            continue
        for job in filter_jobs(jobs, targeting):
            if already_processed(board_token, job["id"]):
                continue
            job["company_name"] = board_token
            new_matches.append((board_token, job))

    print(f"[main] {len(new_matches)} new matching posting(s) found.")

    results = []
    if new_matches:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for board_token, job in new_matches:
                result = apply_to_job(browser, job, profile, dry_run=dry_run)
                record(board_token, job["id"], job["title"], result["status"], result["detail"])
                results.append({"company": board_token, "job": job, "result": result})
                print(f"  [{result['status']}] {board_token}: {job['title']} - {result['detail']}")
            browser.close()

    send_summary_email(profile["notification"]["to_address"], results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--live", action="store_true", help="Force real submission")
    group.add_argument("--dry-run", action="store_true", help="Force dry-run, never submit")
    args = parser.parse_args()

    override = True if args.dry_run else (False if args.live else None)
    main(override)

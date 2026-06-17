"""
main.py
Entry point - run hourly (via cron, Task Scheduler, or GitHub Actions).
Covers both Greenhouse and Ashby boards listed in config/companies.json
(discover.py grows that list automatically on its own schedule).

Usage:
    python src/main.py            # uses dry_run setting from config
    python src/main.py --live     # forces real submission regardless of config
    python src/main.py --dry-run  # forces dry-run regardless of config
"""
import argparse
import json
import os
import sys

# Force stdout to flush immediately after every print. In CI environments
# stdout often isn't a real terminal, so Python may buffer output rather
# than writing it line-by-line - this can make a running job look "stuck"
# in the Actions log even when print statements have already executed,
# since nothing shows up until the buffer flushes (often only at process
# exit). Forcing line buffering here means log output always reflects
# what's actually happened so far.
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.dirname(__file__))
from greenhouse_client import fetch_jobs as fetch_greenhouse_jobs  # noqa: E402
from ashby_client import fetch_jobs as fetch_ashby_jobs, normalize_job as normalize_ashby_job  # noqa: E402
from matcher import filter_jobs  # noqa: E402
from state import already_processed, record  # noqa: E402
from form_filler import apply_to_job  # noqa: E402
from notifier import send_summary_email  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_json(relative_path: str) -> dict:
    with open(os.path.join(ROOT, relative_path)) as f:
        return json.load(f)


def collect_matches(companies: dict, targeting: dict) -> list[tuple[str, dict]]:
    matches = []
    seen_this_run = set()  # guards against duplicate entries within a single fetch (seen in the wild with Instacart)

    for board_token in companies.get("greenhouse", []):
        jobs = fetch_greenhouse_jobs(board_token)
        if jobs is None:
            print(f"[main] Skipping greenhouse:'{board_token}' - board did not resolve.")
            continue
        for job in filter_jobs(jobs, targeting):
            key = (board_token, job["id"])
            if key in seen_this_run or already_processed(board_token, job["id"]):
                continue
            seen_this_run.add(key)
            job["company_name"] = board_token
            job["source"] = "greenhouse"
            matches.append((board_token, job))

    for board_name in companies.get("ashby", []):
        raw_jobs = fetch_ashby_jobs(board_name)
        if raw_jobs is None:
            print(f"[main] Skipping ashby:'{board_name}' - board did not resolve.")
            continue
        normalized = [normalize_ashby_job(board_name, j) for j in raw_jobs]
        for job in filter_jobs(normalized, targeting):
            key = (board_name, job["id"])
            if key in seen_this_run or already_processed(board_name, job["id"]):
                continue
            seen_this_run.add(key)
            matches.append((board_name, job))

    return matches


def main(dry_run_override):
    profile = load_json("config/candidate_profile.json")
    companies = load_json("config/companies.json")
    targeting = profile["targeting"]

    dry_run = dry_run_override if dry_run_override is not None else profile.get("dry_run", True)
    print(f"[main] Running with dry_run={dry_run}")

    new_matches = collect_matches(companies, targeting)
    print(f"[main] {len(new_matches)} new matching posting(s) found.")

    results = []
    if new_matches:
        with sync_playwright() as p:
            # Explicit timeout (default would otherwise be Playwright's
            # internal default, ~30s for most operations, but launch()
            # itself can hang longer on a misconfigured CI runner if
            # required system libraries are missing - bound it explicitly
            # so a launch failure raises a clear, fast error instead of
            # silently blocking the whole run with no output.
            print("[main] Launching browser...")
            browser = p.chromium.launch(headless=True, timeout=60000)
            print("[main] Browser launched successfully.")
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

"""
greenhouse_client.py
Thin wrapper around Greenhouse's public Job Board API.
Docs: https://developers.greenhouse.io/job-board.html
No authentication needed for GET endpoints - this is publicly available data.
"""
import requests

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
TIMEOUT = 15


def fetch_jobs(board_token: str) -> list[dict] | None:
    """
    Fetch all currently published jobs for a company's Greenhouse board.
    Returns None if the board_token doesn't resolve (invalid/wrong company slug).
    content=true includes the full HTML job description, needed for keyword/experience matching.
    """
    url = f"{BASE_URL}/{board_token}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("jobs", [])
    except requests.RequestException as e:
        print(f"[greenhouse_client] Error fetching jobs for '{board_token}': {e}")
        return None


def fetch_job_with_questions(board_token: str, job_id: int) -> dict | None:
    """
    Fetch a single job including its application question schema.
    Useful for previewing what a job's form will ask before attempting to fill it.
    """
    url = f"{BASE_URL}/{board_token}/jobs/{job_id}?questions=true"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[greenhouse_client] Error fetching job {job_id} for '{board_token}': {e}")
        return None


def validate_board_token(board_token: str) -> bool:
    """Quick check: does this board_token resolve to a real, reachable Greenhouse board?"""
    url = f"{BASE_URL}/{board_token}"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException:
        return False

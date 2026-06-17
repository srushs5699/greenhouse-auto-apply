"""
ashby_client.py
Thin wrapper around Ashby's public Job Board API.
Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
No authentication needed for reads - this is publicly available data.
Submitting applications (applicationForm.submit) requires the employer's own
private API key, so - same as Greenhouse - we can read freely but can't submit
through the API as an outside candidate. Submission goes through the real form.
"""
import requests

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
TIMEOUT = 15


def fetch_jobs(board_name: str) -> list[dict] | None:
    """
    Fetch all currently listed jobs for a company's Ashby board.
    Returns None if the board_name doesn't resolve.
    """
    url = f"{BASE_URL}/{board_name}?includeCompensation=true"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("jobs", [])
    except requests.RequestException as e:
        print(f"[ashby_client] Error fetching jobs for '{board_name}': {e}")
        return None
    except ValueError:
        # Non-JSON response usually means the board name doesn't exist
        return None


def validate_board_name(board_name: str) -> bool:
    """Quick check: does this board_name resolve to a real, reachable Ashby board?"""
    url = f"{BASE_URL}/{board_name}"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return False
        # Ashby returns 200 with an empty-ish JSON for some invalid names too,
        # so also confirm the response actually parses as job-board JSON.
        data = resp.json()
        return "jobs" in data
    except (requests.RequestException, ValueError):
        return False


def normalize_job(board_name: str, job: dict) -> dict:
    """
    Convert an Ashby job dict into the same shape main.py/matcher.py expect
    from Greenhouse jobs: id, title, content, first_published, absolute_url.
    """
    url = job.get("applyUrl") or job.get("jobUrl", "")
    job_id = job.get("id") or url.rstrip("/").split("/")[-1]
    return {
        "id": job_id,
        "title": job.get("title", ""),
        "content": job.get("descriptionPlain") or job.get("descriptionHtml", ""),
        "first_published": job.get("publishedAt"),
        "absolute_url": url,
        "company_name": board_name,
        "source": "ashby",
    }

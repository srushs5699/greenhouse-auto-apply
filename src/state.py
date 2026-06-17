"""
state.py
Tracks which job IDs have already been processed across runs.
In GitHub Actions, each run starts a fresh container, so this file must be
committed back to the repo at the end of every run (the workflow yml does this).
"""
import json
import os
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "applied_jobs.json")


def _load() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH) as f:
        return json.load(f)


def already_processed(board_token: str, job_id: int) -> bool:
    state = _load()
    return f"{board_token}:{job_id}" in state


def record(board_token: str, job_id: int, title: str, status: str, detail: str = ""):
    """
    status: one of 'applied', 'flagged_manual_review', 'failed'
    """
    state = _load()
    state[f"{board_token}:{job_id}"] = {
        "company": board_token,
        "job_id": job_id,
        "title": title,
        "status": status,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

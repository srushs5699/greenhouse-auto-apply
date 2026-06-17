import sys, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import main as main_module

def mock_job(job_id, title, content, minutes_ago=10):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    return {"id": job_id, "title": title, "content": content, "first_published": ts, "absolute_url": "x"}

targeting = {
    "role_keywords": ["Backend Engineer"],
    "signal_keywords_in_description": ["Kafka"],
    "min_years_experience": 1,
    "max_years_experience": 4,
    "match_mode": "title_or_description",
    "lookback_minutes": 60,
}

# Simulate Greenhouse returning the SAME job id twice (as seen in the wild with Instacart)
duplicate_job = mock_job(999, "Backend Engineer", "Kafka experience required")
main_module.fetch_greenhouse_jobs = lambda token: [duplicate_job, dict(duplicate_job)]
main_module.fetch_ashby_jobs = lambda name: None  # no ashby boards for this test
main_module.already_processed = lambda board, job_id: False  # nothing seen in prior runs

companies = {"greenhouse": ["testco"], "ashby": []}
matches = main_module.collect_matches(companies, targeting)

assert len(matches) == 1, f"Expected exactly 1 match after dedup, got {len(matches)}"
print("ALL DEDUP TESTS PASSED")

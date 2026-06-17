import sys, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from matcher import is_recently_posted, matches_role, filter_jobs

targeting = {
    "role_keywords": ["Backend Engineer", "Software Engineer"],
    "signal_keywords_in_description": ["Kafka", "RAG", "distributed systems"],
    "min_years_experience": 1,
    "max_years_experience": 4,
    "match_mode": "title_or_description",
    "lookback_minutes": 60,
}

def mock_job(title, content, minutes_ago):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    return {"id": 1, "title": title, "content": content, "first_published": ts, "absolute_url": "x"}

# Recent + title match
j1 = mock_job("Backend Engineer", "3+ years experience required", 30)
assert is_recently_posted(j1, 60) == True
assert matches_role(j1, targeting) == True

# Too old
j2 = mock_job("Backend Engineer", "3+ years experience required", 120)
assert is_recently_posted(j2, 60) == False

# Generic title (no keyword overlap), but description signal match
j3 = mock_job("Member of Technical Staff", "Experience with Kafka and distributed systems, 2+ years", 10)
assert matches_role(j3, targeting) == True

# Generic title, no signal, should fail
j4 = mock_job("Member of Technical Staff", "Frontend React role, 2+ years", 10)
assert matches_role(j4, targeting) == False

# Too senior - should be excluded
j5 = mock_job("Backend Engineer", "8+ years experience required", 10)
assert matches_role(j5, targeting) == False

# No years mentioned at all -> default include
j6 = mock_job("Backend Engineer", "Join our team building cool stuff", 10)
assert matches_role(j6, targeting) == True

print("ALL MATCHER TESTS PASSED")

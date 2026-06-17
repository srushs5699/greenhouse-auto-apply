import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ashby_client import normalize_job
from discover import find_tokens, GREENHOUSE_URL_RE, ASHBY_URL_RE

# Test Ashby job normalization
raw_job = {
    "title": "Backend Engineer",
    "descriptionPlain": "We need 2+ years experience with Kafka",
    "publishedAt": "2026-06-17T19:00:00.000+00:00",
    "jobUrl": "https://jobs.ashbyhq.com/acme/abc123",
    "applyUrl": "https://jobs.ashbyhq.com/acme/abc123/apply",
}
norm = normalize_job("acme", raw_job)
assert norm["title"] == "Backend Engineer"
assert norm["absolute_url"] == "https://jobs.ashbyhq.com/acme/abc123/apply"
assert norm["id"] == "apply"  # derived from URL since no explicit id given
assert norm["company_name"] == "acme"
assert norm["first_published"] == "2026-06-17T19:00:00.000+00:00"

# Test token extraction regexes used by discover.py
gh_urls = [
    "https://boards.greenhouse.io/stripe/jobs/12345",
    "https://job-boards.greenhouse.io/anthropic/jobs/999",
    "https://example.com/unrelated",
]
tokens = find_tokens(gh_urls, GREENHOUSE_URL_RE)
assert tokens == {"stripe", "anthropic"}

ashby_urls = ["https://jobs.ashbyhq.com/notion/xyz", "https://jobs.ashbyhq.com/ramp/abc"]
tokens2 = find_tokens(ashby_urls, ASHBY_URL_RE)
assert tokens2 == {"notion", "ramp"}

print("ALL ASHBY/DISCOVERY TESTS PASSED")

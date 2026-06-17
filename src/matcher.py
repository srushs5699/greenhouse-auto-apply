"""
matcher.py
Decides whether a fetched job is (a) recent enough and (b) relevant enough to apply to.
"""
import re
from datetime import datetime, timedelta, timezone
from html import unescape

# Strips HTML tags from Greenhouse's job description field (content=true returns raw HTML)
_TAG_RE = re.compile(r"<[^>]+>")

# Looks for patterns like "3+ years", "2-4 years", "minimum of 5 years"
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:-\s*(\d+)\s*)?\s*years?", re.IGNORECASE)


def strip_html(raw_html: str) -> str:
    return unescape(_TAG_RE.sub(" ", raw_html or ""))


def is_recently_posted(job: dict, lookback_minutes: int) -> bool:
    """
    Greenhouse jobs have 'first_published' (when it first went live) and 'updated_at'
    (changes if the listing is edited later). We use first_published so an old job
    that got a minor edit doesn't look "new".
    """
    ts = job.get("first_published") or job.get("updated_at")
    if not ts:
        return False
    try:
        posted_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    return posted_at >= cutoff


def matches_role(job: dict, targeting: dict) -> bool:
    title = (job.get("title") or "").lower()
    description = strip_html(job.get("content", "")).lower()

    role_keywords = [k.lower() for k in targeting.get("role_keywords", [])]
    signal_keywords = [k.lower() for k in targeting.get("signal_keywords_in_description", [])]
    mode = targeting.get("match_mode", "title_or_description")

    title_hit = any(k in title for k in role_keywords)
    description_hit = any(k in description for k in signal_keywords)

    if mode == "title_only":
        keyword_match = title_hit
    else:  # title_or_description - generic titles like "Software Engineer II" still match on signals
        keyword_match = title_hit or description_hit

    if not keyword_match:
        return False

    return _experience_in_range(description, targeting.get("min_years_experience", 0),
                                  targeting.get("max_years_experience", 99))


def _experience_in_range(description: str, min_years: int, max_years: int) -> bool:
    """
    Best-effort extraction of required years of experience from free text.
    Logic: include the job if the LOWEST experience figure mentioned is at or
    below your max_years - i.e. the role doesn't ask for more experience than
    you have. If we can't confidently parse a number, default to INCLUDING the
    job (better to flag for human review than silently skip a real match).
    """
    matches = _YEARS_RE.findall(description)
    if not matches:
        return True
    required_years = [int(low) for low, _ in matches]
    if not required_years:
        return True
    return min(required_years) <= max_years


def filter_jobs(jobs: list[dict], targeting: dict) -> list[dict]:
    lookback = targeting.get("lookback_minutes", 60)
    return [
        job for job in jobs
        if is_recently_posted(job, lookback) and matches_role(job, targeting)
    ]

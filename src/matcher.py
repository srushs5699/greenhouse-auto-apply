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

# Titles containing any of these are rejected outright, regardless of description
# content - a sales or PM job description can easily mention "Python" or "platform"
# once in passing without the role itself being engineering.
DEFAULT_TITLE_EXCLUDES = [
    "sales", "trader", "trading", "account executive", "business development",
    "product manager", "program manager", "project manager", "marketing",
    "recruiter", "recruiting", "talent acquisition", "customer success",
    "support specialist", "designer", "counsel", "attorney", "paralegal",
    "hr business partner", "people partner", "executive assistant", "office manager",
]

# When the title alone doesn't clearly indicate an engineering role, require at
# least this many distinct signal keywords in the description before matching -
# a single incidental mention isn't enough signal on its own.
MIN_DESCRIPTION_SIGNAL_HITS = 2


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

    exclude_keywords = [k.lower() for k in targeting.get("title_exclude_keywords", DEFAULT_TITLE_EXCLUDES)]
    if any(k in title for k in exclude_keywords):
        return False

    role_keywords = [k.lower() for k in targeting.get("role_keywords", [])]
    signal_keywords = [k.lower() for k in targeting.get("signal_keywords_in_description", [])]
    mode = targeting.get("match_mode", "title_or_description")

    title_hit = any(k in title for k in role_keywords)

    if mode == "title_only":
        keyword_match = title_hit
    elif title_hit:
        keyword_match = True
    else:
        # No clear engineering title - require multiple distinct signal hits,
        # not just one incidental mention, before treating this as a match.
        signal_hit_count = sum(1 for k in signal_keywords if k in description)
        keyword_match = signal_hit_count >= MIN_DESCRIPTION_SIGNAL_HITS

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

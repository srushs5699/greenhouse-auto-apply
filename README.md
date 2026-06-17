# Greenhouse Auto-Apply Pipeline

Polls a list of companies' public Greenhouse job boards, finds postings matching
your target role/experience that went live in the last hour, fills out the
application form, and (once you trust it) submits automatically.

## Important limitations - read first

- **Greenhouse and Ashby only.** Indeed and LinkedIn require login and aggressively
  block automation; this pipeline deliberately avoids both. It only works against
  companies that host their careers page on one of these two ATSs.
- **Auto-discovery is free and automatic again.** After Google Custom Search (closed
  to new users) and Brave (now paid) turned out to be dead ends, `src/discover_via_hn.py`
  uses the free, public Hacker News Algolia Search API to scan the monthly "Who is
  hiring?" thread for new Greenhouse/Ashby company links. No API key, no signup,
  no cost. It's bounded by what's posted in that thread rather than being a
  universal search, but those threads are dense with real startups/tech companies
  posting real ATS links, so it's a solid free source. You can still also just ask
  Claude in chat to research more companies anytime, on top of this.
- **Form structure varies slightly per company.** The filler matches fields by
  visible label text, which is fairly robust, but some companies' forms (custom
  questions, file upload quirks, occasional CAPTCHA) may not be fillable
  automatically. Those get flagged, not guessed.
- **This was built and reviewed for correctness but not run against live
  forms** (no internet access in the environment it was built in). Offline-testable
  logic (matching, normalization, URL parsing) has unit tests that pass; the
  network-dependent parts (API calls, the actual browser form filling) need
  testing against real postings. Use dry-run mode first.

## One-time setup

1. **Create a private or public GitHub repo** and push this folder to it.

2. **Validate your starting company list:**
   ```
   pip install -r requirements.txt
   python src/validate_boards.py
   ```
   Fix or remove any tokens reported invalid in `data/invalid_boards.json`.

3. **Fill in the salary placeholder** in `config/candidate_profile.json`
   (`screening_answers.salary_expectation`) - already set to "$120,000 minimum".

4. **Set up email notifications** (optional but recommended):
   - Generate a Gmail App Password: https://myaccount.google.com/apppasswords
   - In your GitHub repo: Settings -> Secrets and variables -> Actions -> New repository secret
     - `GMAIL_USER` = your Gmail address
     - `GMAIL_APP_PASSWORD` = the app password (not your normal Gmail password)

5. **Discovery just works, no setup needed.** `discover-companies.yml` runs once
   a day automatically once Actions is enabled - no keys, no secrets, no cost.

6. **Enable GitHub Actions** for the repo (Settings -> Actions -> Allow all actions).
   Both workflows will then run automatically (hourly apply, daily discovery),
   and you can also trigger either manually from the Actions tab.

## Testing locally before trusting it live

```
pip install -r requirements.txt
playwright install chromium
python src/main.py --dry-run
```

This fills out real forms on real postings but stops before clicking submit, so
you can open the flagged/previewed jobs yourself and sanity-check what it filled in.
Check your email (or terminal output) for the run summary.

When you're confident it's working correctly:
- Set `"dry_run": false` in `config/candidate_profile.json`, or
- Run a single live test manually first: `python src/main.py --live`

## How matching works

Edit `config/candidate_profile.json` -> `targeting`:
- `role_keywords`: matched against job titles
- `signal_keywords_in_description`: matched against the job description, so
  generic titles like "Software Engineer II" still match if the description
  mentions backend/AI/LLM signal terms
- `min_years_experience` / `max_years_experience`: best-effort regex match
  against years mentioned in the description (defaults to including the job
  if no clear number is found, rather than silently skipping it)

## Files

- `config/candidate_profile.json` - your info, screening answers, targeting rules
- `config/companies.json` - Greenhouse and Ashby boards to monitor (grow this on demand by asking Claude)
- `src/greenhouse_client.py` - reads the public Greenhouse API
- `src/ashby_client.py` - reads the public Ashby API, normalizes to a common job shape
- `src/matcher.py` - recency + relevance filtering (works on the normalized job shape from either ATS)
- `src/form_filler.py` - Playwright form filling/submission
- `src/state.py` - tracks what's already been applied to (persisted via git commit in CI)
- `src/notifier.py` - email summary after each run
- `src/main.py` - orchestrates all of the above
- `src/validate_boards.py` - checks which companies.json tokens actually resolve
- `src/discover_via_hn.py` - free automated discovery via the HN "Who is hiring?" thread
- `.github/workflows/hourly-apply.yml` - the hourly apply schedule
- `.github/workflows/discover-companies.yml` - daily discovery schedule (free, no setup needed)

# Greenhouse Auto-Apply Pipeline

Polls a list of companies' public Greenhouse job boards, finds postings matching
your target role/experience that went live in the last hour, fills out the
application form, and (once you trust it) submits automatically.

## Important limitations - read first

- **Greenhouse and Ashby only.** Indeed and LinkedIn require login and aggressively
  block automation; this pipeline deliberately avoids both. It only works against
  companies that host their careers page on one of these two ATSs.
- **Auto-discovery finds companies, not a global job search.** `discover.py` uses
  Google Custom Search to find new Greenhouse/Ashby boards matching your target
  roles and adds them to `config/companies.json` automatically. This gets you
  close to "every company Google has indexed on these platforms," but it's bounded
  by Google's index and free search quota - not literally every company everywhere.
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

5. **Set up auto-discovery (Google Custom Search API, free tier):**
   - Go to console.cloud.google.com, create a project (or use an existing one)
   - Enable the "Custom Search API" under APIs & Services -> Library
   - Create an API key under APIs & Services -> Credentials
   - Go to programmablesearchengine.google.com, create a new search engine,
     set it to "Search the entire web," and copy its Search Engine ID (cx)
   - Add both as GitHub repo secrets: `GOOGLE_API_KEY` and `GOOGLE_CSE_ID`
   - Free tier is 100 queries/day; the included schedule (every 6 hours, ~8
     queries per run) uses about 32/day, leaving headroom

6. **Enable GitHub Actions** for the repo (Settings -> Actions -> Allow all actions).
   Two workflows will then run automatically: the hourly apply pipeline, and
   the discovery job every 6 hours that grows `config/companies.json`.

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
- `config/companies.json` - Greenhouse and Ashby boards to monitor (auto-grown by discover.py)
- `src/greenhouse_client.py` - reads the public Greenhouse API
- `src/ashby_client.py` - reads the public Ashby API, normalizes to a common job shape
- `src/google_search.py` - free Google Custom Search API wrapper, used for discovery
- `src/discover.py` - finds new company boards matching your target roles, validates and adds them
- `src/matcher.py` - recency + relevance filtering (works on the normalized job shape from either ATS)
- `src/form_filler.py` - Playwright form filling/submission
- `src/state.py` - tracks what's already been applied to (persisted via git commit in CI)
- `src/notifier.py` - email summary after each run
- `src/main.py` - orchestrates all of the above
- `.github/workflows/hourly-apply.yml` - the hourly apply schedule
- `.github/workflows/discover-companies.yml` - the every-6-hours discovery schedule

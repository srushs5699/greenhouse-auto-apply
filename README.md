# Greenhouse Auto-Apply Pipeline

Polls a list of companies' public Greenhouse job boards, finds postings matching
your target role/experience that went live in the last hour, fills out the
application form, and (once you trust it) submits automatically.

## Important limitations - read first

- **Greenhouse only.** Indeed and LinkedIn require login and aggressively block
  automation; this pipeline deliberately avoids both. It only works against
  companies that host their careers page on Greenhouse.
- **No global "all Greenhouse jobs" search exists.** You're monitoring a fixed
  list of companies (`config/companies.json`), not the whole internet. Add more
  companies as you find them.
- **Form structure varies slightly per company.** The filler matches fields by
  visible label text, which is fairly robust, but some companies' forms (custom
  questions, file upload quirks, occasional CAPTCHA) may not be fillable
  automatically. Those get flagged, not guessed.
- **This was built and reviewed for correctness but not run against live
  Greenhouse forms** (no internet access in the environment it was built in).
  Test thoroughly in dry-run mode before flipping to live submission.

## One-time setup

1. **Create a private GitHub repo** and push this folder to it. Keep it private
   - your resume and contact info live in `config/`.

2. **Validate your company list:**
   ```
   pip install -r requirements.txt
   python src/validate_boards.py
   ```
   Fix or remove any tokens reported invalid in `data/invalid_boards.json`.

3. **Fill in the salary placeholder** in `config/candidate_profile.json`
   (`screening_answers.salary_expectation`).

4. **Set up email notifications** (optional but recommended):
   - Generate a Gmail App Password: https://myaccount.google.com/apppasswords
   - In your GitHub repo: Settings -> Secrets and variables -> Actions -> New repository secret
     - `GMAIL_USER` = your Gmail address
     - `GMAIL_APP_PASSWORD` = the app password (not your normal Gmail password)

5. **Enable GitHub Actions** for the repo (Settings -> Actions -> Allow all actions).
   The workflow in `.github/workflows/hourly-apply.yml` will then run every hour
   automatically, and you can also trigger it manually from the Actions tab.

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
- `config/companies.json` - companies (Greenhouse board tokens) to monitor
- `src/greenhouse_client.py` - reads the public Greenhouse API
- `src/matcher.py` - recency + relevance filtering
- `src/form_filler.py` - Playwright form filling/submission
- `src/state.py` - tracks what's already been applied to (persisted via git commit in CI)
- `src/notifier.py` - email summary after each run
- `src/main.py` - orchestrates all of the above
- `.github/workflows/hourly-apply.yml` - the hourly schedule

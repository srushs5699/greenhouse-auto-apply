"""
form_filler.py
Fills (and optionally submits) a Greenhouse application form using Playwright.

IMPORTANT: Greenhouse doesn't expose a public submission API for outside callers
(submission requires a per-company API key only the employer holds), so this has
to drive the actual browser-rendered form, the same as a human applicant would.
Form structure is fairly consistent across companies but not identical, so:
  - Known/common fields are matched by visible label text (robust to ID changes).
  - Anything we can't confidently match is FLAGGED, not guessed - we never submit
    a form with an unanswered required field.
  - dry_run=True (recommended for the first many runs) fills everything and stops
    right before clicking the final submit button.
"""
from playwright.sync_api import Page, TimeoutError as PWTimeout

LABEL_ALIASES = {
    "first_name": ["First Name"],
    "last_name": ["Last Name"],
    "email": ["Email"],
    "phone": ["Phone"],
    "linkedin": ["LinkedIn Profile", "LinkedIn"],
    "github": ["GitHub", "Github Profile"],
    "portfolio": ["Website", "Portfolio", "Personal Website"],
    "cover_letter": ["Cover Letter"],
}

# Keyword -> profile field, used for screening questions whose labels vary per company
SCREENING_KEYWORD_MAP = [
    (["authorized to work"], "authorized_to_work_us"),
    (["require sponsorship", "sponsorship now or in the future", "visa sponsorship"],
     "requires_sponsorship_now_or_future"),
    (["notice period", "available to start", "start date"], "notice_period"),
    (["salary", "compensation expectation", "expected pay"], "salary_expectation"),
    (["relocate"], "willing_to_relocate"),
]

EEO_KEYWORDS = ["race", "ethnicity", "gender", "veteran", "disability", "pronoun", "sexual orientation"]
DECLINE_OPTION_TEXTS = ["Decline to answer", "I don't wish to answer", "Prefer not to answer",
                         "I do not wish to disclose"]


def _try_fill_by_label(page: Page, label_options: list[str], value: str) -> bool:
    for label in label_options:
        try:
            field = page.get_by_label(label, exact=False)
            if field.count() > 0:
                field.first.fill(str(value))
                return True
        except (PWTimeout, Exception):
            continue
    return False


def _try_select_decline(page: Page, label_substring: str) -> bool:
    """For EEO dropdowns, select a 'decline to answer' style option if present."""
    try:
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            label_text = ""
            try:
                label_text = sel.evaluate(
                    "el => el.closest('.field')?.innerText || el.labels?.[0]?.innerText || ''"
                )
            except Exception:
                pass
            if label_substring.lower() in label_text.lower():
                options = sel.locator("option").all_inner_texts()
                for decline_text in DECLINE_OPTION_TEXTS:
                    match = next((o for o in options if decline_text.lower() in o.lower()), None)
                    if match:
                        sel.select_option(label=match)
                        return True
        return False
    except Exception:
        return False


def apply_to_job(browser, job: dict, profile: dict, dry_run: bool = True) -> dict:
    """
    Returns {"status": "applied" | "dry_run_preview" | "flagged_manual_review" | "failed",
             "detail": str}
    """
    personal = profile["personal"]
    screening = profile["screening_answers"]
    unmatched_required = []

    page = browser.new_page()
    try:
        page.goto(job["absolute_url"], timeout=30000)

        _try_fill_by_label(page, LABEL_ALIASES["first_name"], personal["full_name"].split()[0])
        _try_fill_by_label(page, LABEL_ALIASES["last_name"], " ".join(personal["full_name"].split()[1:]) or "Shinde")
        _try_fill_by_label(page, LABEL_ALIASES["email"], personal["email"])
        _try_fill_by_label(page, LABEL_ALIASES["phone"], personal["phone"])
        _try_fill_by_label(page, LABEL_ALIASES["linkedin"], personal["linkedin_url"])
        _try_fill_by_label(page, LABEL_ALIASES["github"], personal["github_url"])
        _try_fill_by_label(page, LABEL_ALIASES["portfolio"], personal["portfolio_url"])

        # Resume upload - first file input on a Greenhouse form is virtually always resume
        try:
            file_inputs = page.locator('input[type="file"]')
            if file_inputs.count() > 0:
                file_inputs.first.set_input_files(personal["resume_path"])
        except Exception:
            unmatched_required.append("resume_upload_failed")

        # Cover letter (templated, lightly customized)
        cover_letter_text = profile["cover_letter"]["template"].format(
            job_title=job.get("title", "this role"),
            company_name=job.get("company_name", "your team"),
        )
        _try_fill_by_label(page, LABEL_ALIASES["cover_letter"], cover_letter_text)

        # EEO questions - decline by default
        for keyword in EEO_KEYWORDS:
            _try_select_decline(page, keyword)

        # Common screening questions matched by label keyword
        all_labels = page.locator("label").all_inner_texts()
        for label_text in all_labels:
            lt = label_text.lower()
            for keywords, profile_key in SCREENING_KEYWORD_MAP:
                if any(k in lt for k in keywords):
                    value = screening.get(profile_key)
                    if value is None or value == "PLACEHOLDER_FILL_ME_IN":
                        unmatched_required.append(label_text.strip())
                        continue
                    answer = "Yes" if value is True else "No" if value is False else str(value)
                    try:
                        page.get_by_label(label_text, exact=True).first.fill(answer)
                    except Exception:
                        try:
                            page.get_by_label(label_text, exact=True).first.select_option(label=answer)
                        except Exception:
                            unmatched_required.append(label_text.strip())

        # Check for any REQUIRED inputs still empty that we haven't accounted for
        required_inputs = page.locator("input[required], select[required], textarea[required]")
        for i in range(required_inputs.count()):
            el = required_inputs.nth(i)
            try:
                if el.input_value().strip() == "":
                    name_attr = el.get_attribute("name") or el.get_attribute("id") or "unknown_field"
                    if name_attr not in unmatched_required:
                        unmatched_required.append(name_attr)
            except Exception:
                continue

        if unmatched_required:
            return {
                "status": "flagged_manual_review",
                "detail": f"Unmatched required fields: {unmatched_required}",
            }

        if dry_run:
            return {"status": "dry_run_preview", "detail": "Form filled, submit NOT clicked (dry_run=True)."}

        submit_button = page.get_by_role("button", name="Submit Application")
        if submit_button.count() == 0:
            return {"status": "flagged_manual_review", "detail": "Could not locate submit button."}
        submit_button.first.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        return {"status": "applied", "detail": "Submitted."}

    except Exception as e:
        return {"status": "failed", "detail": str(e)}
    finally:
        page.close()

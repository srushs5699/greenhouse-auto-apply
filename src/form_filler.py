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

# Ashby renders its own standard fields using a stable "_systemfield_*" name/id
# convention rather than Greenhouse-style <label> text, so the label-based
# aliases above don't match them. These selectors are Ashby's documented
# system field naming pattern and apply across all Ashby-hosted boards.
# https://developers.ashbyhq.com - Ashby job application form fields use
# _systemfield_name, _systemfield_email, _systemfield_phone,
# _systemfield_location, _systemfield_resume as consistent identifiers.
ASHBY_SYSTEMFIELD_SELECTORS = {
    "full_name": '[name="_systemfield_name"], #_systemfield_name',
    "email": '[name="_systemfield_email"], #_systemfield_email',
    "phone": '[name="_systemfield_phone"], #_systemfield_phone',
    "location": '[name="_systemfield_location"], #_systemfield_location',
    "resume": '[name="_systemfield_resume"], #_systemfield_resume, [id="_systemfield_resume"]',
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


def _try_fill_ashby_systemfield(page: Page, selector: str, value: str) -> bool:
    """Fill an Ashby _systemfield_* input/textarea by CSS selector. Returns True on success."""
    try:
        field = page.locator(selector)
        if field.count() > 0:
            field.first.fill(str(value))
            return True
    except Exception:
        pass
    return False


def _try_upload_resume(page: Page, resume_path: str) -> tuple[bool, str]:
    """
    Try Ashby's named resume field first (works even when it's wrapped in a
    drag-and-drop UI, since the underlying <input type="file"> still accepts
    set_input_files directly regardless of how it's styled). Falls back to
    the first generic file input on the page (the Greenhouse pattern, where
    resume is virtually always the first file input).

    Returns (success, detail) - detail explains *why* on failure, since a
    silent resume-upload failure is costly (it blocks every single
    application, not just one edge-case question) and the previous version
    swallowed the real exception entirely, making this impossible to debug
    from flagged output alone.
    """
    import os
    if not os.path.isfile(resume_path):
        cwd = os.getcwd()
        return False, f"resume_path '{resume_path}' does not exist (cwd={cwd})"

    last_error = None
    try:
        ashby_resume = page.locator(ASHBY_SYSTEMFIELD_SELECTORS["resume"])
        if ashby_resume.count() > 0:
            ashby_resume.first.set_input_files(resume_path)
            return True, "uploaded via Ashby systemfield selector"
    except Exception as e:
        last_error = f"Ashby selector attempt failed: {e}"

    try:
        file_inputs = page.locator('input[type="file"]')
        count = file_inputs.count()
        if count > 0:
            file_inputs.first.set_input_files(resume_path)
            return True, "uploaded via generic file input"
        else:
            last_error = f"no input[type=file] found on page (Ashby attempt: {last_error})"
    except Exception as e:
        last_error = f"generic file input attempt failed: {e} (Ashby attempt: {last_error})"

    return False, last_error or "unknown failure"


def _try_answer_yes_no_buttons(page: Page, label_text: str, answer: str) -> bool:
    """
    Ashby renders yes/no screening questions as a pair of plain <button>
    elements with a hidden checkbox input, not a real <select> or text
    <input>, so neither .fill() nor .select_option() can touch them:

        <label for="...">Question text</label>
        <div class="_container..._yesno_...">
          <button class="_option...">Yes</button>
          <button class="_option...">No</button>
          <input type="checkbox" tabindex="-1" name="...">
        </div>

    The label's "for" attribute doesn't point at either button (it points at
    the hidden checkbox), so get_by_label() can't find them either. Instead,
    locate the <label> by its exact text, walk up to its immediate field
    container, then click the <button> whose own text matches the answer.
    """
    try:
        label = page.locator("label").get_by_text(label_text, exact=True)
        if label.count() == 0:
            return False

        field_entry = label.first.locator(
            "xpath=ancestor::div[contains(@class, '_fieldEntry')][1]"
        )
        if field_entry.count() == 0:
            field_entry = label.first.locator("xpath=..")

        button = field_entry.get_by_role("button", name=answer, exact=True)
        if button.count() == 0:
            button = field_entry.get_by_text(answer, exact=True)
        if button.count() > 0:
            button.first.click()
            # Verify the click actually registered. Ashby's hidden checkbox
            # for this field type has no 'required' HTML attribute (Ashby
            # validates it via its own JS at submit time), so the generic
            # catch-all required-field scan elsewhere in this file can't
            # detect a silently-failed click here. Check explicitly instead
            # of assuming the click worked.
            try:
                checkbox = field_entry.locator('input[type="checkbox"]')
                if checkbox.count() > 0:
                    return checkbox.first.is_checked()
            except Exception:
                pass
            return True
    except Exception:
        pass
    return False


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


def _describe_unmatched_field(el) -> str:
    """
    Build a human-readable descriptor for a required field we couldn't fill,
    so flagged_manual_review output tells you *what* the field is instead of
    just 'unknown_field'. Tries, in order: name/id attrs, aria-label,
    placeholder, a <label for=...> match, and finally the visible text of the
    nearest ancestor container (covers custom-rendered widgets with no
    standard label association).
    """
    try:
        name_attr = el.get_attribute("name")
        id_attr = el.get_attribute("id")
        aria_label = el.get_attribute("aria-label")
        placeholder = el.get_attribute("placeholder")
        field_type = el.get_attribute("type") or el.evaluate("el => el.tagName.toLowerCase()")

        nearby_text = ""
        try:
            nearby_text = el.evaluate(
                """el => {
                    const container = el.closest('.field, .application-question, fieldset, div[class*="question"]') || el.parentElement;
                    if (!container) return '';
                    return container.innerText.trim().slice(0, 120);
                }"""
            )
        except Exception:
            pass

        parts = []
        if name_attr:
            parts.append(f"name={name_attr}")
        if id_attr:
            parts.append(f"id={id_attr}")
        if aria_label:
            parts.append(f"aria-label='{aria_label}'")
        if placeholder:
            parts.append(f"placeholder='{placeholder}'")
        parts.append(f"type={field_type}")
        if nearby_text:
            parts.append(f"nearby_text='{nearby_text}'")

        return "unknown_field(" + ", ".join(parts) + ")" if parts else "unknown_field(no attributes found)"
    except Exception as e:
        return f"unknown_field(descriptor_error: {e})"


def apply_to_job(browser, job: dict, profile: dict, dry_run: bool = True) -> dict:
    """
    Returns {"status": "applied" | "dry_run_preview" | "flagged_manual_review" | "failed",
             "detail": str}
    """
    personal = profile["personal"]
    screening = profile["screening_answers"]
    unmatched_required = []

    page = browser.new_page()
    page.set_default_timeout(30000)  # caps every Playwright action at 30s so a single
    # stuck selector/overlay/iframe can't silently hang the whole run - it'll raise
    # and get caught by the except block below instead, recorded as 'failed'.
    try:
        page.goto(job["absolute_url"], timeout=30000)

        # Try Ashby's combined full-name systemfield first; if that's not
        # present (i.e. this is a Greenhouse-style form with separate
        # First/Last Name fields), fall back to the label-based approach.
        if not _try_fill_ashby_systemfield(page, ASHBY_SYSTEMFIELD_SELECTORS["full_name"], personal["full_name"]):
            _try_fill_by_label(page, LABEL_ALIASES["first_name"], personal["full_name"].split()[0])
            _try_fill_by_label(page, LABEL_ALIASES["last_name"], " ".join(personal["full_name"].split()[1:]) or "Shinde")

        if not _try_fill_ashby_systemfield(page, ASHBY_SYSTEMFIELD_SELECTORS["email"], personal["email"]):
            _try_fill_by_label(page, LABEL_ALIASES["email"], personal["email"])

        if not _try_fill_ashby_systemfield(page, ASHBY_SYSTEMFIELD_SELECTORS["phone"], personal["phone"]):
            _try_fill_by_label(page, LABEL_ALIASES["phone"], personal["phone"])

        _try_fill_by_label(page, LABEL_ALIASES["linkedin"], personal["linkedin_url"])
        _try_fill_by_label(page, LABEL_ALIASES["github"], personal["github_url"])
        _try_fill_by_label(page, LABEL_ALIASES["portfolio"], personal["portfolio_url"])

        # Resume upload - tries Ashby's named field first, then falls back to
        # the first generic file input (the Greenhouse pattern).
        resume_ok, resume_detail = _try_upload_resume(page, personal["resume_path"])
        if not resume_ok:
            unmatched_required.append(f"resume_upload_failed: {resume_detail}")

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
                            if not _try_answer_yes_no_buttons(page, label_text, answer):
                                unmatched_required.append(label_text.strip())

        # Check for any REQUIRED inputs still empty that we haven't accounted for
        required_inputs = page.locator("input[required], select[required], textarea[required]")
        for i in range(required_inputs.count()):
            el = required_inputs.nth(i)
            try:
                if el.input_value().strip() == "":
                    descriptor = _describe_unmatched_field(el)
                    if descriptor not in unmatched_required:
                        unmatched_required.append(descriptor)
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

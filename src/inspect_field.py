"""
inspect_field.py
One-time diagnostic: dumps the actual rendered HTML around specific
screening-question labels on a live job posting, so we can see exactly
what kind of element ('Are you authorized to work...') really is instead
of guessing. Run this against one OpenAI URL and one Replit URL.

Usage:
    python src/inspect_field.py "<job_url>"
"""
import sys
from playwright.sync_api import sync_playwright

TARGET_LABEL_SNIPPETS = [
    "authorized to work",
    "require sponsorship",
    "Pick date",
    "relocate",
]


def main(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        try:
            page.wait_for_selector("#form", timeout=15000)
        except Exception:
            print("WARNING: #form selector never appeared - page may not have loaded the application form.")
        page.wait_for_timeout(2000)  # extra settle time for late-mounting fields

        for snippet in TARGET_LABEL_SNIPPETS:
            print(f"\n{'='*70}\nSearching for: '{snippet}'\n{'='*70}")
            try:
                loc = page.locator(f"text={snippet}")
                count = loc.count()
                print(f"Found {count} element(s) containing this text.")
                if count > 0:
                    # First show the SMALLEST element containing the text directly
                    # (its own tag/outerHTML, no ancestor walk) - this tells us
                    # exactly what kind of node holds the label text itself.
                    own_html = loc.first.evaluate("el => el.outerHTML")
                    print(f"--- Element itself (tag: {loc.first.evaluate('el => el.tagName')}) ---")
                    print(own_html[:500])

                    # Then walk up just 1 and 2 levels (not 4) to see the
                    # immediate question wrapper, which is where the actual
                    # input/radio/button for this question should live.
                    for levels in (1, 2):
                        try:
                            ancestor_html = loc.first.evaluate(
                                f"""el => {{
                                    let node = el;
                                    for (let i = 0; i < {levels} && node.parentElement; i++) {{
                                        node = node.parentElement;
                                    }}
                                    return node.outerHTML;
                                }}"""
                            )
                            print(f"\n--- {levels} level(s) up (truncated to 800 chars) ---")
                            print(ancestor_html[:800])
                        except Exception as e:
                            print(f"  (error walking up {levels} levels: {e})")
            except Exception as e:
                print(f"Error: {e}")

        browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/inspect_field.py <job_url>")
        sys.exit(1)
    main(sys.argv[1])

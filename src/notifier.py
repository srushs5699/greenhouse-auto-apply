"""
notifier.py
Sends a summary email after each run. Reads credentials from environment
variables (set as GitHub Actions secrets, or your shell env if running locally)
so nothing sensitive lives in code.

Required env vars:
  GMAIL_USER            - the Gmail address sending from
  GMAIL_APP_PASSWORD    - a Gmail App Password (NOT your normal password -
                           generate one at https://myaccount.google.com/apppasswords)
"""
import os
import smtplib
from email.mime.text import MIMEText


def send_summary_email(to_address: str, results: list[dict]):
    user = os.environ.get("GMAIL_USER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not app_password:
        print("[notifier] GMAIL_USER / GMAIL_APP_PASSWORD not set - skipping email, printing summary instead.")
        _print_summary(results)
        return

    applied = [r for r in results if r["result"]["status"] == "applied"]
    previewed = [r for r in results if r["result"]["status"] == "dry_run_preview"]
    flagged = [r for r in results if r["result"]["status"] == "flagged_manual_review"]
    failed = [r for r in results if r["result"]["status"] == "failed"]

    lines = [f"Greenhouse auto-apply run summary - {len(results)} matching job(s) found.\n"]
    if applied:
        lines.append(f"APPLIED ({len(applied)}):")
        lines += [f"  - {r['job']['title']} @ {r['company']}: {r['job']['absolute_url']}" for r in applied]
    if previewed:
        lines.append(f"\nDRY RUN PREVIEW - not submitted ({len(previewed)}):")
        lines += [f"  - {r['job']['title']} @ {r['company']}: {r['job']['absolute_url']}" for r in previewed]
    if flagged:
        lines.append(f"\nFLAGGED FOR MANUAL REVIEW ({len(flagged)}):")
        lines += [f"  - {r['job']['title']} @ {r['company']}: {r['result']['detail']} -> {r['job']['absolute_url']}"
                   for r in flagged]
    if failed:
        lines.append(f"\nFAILED ({len(failed)}):")
        lines += [f"  - {r['job']['title']} @ {r['company']}: {r['result']['detail']}" for r in failed]
    if not results:
        lines.append("No new matching postings in the last hour.")

    body = "\n".join(lines)
    msg = MIMEText(body)
    msg["Subject"] = f"Greenhouse auto-apply: {len(applied)} applied, {len(flagged)} flagged"
    msg["From"] = user
    msg["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, app_password)
        server.sendmail(user, [to_address], msg.as_string())


def _print_summary(results: list[dict]):
    for r in results:
        print(f"{r['result']['status']:25s} {r['company']:15s} {r['job']['title']}")

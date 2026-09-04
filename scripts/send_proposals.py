#!/usr/bin/env python3
"""
Auto Email Sender — Sends proposals via Gmail
==============================================
Called by GitHub Actions or manually.
Uses GMAIL_APP_PASSWORD from environment.
"""
import smtplib, os, json, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Config
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM_EMAIL = "sparkbountybot@gmail.com"

# Get app password from env (GitHub Actions injects this)
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# File paths
MANIFEST_PATH = "/sandbox/new/data/bounty_manifest.json"
SENT_LOG_PATH = "/sandbox/new/data/sent_log.json"


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {}


def load_sent_log():
    if os.path.exists(SENT_LOG_PATH):
        with open(SENT_LOG_PATH) as f:
            return json.load(f)
    return {
        "timestamp": "",
        "total_sent": 0,
        "total_failed": 0,
        "sent": [],
        "failed": [],
    }


def send_email(to_email, subject, body, manifest_entry=None):
    """Send a single email via Gmail SMTP"""
    if not GMAIL_APP_PASSWORD:
        return {"success": False, "message": "No GMAIL_APP_PASSWORD configured"}

    try:
        msg = MIMEMultipart()
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(FROM_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        result = {"success": True, "message": "Sent successfully"}
        if manifest_entry:
            result["reward"] = manifest_entry.get("reward", 0)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


def send_all_proposals():
    """Send all proposals from manifest"""
    manifest = load_manifest()
    if not manifest.get("proposals"):
        print("No proposals in manifest")
        return {"total_sent": 0, "total_failed": 0}

    # Track what's already sent
    sent_log = load_sent_log()
    already_sent = set()
    for s in sent_log.get("sent", []):
        key = f"{s.get('repo', '')}/{s.get('issue', '')}"
        already_sent.add(key)

    sent = []
    failed = []
    total_sent = 0
    total_failed = 0

    for p in manifest["proposals"]:
        email_to = p.get("email_to", [])
        if not email_to:
            failed.append({
                "repo": p.get("repo", ""),
                "issue": p.get("issue", ""),
                "title": p.get("title", ""),
                "reason": "No email address",
            })
            total_failed += 1
            continue

        # Check if we've already sent to this bounty
        key = f"{p.get('repo', '')}/{p.get('issue', '')}"
        if key in already_sent:
            print(f"  Skipping (already sent): {p['title'][:40]}")
            continue

        # Send to first email
        email = email_to[0] if isinstance(email_to, list) else email_to
        subject = p.get("email_subject", "Proposal")
        body = p.get("email_body", "Proposal")

        print(f"  Sending to {email}...")
        result = send_email(email, subject, body, p)

        if result["success"]:
            sent.append({
                "repo": p.get("repo", ""),
                "issue": p.get("issue", ""),
                "email": email,
                "title": p.get("title", ""),
                "reward": p.get("reward", 0),
                "message": "Sent successfully",
            })
            total_sent += 1
            print(f"    ✅ Success")
        else:
            failed.append({
                "repo": p.get("repo", ""),
                "issue": p.get("issue", ""),
                "email": email,
                "title": p.get("title", ""),
                "message": result.get("message", "Unknown error"),
            })
            total_failed += 1
            print(f"    ❌ {result.get('message', 'Unknown error')}")

    # Save updated sent log
    sent_log = {
        "timestamp": datetime.now().isoformat(),
        "total_sent": total_sent,
        "total_failed": total_failed,
        "sent": sent,
        "failed": failed,
    }

    with open(SENT_LOG_PATH, "w") as f:
        json.dump(sent_log, f, indent=2)

    # Update manifest status
    manifest["status"] = "sent"
    manifest["action_taken"] = "email_sent"
    manifest["sent_count"] = total_sent
    manifest["failed_count"] = total_failed

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    return {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "sent": sent,
        "failed": failed,
    }


if __name__ == "__main__":
    print("=" * 70)
    print("  AUTO EMAIL SENDER — Gmail SMTP Pipeline")
    print("=" * 70)

    result = send_all_proposals()

    print("\n" + "=" * 70)
    print(f"  RESULTS: {result['total_sent']} sent, {result['total_failed']} failed")
    print("=" * 70)

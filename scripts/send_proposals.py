#!/usr/bin/env python3
"""
Bounty Proposal Email Sender
=============================
Reads proposal manifest from the repo and sends emails via Gmail SMTP.
Designed to run in GitHub Actions where Gmail is NOT blocked.

Environment variables (from GitHub Secrets):
  GMAIL_EMAIL - sparkbountybot@gmail.com
  GMAIL_APP_PASSWORD - Gmail App Password (not the account password)
"""
import json
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Configuration from environment
GMAIL_EMAIL = os.environ.get('GMAIL_EMAIL', 'sparkbountybot@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

def send_email(to_email, subject, body):
    """Send email via Gmail SMTP"""
    if not GMAIL_APP_PASSWORD:
        return False, "No Gmail App Password configured"

    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject

    # Create HTML and plain text versions
    msg.attach(MIMEText(body, 'html'))
    msg.attach(MIMEText(body.replace('<br>', '\n').replace('</p>', '\n\n').replace('<p>', ''), 'plain'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_EMAIL, to_email, msg.as_string())
        server.quit()
        return True, "Sent successfully"
    except Exception as e:
        return False, str(e)

def read_proposal_file(filepath):
    """Read a proposal file and extract email content"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        # Extract the email body (between --- markers or the main content)
        body = content
        for line in content.split('\n'):
            if line.startswith('# '):
                continue
            if line.startswith('---'):
                continue
            body = content.split('---\n')[-1] if '---\n' in content else content
            break

        # Extract subject from filename pattern or content
        subject = f"Bounty Proposal: {os.path.basename(filepath)}"

        return subject, body
    except Exception as e:
        return None, f"Error reading {filepath}: {e}"

def main():
    print("=" * 60)
    print("  BOUNTY PROPOSAL EMAIL SENDER")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)
    print()

    # Read manifest
    manifest_path = Path('data/bounty_manifest.json')
    if not manifest_path.exists():
        print("ERROR: No manifest found. Run bounty_hunter.py first.")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    proposals = manifest.get('proposals', [])
    print(f"Found {len(proposals)} proposals in manifest")
    print()

    if not proposals:
        print("No proposals to send.")
        sys.exit(0)

    # Send emails
    sent = []
    failed = []

    for prop in proposals:
        email_to = prop.get('email_to', [])
        if not email_to:
            print(f"⚠️  {prop['title'][:40]}: No email address found")
            failed.append({
                'repo': prop['repo'],
                'issue': prop['issue'],
                'title': prop['title'],
                'reason': 'No email address'
            })
            continue

        # Try the first email address
        to_email = email_to[0] if isinstance(email_to, list) else email_to

        print(f"📧 Sending to {to_email}...")
        print(f"   Repo: {prop['repo']}/{prop['issue']}")
        print(f"   Title: {prop['title'][:50]}")
        print(f"   Reward: ${prop['reward']}{'K' if prop['reward'] >= 1000 else ''}" if prop['reward'] else "   Reward: As listed")

        # Read full proposal from file
        proposal_file = prop.get('file', '')
        if proposal_file and Path(proposal_file).exists():
            subject, body = read_proposal_file(proposal_file)
        else:
            subject = prop.get('email_subject', f'Proposal for {prop["repo"]} #{prop["issue"]}')
            body = prop.get('email_body', f'Proposal for {prop["repo"]} #{prop["issue"]}')

        success, message = send_email(to_email, subject, body)

        if success:
            print(f"   ✅ SENT!")
            sent.append({
                'repo': prop['repo'],
                'issue': prop['issue'],
                'email': to_email,
                'title': prop['title'],
                'reward': prop['reward'],
                'message': message
            })
        else:
            print(f"   ❌ FAILED: {message}")
            failed.append({
                'repo': prop['repo'],
                'issue': prop['issue'],
                'email': to_email,
                'title': prop['title'],
                'message': message
            })

        print()

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_sent': len(sent),
        'total_failed': len(failed),
        'sent': sent,
        'failed': failed,
    }

    results_path = Path('data/sent_log.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print("=" * 60)
    print(f"RESULTS: {len(sent)} sent, {len(failed)} failed")
    print("=" * 60)

    if sent:
        print("\n✅ Successfully sent emails:")
        for s in sent:
            print(f"   → {s['email']}: {s['title'][:40]}...")

    if failed:
        print("\n❌ Failed to send:")
        for f in failed:
            print(f"   → {f['email']}: {f.get('message', 'Unknown error')}")

    # Return appropriate exit code
    if sent and not failed:
        print("\n🎉 All emails sent successfully!")
    elif sent:
        print(f"\n⚠️  {len(sent)} sent, {len(failed)} failed")
    else:
        print("\n❌ No emails sent")
        sys.exit(1)

if __name__ == '__main__':
    main()

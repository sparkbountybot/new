"""
Gmail Monitor — Scans Gmail for invoices, payments, and billing alerts.
Uses IMAP to scan inbox and creates alerts based on search terms.
"""
import os, re, imaplib
from email import policy
from email.parser import BytesParser
from datetime import datetime
from config import load_state, save_state


class GmailMonitor:
    """Monitors Gmail for invoices, payments, and billing alerts."""

    def __init__(self, config=None):
        self.config = config or {}
        gmail = self.config.get("gmail", {})
        self.email = gmail.get("email", "")
        self.password = gmail.get("password", "")
        self.check_interval = gmail.get("check_interval_seconds", 300)
        self.search_terms = gmail.get("search_terms", "payment OR invoice OR unpaid OR billing OR due")

        if not self.email or not self.password:
            self.connected = False
            print("  WARNING: Gmail not configured. Set GMAIL_EMAIL and GMAIL_PASSWORD.")
            return
        self.connected = True

    def connect(self):
        """Connect to Gmail IMAP."""
        if not self.connected:
            return False
        try:
            self.imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            self.imap.login(self.email, self.password)
            self.imap.select("INBOX")
            return True
        except Exception as e:
            print(f"  Gmail connection error: {e}")
            self.connected = False
            return False

    def scan(self) -> list:
        """Scan Gmail inbox for matching emails."""
        print("\n=== Gmail Monitor ===")

        if not self.connect():
            return []

        # Search for matching emails
        terms = self.search_terms.split()
        alerts = []

        for term in terms:
            try:
                status, messages = self.imap.search(None, f'(SUBJECT "{term}")')
                if status != "OK" or not messages[0]:
                    continue

                msg_ids = messages[0].split()
                print(f"  Found {len(msg_ids)} emails matching '{term}'")

                for msg_id in msg_ids[-10:]:  # Last 10 matches
                    status, msg_data = self.imap.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data:
                        continue

                    raw_email = msg_data[0][1]
                    msg = BytesParser(policy=policy.default).parsebytes(raw_email)

                    subject = msg.get("Subject", "No subject")
                    from_addr = msg.get("From", "unknown")
                    date_str = msg.get("Date", "")
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body += payload.decode("utf-8", errors="ignore")
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")

                    # Check if already alerted
                    state = load_state("alerts")
                    existing_subjects = {a.get("subject", "") for a in state.get("alerts", [])}

                    if subject not in existing_subjects:
                        alert = {
                            "subject": subject,
                            "from": from_addr,
                            "date": date_str,
                            "body_preview": body[:500],
                            "term": term,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        alerts.append(alert)

            except Exception as e:
                print(f"  Error scanning for '{term}': {e}")

        # Save alerts
        if alerts:
            state = load_state("alerts")
            all_alerts = state.get("alerts", [])
            all_alerts.extend(alerts)
            save_state("alerts", {"alerts": all_alerts})

            print(f"\n  New alerts: {len(alerts)}")
            for a in alerts[:3]:
                print(f"    [{a['date'][:10]}] {a['subject']}")
        else:
            print("  No new alerts.")

        return alerts

    def get_alerts(self) -> list:
        """Get current alerts."""
        state = load_state("alerts")
        return state.get("alerts", [])

"""
Email Sender — Sends reports and notifications via Gmail or SendGrid.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class EmailSender:
    """Sends email reports via Gmail SMTP or SendGrid API."""

    def __init__(self, config=None):
        self.config = config or {}
        email_cfg = self.config.get("email", {})
        sendgrid_cfg = self.config.get("sendgrid", {})

        self.from_email = email_cfg.get("from_email", "")
        self.from_name = email_cfg.get("from_name", "BountyBot")
        self.sendgrid_key = sendgrid_cfg.get("api_key", "") or self.config.get("email", {}).get("sendgrid_api_key", "")

        self.gmail_smtp = "smtp.gmail.com:587"
        self.gmail_user = self.config.get("gmail", {}).get("email", "")
        self.gmail_pass = self.config.get("gmail", {}).get("password", "")

        self.connected = bool(self.sendgrid_key or (self.gmail_user and self.gmail_pass))

    def send_report(self, subject: str, body: str, recipient: str = None) -> bool:
        """Send a text report email."""
        if not self.connected:
            print("  ERROR: No email configuration. Cannot send reports.")
            return False

        recipient = recipient or self.from_email

        if self.sendgrid_key:
            return self._send_via_sendgrid(subject, body, recipient)
        else:
            return self._send_via_gmail(subject, body, recipient)

    def _send_via_sendgrid(self, subject, body, recipient) -> bool:
        """Send via SendGrid API."""
        try:
            import requests
            payload = {
                "personalizations": [{"to": [{"email": recipient}]}],
                "from": {"email": self.from_email, "name": self.from_name},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            }
            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={"Authorization": f"Bearer {self.sendgrid_key}", "Content-Type": "application/json"},
                timeout=30,
            )
            if resp.status_code == 202:
                print(f"  Email sent via SendGrid to {recipient}")
                return True
            else:
                print(f"  SendGrid error: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"  SendGrid error: {e}")
            return False

    def _send_via_gmail(self, subject, body, recipient) -> bool:
        """Send via Gmail SMTP."""
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(self.gmail_smtp)
            server.starttls()
            server.login(self.gmail_user, self.gmail_pass)
            server.sendmail(self.from_email, recipient, msg.as_string())
            server.quit()

            print(f"  Email sent via Gmail to {recipient}")
            return True
        except Exception as e:
            print(f"  Gmail SMTP error: {e}")
            return False

    def send_test(self) -> bool:
        """Send a test email."""
        body = f"""BountyBot Test Email
Generated: {datetime.utcnow().isoformat()}

This is a test email from BountyBot Framework v2.
If you received this, email sending is working correctly.

System Status:
- GitHub: Connected
- Trading: Configured
- Alerts: Monitoring
"""
        return self.send_report("BountyBot Test Email", body)

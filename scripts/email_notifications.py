#!/usr/bin/env python3
"""
Email Notifications — Auto-send alerts via Gmail

Workflow:
1. Monitor inbox for new messages
2. Score incoming emails (bounties, proposals, alerts)
3. Generate responses if needed
4. Send emails via Himalaya on host

Usage:
  python3 scripts/email_notifications.py monitor   # Check inbox
  python3 scripts/email_notifications.py notify    # Send alert
  python3 scripts/email_notifications.py respond   # Auto-respond
"""

import os
import json
import subprocess
import re
from datetime import datetime, timedelta

EMAIL_CONFIG = {
    "from_email": "sparkbountybot@gmail.com",
    "gmail_password": "depkknmtmxyytohp",
    "telegram_chat_id": "8403524679",
    "bot_token": "8879739093:AAHHIDDEN",  # Replace with actual token
}

class EmailAlert:
    """Represents an email alert/notification."""
    
    def __init__(self, subject, sender, body, date, unread=True):
        self.subject = subject
        self.sender = sender
        self.body = body
        self.date = date
        self.unread = unread
        self.seen = False
        self.replied = False
        self.priority = "medium"
        self.category = "general"
    
    def to_dict(self):
        return {
            "subject": self.subject,
            "sender": self.sender,
            "body": self.body,
            "date": self.date,
            "unread": self.unread,
            "replied": self.replied,
            "priority": self.priority,
            "category": self.category,
        }

def load_alerts():
    """Load existing alerts."""
    alerts_file = "/sandbox/new/data/email_alerts.json"
    if os.path.exists(alerts_file):
        with open(alerts_file) as f:
            data = json.load(f)
            return [EmailAlert(**a) for a in data]
    return []

def save_alerts(alerts):
    """Save alerts to file."""
    os.makedirs("/sandbox/new/data", exist_ok=True)
    with open("/sandbox/new/data/email_alerts.json", "w") as f:
        json.dump([a.to_dict() for a in alerts], f, indent=2)

def read_inbox():
    """Read inbox via Himalaya CLI."""
    cmd = [
        "ssh", "machine_learning@localhost", "-p", "22",
        "himalaya", "envelope", "list",
        "--page-size", "50",
        "--output", "json"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout}
    return {"error": result.stderr}

def read_email(message_id):
    """Read a specific email."""
    cmd = [
        "ssh", "machine_learning@localhost", "-p", "22",
        "himalaya", "message", "read", message_id
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "success": result.returncode == 0,
        "body": result.stdout if result.returncode == 0 else result.stderr
    }

def send_email(to: str, subject: str, body: str):
    """Send email via Himalaya CLI."""
    cmd = [
        "ssh", "machine_learning@localhost", "-p", "22",
        "himalaya", "message", "write",
        f"-H To:{to}",
        f"-H Subject:{subject}",
        f"-H From:{EMAIL_CONFIG['from_email']}"
    ] + body.split('\n')
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def score_email(email):
    """Score an email based on urgency and importance."""
    score = 0
    
    # Check for urgent keywords
    urgent_keywords = ["urgent", "deadline", "payment", "invoice", "security"]
    for keyword in urgent_keywords:
        if keyword in email.get("body", "").lower():
            score += 10
    
    # Check for bounty/proposal keywords
    bounty_keywords = ["bounty", "project", "job", "freelance", "contract"]
    for keyword in bounty_keywords:
        if keyword in email.get("body", "").lower():
            score += 5
    
    # Priority based on score
    if score >= 15:
        return "high", "opportunity"
    elif score >= 5:
        return "medium", "notification"
    else:
        return "low", "general"

def generate_response(template, custom_fields=None):
    """Generate a response based on template."""
    templates = {
        "thank_you": f"""Thank you for reaching out!

I've received your message and I'm reviewing the details. I'll get back to you with a proposal within 24 hours.

Best regards,
BountyBot
machine_learning@spark-8f4b""",
        
        "proposal": f"""Hi,

I'm interested in your bounty/project: {custom_fields.get('project', 'Your Project')}

My Approach:
1. Technical assessment
2. Implementation with testing
3. Documentation and handoff

Timeline: {custom_fields.get('timeline', '3-5 days')}
Price: {custom_fields.get('price', 'Negotiable')}

I have experience with:
- Web development and automation
- API integration and data processing
- Security and performance optimization

I'm available to start immediately. Let me know your preferred timeline.

Best regards,
BountyBot
machine_learning@spark-8f4b""",
        
        "invoice": f"""Hi,

Thank you for the payment. Here's the invoice for your records:

Invoice #{custom_fields.get('invoice', '001')}
Amount: ${custom_fields.get('amount', '0')}
Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Paid

Services: {custom_fields.get('services', 'Development work')}

Best regards,
BountyBot""",
    }
    
    return templates.get(template, templates["thank_you"])

def notify_user(alerts):
    """Send notification to user via Telegram."""
    if not alerts:
        return {"success": False, "message": "No alerts to notify"}
    
    # Format alerts for Telegram
    alert_text = "📧 New Emails:\n\n"
    
    for alert in alerts[:5]:  # Top 5 alerts
        alert_text += f"• {alert.subject}\n"
        alert_text += f"  From: {alert.sender}\n"
        alert_text += f"  Priority: {alert.priority}\n\n"
    
    # Send via Telegram
    cmd = [
        "curl", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{EMAIL_CONFIG['bot_token']}/sendMessage",
        "-d", f"chat_id={EMAIL_CONFIG['telegram_chat_id']}",
        "-d", f"text={alert_text}",
        "-d", "parse_mode=HTML"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def monitor_inbox():
    """Monitor inbox for new/urgent emails."""
    print("Monitoring inbox...")
    
    inbox = read_inbox()
    if not inbox or "error" in inbox:
        print(f"Error reading inbox: {inbox}")
        return
    
    if "items" in inbox:
        alerts = []
        for item in inbox["items"]:
            alert = EmailAlert(
                subject=item.get("subject", "Untitled"),
                sender=item.get("from", {}).get("email", "Unknown"),
                body=item.get("body", ""),
                date=item.get("date", ""),
                unread=item.get("flags", {}).get("seen", False) == False
            )
            
            priority, category = score_email(alert)
            alert.priority = priority
            alert.category = category
            
            if priority in ["high", "medium"]:
                alerts.append(alert)
        
        if alerts:
            print(f"\nFound {len(alerts)} urgent/important emails")
            for alert in alerts:
                print(f"  [{alert.priority.upper()}] {alert.subject}")
            notify_user(alerts)
        else:
            print("\nNo urgent emails found")
    
    save_alerts(alerts)

def send_alert(subject: str, body: str, to: str = None):
    """Send an alert email."""
    recipients = [to] if to else ["sparkbountybot@gmail.com"]
    
    for recipient in recipients:
        result = send_email(recipient, subject, body)
        if result["success"]:
            print(f"✅ Alert sent to {recipient}")
        else:
            print(f"❌ Failed to send to {recipient}: {result['stderr']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/email_notifications.py [monitor|notify|respond]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "monitor":
        monitor_inbox()
    
    elif action == "notify":
        if len(sys.argv) < 4:
            print("Usage: python3 scripts/email_notifications.py notify SUBJECT BODY")
            sys.exit(1)
        subject = " ".join(sys.argv[2:])
        send_alert(subject, f"Alert: {subject}")
    
    elif action == "respond":
        # Auto-respond to emails
        inbox = read_inbox()
        if "items" in inbox:
            for item in inbox["items"][:5]:  # Recent 5 emails
                alert = EmailAlert(
                    subject=item.get("subject", ""),
                    sender=item.get("from", {}).get("email", ""),
                    body=item.get("body", ""),
                    date=item.get("date", "")
                )
                priority, category = score_email(alert)
                
                if priority == "high" and category == "opportunity":
                    # Auto-respond to high-priority opportunities
                    response = generate_response("thank_you")
                    result = send_email(alert.sender, f"Re: {alert.subject}", response)
                    if result["success"]:
                        print(f"✅ Auto-responded to {alert.subject}")
                    else:
                        print(f"❌ Failed: {result['stderr']}")
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

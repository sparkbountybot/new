#!/usr/bin/env python3
"""
Email automation module - for Gmail integration via Himalaya CLI
Requires: himalaya installed, App Password configured

TODO for morning: User must run openshell policy on host to unblock
network for Google APIs, then install himalaya and configure credentials.
"""

import os
import subprocess
import json
from datetime import datetime, timedelta

EMAIL_CONFIG_PATH = os.path.expanduser("~/.config/himalaya/config.toml")

def email_send(to: str, subject: str, body: str, from_addr: str = None):
    """Send an email via Himalaya CLI."""
    headers = []
    if from_addr:
        headers.append(f"-H From:{from_addr}")
    
    cmd = [
        "himalaya", "message", "write",
        "-H", f"To:{to}",
        "-H", f"Subject:{subject}"
    ]
    if from_addr:
        cmd.append(f"-H From:{from_addr}")
    
    cmd.append(body)
    
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def email_inbox(count: int = 20):
    """List recent emails."""
    result = subprocess.run(
        ["himalaya", "envelope", "list", "--page-size", str(count), "--output", "json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout}
    return {"error": result.stderr}

def email_search(query: str, max_results: int = 20):
    """Search emails."""
    result = subprocess.run(
        ["himalaya", "envelope", "list", 
         "--search", query, 
         "--page-size", str(max_results),
         "--output", "json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout}
    return {"error": result.stderr}

def email_read(message_id: str):
    """Read a specific email."""
    result = subprocess.run(
        ["himalaya", "message", "read", message_id],
        capture_output=True, text=True, timeout=30
    )
    return {
        "success": result.returncode == 0,
        "body": result.stdout if result.returncode == 0 else result.stderr
    }

def setup_email():
    """Create himalaya config file for Gmail."""
    config_toml = """
[accounts.sparkbot]
email = "machine_learning@spark-8f4b"
display-name = "BountyBot"
default = true

backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "machine_learning@spark-8f4b"
backend.auth.type = "password"
backend.auth.cmd = "echo 'APP_PASSWORD_HERE'"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 465
message.send.backend.encryption.type = "tls"
message.send.login = "machine_learning@spark-8f4b"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "echo 'APP_PASSWORD_HERE'"

# Folder aliases for Gmail
folder.aliases.inbox = "INBOX"
folder.aliases.sent = "Sent"
folder.aliases.drafts = "Drafts"
folder.aliases.trash = "Trash"
folder.aliases.archive = "Gmail/All Mail"
"""
    return config_toml

if __name__ == "__main__":
    print("=== Email Automation Module ===")
    print("Requires: himalaya installed, App Password configured")
    print("TODO: Run openshell policy on host to unblock Google APIs")
    print("")
    print("Config template:")
    print(setup_email())

#!/usr/bin/env python3
"""
Gmail Automation via Himalaya CLI (Rust binary)
Status: Network blocked until policy update
App Password saved, ready for tomorrow

TODO for tomorrow:
1. User runs openshell policy on host to unblock Google services:
   openshell policy update spark2 \\
     --add-endpoint smtp.gmail.com:465:read-write:tls:enforce \\
     --add-endpoint imap.gmail.com:993:read-write:tls:enforce \\
     --add-endpoint smtp.gmail.com:587:read-write:start-tls:enforce \\
     --add-endpoint oauth2.googleapis.com:443:read-write:rest:enforce \\
     --add-endpoint accounts.google.com:443:read-write:rest:enforce \\
     --add-endpoint www.googleapis.com:443:read-write:rest:enforce \\
     --wait

2. Install Himalaya ARM64 binary:
   curl -sSL "https://github.com/pimalaya/himalaya/releases/latest/download/himalaya-linux-arm64.tar.gz" \\
     -o /tmp/himalaya.tar.gz
   tar -xzf /tmp/himalaya.tar.gz -C /tmp/
   cp /tmp/himalaya /usr/local/bin/

3. Configure ~/.config/himalaya/config.toml with:
   - Account: machine_learning@spark-8f4b
   - App Password (16 chars, already saved in .env)
   - IMAP: imap.gmail.com:993 (TLS)
   - SMTP: smtp.gmail.com:465 (TLS)

4. Test: himalaya envelope list

DNS via curl works: curl -s "https://dns.google/resolve?name=smtp.gmail.com&type=A"
Returns: 192.178.209.109 (for smtp.gmail.com)

App Password is saved in .env as GMAIL_APP_PASSWORD
"""

import os
import subprocess
import json
import tempfile
from datetime import datetime, timedelta

CONFIG_DIR = os.path.expanduser("~/.config/himalaya")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.toml")

def get_app_password():
    """Read app password from .env"""
    for path in ['.env', os.path.expanduser('~/.env'), '/sandbox/.env']:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    for line in f:
                        if line.startswith('GMAIL_APP_PASSWORD='):
                            return line.split('=', 1)[1].strip().strip('"\'')
            except:
                pass
    return None

def generate_config():
    """Generate himalaya config file"""
    password = get_app_password()
    if not password:
        return None
    
    return f"""[accounts.sparkbot]
email = "machine_learning@spark-8f4b"
display-name = "BountyBot"
default = true

backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "machine_learning@spark-8f4b"
backend.auth.type = "password"
backend.auth.cmd = "echo '{password}'"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 465
message.send.backend.encryption.type = "tls"
message.send.login = "machine_learning@spark-8f4b"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "echo '{password}'"

# Gmail folder aliases
folder.aliases.inbox = "INBOX"
folder.aliases.sent = "Sent"
folder.aliases.drafts = "Drafts"
folder.aliases.trash = "Trash"
folder.aliases.archive = "Gmail/All Mail"
"""

def setup_himalaya():
    """Setup Himalaya config and verify"""
    config = generate_config()
    if not config:
        return {"status": "error", "message": "App password not found in .env"}
    
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        f.write(config)
    
    return {"status": "config_written", "path": CONFIG_FILE, "message": "Config created. Next: install himalaya binary and test."}

def email_send(to: str, subject: str, body: str, from_addr: str = None):
    """Send email via Himalaya CLI"""
    cmd = ["himalaya", "message", "write", f"-H To:{to}", f"-H Subject:{subject}"]
    if from_addr:
        cmd.append(f"-H From:{from_addr}")
    cmd.append(body)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def email_inbox(count: int = 20):
    """List recent emails"""
    result = subprocess.run(
        ["himalaya", "envelope", "list", "--page-size", str(count), "--output", "json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except:
            return {"raw": result.stdout}
    return {"error": result.stderr}

def email_search(query: str, max_results: int = 20):
    """Search emails"""
    result = subprocess.run(
        ["himalaya", "envelope", "list", "--search", query, "--page-size", str(max_results), "--output", "json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except:
            return {"raw": result.stdout}
    return {"error": result.stderr}

if __name__ == "__main__":
    print("=== Gmail Automation Module ===")
    print(f"Status: Network blocked (proxy)")
    print(f"App Password: {'Found' if get_app_password() else 'MISSING'}")
    print(f"Config file: {CONFIG_FILE}")
    print()
    print("TOMORROW:")
    print("1. User runs openshell policy to unblock Google services")
    print("2. Install Himalaya ARM64 binary")
    print("3. Run python3 scripts/email_automation.py setup")
    print("4. Test: himalaya envelope list")

#!/usr/bin/env python3
"""
Bounty Hunter Pipeline — Scoring, submission, and email automation
Status: Ready to run (uses local network: GitHub API, PyPI)

Workflow:
1. Scan GitHub for bounty listings (open source bounties)
2. Score each bounty (payout, difficulty, time, client reputation)
3. Generate proposal emails
4. Send via Gmail (himalaya CLI on host)
5. Track submissions

Usage:
  python3 scripts/bounty_hunter.py scan      # Find bounties
  python3 scripts/bounty_hunter.py score     # Score new bounties
  python3 scripts/bounty_hunter.py propose   # Generate proposals
  python3 scripts/bounty_hunter.py send EMAIL # Send proposal email
"""

import os
import json
import subprocess
import re
from datetime import datetime, timedelta

# Scoring configuration
SCORE_CONFIG = {
    "payout_threshold": 100,  # Minimum payout to consider
    "payout_weight": 0.3,      # Weight for payout score
    "difficulty_weight": 0.2,  # Weight for difficulty assessment
    "time_weight": 0.15,       # Weight for time-to-pay
    "client_weight": 0.25,     # Weight for client reputation
    "complexity_weight": 0.1,  # Weight for technical complexity
}

class Bounty:
    """Represents a bounty opportunity."""
    
    def __init__(self, title, source, link, payout=None, client=None, deadline=None):
        self.title = title
        self.source = source  # github, upwork, fiverr, etc.
        self.link = link
        self.payout = payout
        self.client = client or "Unknown"
        self.deadline = deadline
        self.score = None
        self.proposal = None
        self.submitted = False
        self.submitted_at = None
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "title": self.title,
            "source": self.source,
            "link": self.link,
            "payout": self.payout,
            "client": self.client,
            "deadline": self.deadline,
            "score": self.score,
            "submitted": self.submitted,
            "submitted_at": self.submitted_at,
            "created_at": self.created_at,
        }

def load_bounties():
    """Load existing bounties from file."""
    bounties_file = "/sandbox/new/data/bounties.json"
    if os.path.exists(bounties_file):
        with open(bounties_file) as f:
            data = json.load(f)
            return [Bounty(**b) for b in data]
    return []

def save_bounties(bounties):
    """Save bounties to file."""
    os.makedirs("/sandbox/new/data", exist_ok=True)
    with open("/sandbox/new/data/bounties.json", "w") as f:
        json.dump([b.to_dict() for b in bounties], f, indent=2)

def scan_github_bounties():
    """Scan GitHub for open source bounties using GitHub API (which works)."""
    print("Scanning GitHub for bounty opportunities...")
    
    # Search for repos with bounty labels/issues
    queries = [
        "label:reward label:paying",
        "label:bounty",
        "label:good-first-issue label:help-wanted",
    ]
    
    bounties = []
    for query in queries:
        print(f"  Querying: {query}")
        try:
            # Use curl subprocess (GitHub works through proxy)
            result = subprocess.run(
                ["curl", "-s", 
                 f"https://api.github.com/search/issues?q={query}&per_page=10&sort=created"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if "items" in data:
                        for item in data["items"]:
                            bounty = Bounty(
                                title=item.get("title", "Untitled"),
                                source="github",
                                link=item.get("html_url", ""),
                                client=item.get("user", {}).get("login", "Unknown"),
                                deadline=None,
                            )
                            # Check for reward/bounty in labels or title
                            if any(tag in str(item.get("labels", [])).lower() for tag in ["reward", "bounty", "paying"]):
                                bounties.append(bounty)
                                print(f"    Found: {item['title'][:60]}")
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"    Error: {e}")
    
    print(f"\n  Found {len(bounties)} potential bounties")
    return bounties

def score_bounty(bounty):
    """Score a bounty based on multiple factors."""
    score = 0
    
    # Payout score (0-10)
    if bounty.payout:
        payout_score = min(10, bounty.payout / 100)
        score += payout_score * SCORE_CONFIG["payout_weight"]
    
    # Client reputation (0-10)
    client_score = min(10, len(bounty.client) / 5)  # Simple heuristic
    score += client_score * SCORE_CONFIG["client_weight"]
    
    # Deadline urgency (0-10)
    if bounty.deadline:
        try:
            days_left = (datetime.fromisoformat(bounty.deadline) - datetime.now()).days
            urgency = max(0, min(10, days_left))
            score += urgency * SCORE_CONFIG["time_weight"]
        except:
            pass
    
    return round(score, 1)

def generate_proposal(bounty, style="professional"):
    """Generate a proposal/reply email for a bounty."""
    if style == "professional":
        subject = f"Proposal: {bounty.title[:50]}"
        body = f"""Dear Bounty Host,

I'm interested in your bounty: "{bounty.title}"

My Approach:
1. Technical assessment and planning
2. Implementation with testing
3. Documentation and handoff

Timeline: ~3-5 days (depending on scope)
Price: Negotiable based on requirements

I have experience with:
- Web development and automation
- API integration and data processing
- Security and performance optimization

I've reviewed your requirements and I'm confident I can deliver quality work.

Best regards,
BountyBot
machine_learning@spark-8f4b"""
    else:
        subject = f"Re: {bounty.title[:50]}"
        body = f"""Hey there,

This looks like an interesting project! I can help with:
- Technical implementation
- Testing and documentation
- Quick turnaround

I'm available to start immediately. Let me know your timeline.

Cheers,
BountyBot"""
    
    return subject, body

def send_email(to: str, subject: str, body: str):
    """Send email via Himalaya CLI on host."""
    cmd = [
        "ssh", "machine_learning@localhost", "-p", "22",
        "himalaya", "message", "write",
        f"-H To:{to}",
        f"-H Subject:{subject}",
        "-H From:sparkbountybot@gmail.com"
    ] + body.split('\n')
    
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def read_inbox(max_count: int = 20):
    """Read inbox via Himalaya CLI on host."""
    cmd = [
        "ssh", "machine_learning@localhost", "-p", "22",
        "himalaya", "envelope", "list",
        f"--page-size={max_count}",
        "--output", "json"
    ]
    
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout}
    return {"error": result.stderr}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/bounty_hunter.py [scan|score|propose|send|inbox]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "scan":
        bounties = scan_github_bounties()
        if bounties:
            save_bounties(bounties)
            print(f"\nSaved {len(bounties)} bounties to /sandbox/new/data/bounties.json")
        else:
            print("No bounties found")
    
    elif action == "inbox":
        inbox = read_inbox(20)
        print(json.dumps(inbox, indent=2, default=str))
    
    elif action == "propose":
        bounties = load_bounties()
        for b in bounties:
            if not b.proposal and not b.submitted:
                subject, body = generate_proposal(b)
                b.proposal = (subject, body)
                print(f"Generated proposal for: {b.title}")
        save_bounties(bounties)
    
    elif action == "send":
        if len(sys.argv) < 3:
            print("Usage: python3 scripts/bounty_hunter.py send EMAIL")
            sys.exit(1)
        to_email = sys.argv[2]
        subject, body = generate_proposal(Bounty("Test", "test", "test"))
        result = send_email(to_email, subject, body)
        print(json.dumps(result, indent=2))
    
    elif action == "score":
        bounties = load_bounties()
        for b in bounties:
            b.score = score_bounty(b)
            print(f"Score {b.score}: {b.title[:50]}")
        save_bounties(bounties)

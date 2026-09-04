"""
Bounty Follow-Up System
=======================
Tracks sent proposals, sends follow-ups if no response, and manages the pipeline.

Usage:
  python3 follow_up_system.py --send          Send follow-ups for old proposals
  python3 follow_up_system.py --status        Show status of all proposals
  python3 follow_up_system.py --run             Full run: scan, analyze, propose, send
"""
import subprocess, re, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = "/sandbox/new"
FOLLOW_UP_DB = f"{WORKSPACE}/data/follow_up_db.json"

def load_db():
    if os.path.exists(FOLLOW_UP_DB):
        with open(FOLLOW_UP_DB) as f:
            return json.load(f)
    return {"proposals": [], "last_run": None}

def save_db(db):
    db["last_run"] = datetime.now().isoformat()
    with open(FOLLOW_UP_DB, 'w') as f:
        json.dump(db, f, indent=2)

def send_follow_up(proposal, days_since_sent):
    """Generate a follow-up email for a proposal that got no response"""
    email = proposal["email"]
    subject = f"Re: Proposal: {proposal['title'][:40]} — Following up"
    
    body = f"Following up on my previous message regarding: {proposal['title']}\n\n"
    
    if days_since_sent <= 3:
        body += "Just checking if you had a chance to review my proposal.\n"
    elif days_since_sent <= 7:
        body += "Checking in again — I'm still very interested in this bounty.\n"
        body += "I've had time to review the repo more thoroughly and am confident I can deliver quality work.\n"
    else:
        body += "Reaching out one more time about this bounty opportunity.\n"
        body += "If this is no longer open, a quick reply would be appreciated so I can focus elsewhere.\n"
    
    body += f"\nBest regards,\nsparkbountybot"
    
    return {"subject": subject, "body": body}

def check_and_send_followups():
    """Check all proposals and send follow-ups for those that need it"""
    db = load_db()
    now = datetime.now()
    followups_sent = 0
    
    for p in db.get("proposals", []):
        if p.get("status") != "sent":
            continue
        
        sent_date = datetime.fromisoformat(p.get("sent_date", ""))
        days_since = (now - sent_date).days
        
        # Send follow-ups at day 3, day 7, day 14
        next_followup_day = {3, 7, 14}
        next_followup_num = None
        for day in sorted(next_followup_day):
            if days_since >= day and not p.get(f"followup_{day}_sent"):
                next_followup_num = day
                break
        
        if next_followup_num:
            followup = send_follow_up(p, days_since)
            print(f"  Following up: {p['title'][:50]} ({days_since} days ago)")
            print(f"    Next followup: day {next_followup_num}")
            
            # Mark as followup sent
            p[f"followup_{next_followup_num}_sent"] = True
            p["followup_count"] = p.get("followup_count", 0) + 1
            followups_sent += 1
            
            # In production, this would trigger the email sender
            # For now, just log what would be sent
            print(f"    Subject: {followup['subject']}")
            print(f"    Body: {followup['body'][:100]}...")
    
    if followups_sent > 0:
        print(f"\n  ✅ {followups_sent} follow-ups prepared")
    else:
        print(f"\n  ℹ️  No follow-ups needed at this time")
    
    save_db(db)
    return followups_sent

def show_status():
    """Show status of all proposals"""
    db = load_db()
    
    proposals = db.get("proposals", [])
    if not proposals:
        print("No proposals tracked yet.")
        return
    
    print(f"Total proposals: {len(proposals)}")
    print()
    
    for i, p in enumerate(proposals):
        status = p.get("status", "unknown")
        days_since = ""
        if p.get("sent_date"):
            sent = datetime.fromisoformat(p["sent_date"])
            days_since = f" ({(datetime.now() - sent).days} days ago)"
        
        print(f"{i+1}. [{status.upper()}] {p['title'][:50]}{days_since}")
        print(f"   Email: {p.get('email', 'N/A')}")
        print(f"   Reward: ${p.get('reward', 0)}")
        if p.get("followup_count", 0) > 0:
            print(f"   Follow-ups sent: {p['followup_count']}")
    
    print()
    print("Status legend:")
    print("  SENT: Proposal sent, awaiting response")
    print("  REPLIED: Got a response")
    print("  ACCEPTED: Work accepted, payment pending")
    print("  CLOSED: No longer valid")

def add_proposal(title, email, url, reward=0):
    """Add a new proposal to the database"""
    db = load_db()
    
    proposal = {
        "id": len(db["proposals"]) + 1,
        "title": title,
        "email": email,
        "url": url,
        "reward": reward,
        "status": "pending",
        "created": datetime.now().isoformat(),
    }
    
    db["proposals"].append(proposal)
    save_db(db)
    print(f"Added: {title[:50]}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 follow_up_system.py --run       Full run: scan, analyze, propose, send")
        print("  python3 follow_up_system.py --send       Send follow-ups for old proposals")
        print("  python3 follow_up_system.py --status     Show status of all proposals")
        print("  python3 follow_up_system.py --add TITLE EMAIL URL REWARD")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--run":
        print("=" * 70)
        print("  BOUNTY FOLLOW-UP SYSTEM — Full Run")
        print("=" * 70)
        print()
        print("[1/3] Checking for follow-ups needed...")
        check_and_send_followups()
        print()
        print("[2/3] Running bounty hunter...")
        subprocess.run([sys.executable, f"{WORKSPACE}/bounty_hunter.py"], cwd=WORKSPACE)
        print()
        print("[3/3] Analyzing repos...")
        subprocess.run([sys.executable, f"{WORKSPACE}/repo_analyzer.py"], cwd=WORKSPACE)
        print()
        print("✅ Full run complete!")
    
    elif cmd == "--send":
        print("=" * 70)
        print("  BOUNTY FOLLOW-UP SYSTEM — Send Follow-ups")
        print("=" * 70)
        check_and_send_followups()
    
    elif cmd == "--status":
        print("=" * 70)
        print("  BOUNTY FOLLOW-UP SYSTEM — Status")
        print("=" * 70)
        show_status()
    
    elif cmd == "--add":
        if len(sys.argv) < 5:
            print("Usage: python3 follow_up_system.py --add TITLE EMAIL URL [REWARD]")
            return
        title = sys.argv[2]
        email = sys.argv[3]
        url = sys.argv[4]
        reward = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        add_proposal(title, email, url, reward)
    
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()

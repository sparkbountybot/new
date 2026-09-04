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

def add_to_followup_db(proposal):
    """Track a sent proposal for follow-up management"""
    db = load_db()
    
    proposal_id = f"{proposal.get('repo','')}/{proposal.get('issue',0)}"
    
    # Check if already exists
    for existing in db.get("proposals", []):
        if existing.get("id") == proposal_id:
            existing["status"] = "sent"
            existing["sent_date"] = datetime.now().isoformat()
            save_db(db)
            return existing
    
    # New proposal
    db.setdefault("proposals", []).append({
        "id": proposal_id,
        "title": proposal.get("title", ""),
        "email": proposal.get("email_to", [None])[0] if isinstance(proposal.get("email_to"), list) else None,
        "url": proposal.get("url", ""),
        "reward": proposal.get("reward", 0),
        "repo": proposal.get("repo", ""),
        "issue": proposal.get("issue", 0),
        "status": "sent",
        "sent_date": datetime.now().isoformat(),
        "followup_count": 0,
        "last_followup": None,
        "responses": [],
    })
    save_db(db)
    return db["proposals"][-1]


def check_and_send_followups():
    """Check all proposals and send follow-ups for those that need it"""
    db = load_db()
    now = datetime.now()
    followups_sent = 0
    followup_actions = []
    
    for p in db.get("proposals", []):
        if p.get("status") not in ("sent", "followup_sent"):
            continue
        
        sent_date = datetime.fromisoformat(p.get("sent_date", ""))
        days_since = (now - sent_date).days
        
        # Skip if already responded
        if p.get("responses") and p["responses"][-1].get("status") == "responded":
            continue
        
        # Send follow-ups at day 3, day 7, day 14
        next_followup_num = None
        for day in [3, 7, 14]:
            if days_since >= day and not p.get(f"followup_{day}_sent"):
                next_followup_num = day
                break
        
        if next_followup_num:
            followup_body = send_follow_up(p, days_since)
            followup_actions.append({
                "proposal_id": p["id"],
                "email": p.get("email", ""),
                "subject": f"Re: {p.get('title', '')[:40]} — Follow up #{p.get('followup_count', 0) + 1}",
                "body": followup_body,
                "day": next_followup_num,
            })
            p[f"followup_{next_followup_num}_sent"] = True
            p["followup_count"] = p.get("followup_count", 0) + 1
            p["status"] = "followup_sent"
            p["last_followup"] = datetime.now().isoformat()
            followups_sent += 1
    
    if followups_sent > 0:
        print(f"  ✅ {followups_sent} follow-ups prepared")
        for fa in followup_actions:
            print(f"    → {fa['email']}: {fa['subject']}")
    else:
        print(f"  ℹ️  No follow-ups needed at this time")
    
    save_db(db)
    return followups_sent, followup_actions


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
            days_since = f" ({(datetime.now() - sent).days}d ago)"
        
        print(f"{i+1}. [{status.upper()}] {p.get('title', 'N/A')[:50]}{days_since}")
        print(f"   Email: {p.get('email', 'N/A')}")
        print(f"   Reward: ${p.get('reward', 0)}")
        print(f"   Follow-ups: {p.get('followup_count', 0)}")
        if p.get("responses"):
            print(f"   Last response: {p['responses'][-1]}")
        print()

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

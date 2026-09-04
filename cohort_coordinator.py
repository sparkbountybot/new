"""
Cohort Coordinator — Multi-Sandbox Intelligence Sharing
========================================================
Coordinates between multiple Hermes sandboxes to share bounty intel,
avoid duplication, and amplify results. Each sandbox is a "node" in the
cohort.

Architecture:
  [sandbox A] <--GitHub Shared Repo--> [sandbox B]
       |                                       |
  Scans bounties                      Scans bounties
  Analyzes repos                      Analyzes repos
  Diffs proposals                     Diffs proposals
  
  They share:
  - Which bounties they've already claimed
  - Repo analysis results (cached)
  - Response rates per platform
  - New bounty sources discovered

Usage:
  python3 cohort_coordinator.py --share     Share this sandbox's data
  python3 cohort_coordinator.py --sync      Sync from shared repo
  python3 cohort_coordinator.py --status    Show cohort status
"""
import subprocess, re, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = "/sandbox/new"
SHARED_DIR = f"{WORKSPACE}/.github/shared"
COHORT_DB = f"{WORKSPACE}/data/cohort_db.json"
SHARED_DB_PATH = f"{SHARED_DIR}/cohort_data.json"


def load_cohort_db():
    if os.path.exists(COHORT_DB):
        with open(COHORT_DB) as f:
            return json.load(f)
    return {
        "this_sandbox": "sandbox-a",  # Default, will be overridden
        "nodes": {},
        "shared_bounties": {},
        "response_stats": {},
        "last_sync": None,
    }


def save_cohort_db(db):
    db["last_sync"] = datetime.now().isoformat()
    with open(COHORT_DB, 'w') as f:
        json.dump(db, f, indent=2)


def detect_hostname():
    """Detect which sandbox we're running in"""
    try:
        result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
        hostname = result.stdout.strip()
        # Normalize to sandbox-a, sandbox-b, etc.
        if "spark2" in hostname.lower():
            return "spark2"
        elif "spark3" in hostname.lower():
            return "spark3"
        else:
            return hostname.lower()
    except:
        return "unknown"


def share_data():
    """Share this sandbox's bounty/repo data with the cohort"""
    db = load_cohort_db()
    hostname = detect_hostname()
    db["this_sandbox"] = hostname
    
    print(f"Cohort Coordinator v1.0")
    print(f"Sandbox: {hostname}")
    print(f"Time: {datetime.now().isoformat()}")
    print()
    
    # Collect local data
    local_data = collect_local_data()
    
    if not local_data:
        print("  ℹ️  No data to share yet. Run bounty_hunter.py first.")
        return
    
    print("  Local data collected:")
    print(f"    - Proposals: {local_data.get('proposal_count', 0)}")
    print(f"    - Repos analyzed: {len(local_data.get('repo_analysis', {}))}")
    print(f"    - New bounties: {len(local_data.get('bounty_urls', []))}")
    
    # Write to shared location (visible to git)
    os.makedirs(SHARED_DIR, exist_ok=True)
    
    # Update the shared cohort db
    db["nodes"][hostname] = {
        "last_seen": datetime.now().isoformat(),
        "proposal_count": local_data.get("proposal_count", 0),
        "repo_count": len(local_data.get("repo_analysis", {})),
        "bounty_count": len(local_data.get("bounty_urls", [])),
        "uptime_since": "unknown",
        "hostname": hostname,  # For detection
    }
    
    # Add our bounty URLs and analyzed repos
    for url in local_data.get("bounty_urls", []):
        db["shared_bounties"][url] = {
            "discovered_by": hostname,
            "timestamp": datetime.now().isoformat(),
        }
    
    for repo, analysis in local_data.get("repo_analysis", {}).items():
        db["shared_bounties"][f"repo:{repo}"] = {
            "discovered_by": hostname,
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "total_files": analysis.get("total_files", 0),
                "languages": analysis.get("languages", {}),
                "has_tests": analysis.get("has_tests", False),
                "main_file": analysis.get("main_file", ""),
            }
        }
    
    save_cohort_db(db)
    
    # Also write to git-tracked shared dir
    with open(SHARED_DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)
    
    print(f"\n  ✅ Shared data saved to:")
    print(f"    - Local: {COHORT_DB}")
    print(f"    - Git: {SHARED_DB_PATH} (commit this)")
    print(f"  ℹ️  Run: git add .github/shared/cohort_data.json && git commit -m 'cohort share'")


def collect_local_data():
    """Collect data from this sandbox's local state"""
    data = {
        "proposal_count": 0,
        "bounty_urls": [],
        "repo_analysis": {},
        "recent_proposals": [],
    }
    
    # Count proposals
    proposals_dir = f"{WORKSPACE}/proposals"
    if os.path.exists(proposals_dir):
        data["proposal_count"] = len([f for f in os.listdir(proposals_dir) if f.endswith(".md")])
    
    # Get new bounty URLs from manifest
    manifest_path = f"{WORKSPACE}/data/bounty_manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        for p in manifest.get("proposals", []):
            url = p.get("url", "")
            if url:
                data["bounty_urls"].append(url)
            
            # Collect repo analysis from proposals
            repo = p.get("repo", "")
            if repo and "analyzed" in p and p.get("analyzed"):
                repo_url = f"https://github.com{repo}.git"
                if repo_url not in data["repo_analysis"]:
                    data["repo_analysis"][repo_url] = {
                        "file_count": p.get("repo_file_count", 0),
                        "main_file": p.get("repo_main_file", ""),
                        "analyzed_at": datetime.now().isoformat(),
                    }
            
            data["recent_proposals"].append({
                "url": url,
                "title": p.get("title", ""),
                "reward": p.get("reward", 0),
                "email_to": p.get("email_to", []),
            })
    
    return data


def sync_data():
    """Sync data from the shared repo (what other sandboxes have done)"""
    print("  Syncing cohort data...")
    
    # Pull latest shared data
    result = subprocess.run(
        ["git", "-C", WORKSPACE, "pull", "origin", "main", "--no-rebase"],
        capture_output=True, text=True, timeout=30
    )
    
    if "Already up to date" in result.stdout or "Already up to date" in result.stderr:
        print("  ℹ️  Already up to date")
    else:
        print("  ✅ Pulled latest shared data")
    
    if os.path.exists(SHARED_DB_PATH):
        with open(SHARED_DB_PATH) as f:
            shared_db = json.load(f)
        print(f"  📊 Shared data loaded from repo")
        return shared_db
    else:
        print("  ℹ️  No shared data yet")
        return None


def show_status():
    """Show cohort status"""
    db = load_cohort_db()
    hostname = detect_hostname()
    
    print("=" * 70)
    print(f"  COHORT STATUS — {hostname}")
    print("=" * 70)
    print()
    
    print("  Nodes:")
    for node, info in db.get("nodes", {}).items():
        marker = " ← this sandbox" if node == hostname else ""
        last_seen = info.get("last_seen", "unknown")
        try:
            from datetime import datetime
            if last_seen != "unknown":
                ts = datetime.fromisoformat(last_seen)
                ago = (datetime.now() - ts).total_seconds()
                if ago < 300:
                    ago_str = f"{int(ago)}s ago"
                elif ago < 3600:
                    ago_str = f"{int(ago/60)}m ago"
                else:
                    ago_str = f"{int(ago/3600)}h ago"
                last_seen = ago_str
        except:
            pass
        print(f"    {node}: {info.get('proposal_count', 0)} proposals, {info.get('repo_count', 0)} repos analyzed — {last_seen}{marker}")
    
    print()
    print("  Shared bounties:")
    print(f"    Total tracked: {len(db.get('shared_bounties', {}))}")
    
    # Count by sandbox
    by_sandbox = {}
    for url, info in db.get("shared_bounties", {}).items():
        if url.startswith("repo:"):
            continue
        found_by = info.get("discovered_by", "unknown")
        by_sandbox[found_by] = by_sandbox.get(found_by, 0) + 1
    
    for sandbox, count in by_sandbox.items():
        marker = " ← our finds" if sandbox == hostname else ""
        print(f"    {sandbox}: {count} bounties{marker}")
    
    print()
    print("  Response stats:")
    stats = db.get("response_stats", {})
    if stats:
        for platform, data in stats.items():
            total = data.get("total", 0)
            responded = data.get("responded", 0)
            rate = f"{int(responded/total*100)}%" if total > 0 else "N/A"
            print(f"    {platform}: {responded}/{total} responded ({rate})")
    else:
        print("    No response data yet")


def build_cohort_report():
    """Build a comprehensive report for the cohort"""
    db = load_cohort_db()
    hostname = detect_hostname()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "sandbox": hostname,
        "nodes": len(db.get("nodes", {})),
        "shared_bounties": len(db.get("shared_bounties", {})),
        "this_sandbox": {},
        "opportunities": [],
    }
    
    # Our local data
    local = collect_local_data()
    report["this_sandbox"] = {
        "proposals": local.get("proposal_count", 0),
        "bounties": len(local.get("bounty_urls", [])),
        "repos_analyzed": len(local.get("repo_analysis", {})),
    }
    
    # Find high-value opportunities we haven't done yet
    our_bounties = set(local.get("bounty_urls", []))
    shared_urls = {url for url in db.get("shared_bounties", {}).keys() if not url.startswith("repo:")}
    other_bounties = shared_urls - our_bounties
    
    report["opportunities"] = list(other_bounties)[:20]  # Top 20
    
    return report


def main():
    if len(sys.argv) < 2:
        print("Cohort Coordinator v1.0")
        print()
        print("Usage:")
        print("  python3 cohort_coordinator.py --share     Share this sandbox's data")
        print("  python3 cohort_coordinator.py --sync      Sync from shared repo")
        print("  python3 cohort_coordinator.py --status    Show cohort status")
        print("  python3 cohort_coordinator.py --report    Build cohort report")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--share":
        share_data()
    
    elif cmd == "--sync":
        sync_data()
    
    elif cmd == "--status":
        show_status()
    
    elif cmd == "--report":
        report = build_cohort_report()
        print(json.dumps(report, indent=2))
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()

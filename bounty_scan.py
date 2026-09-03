#!/usr/bin/env python3
"""
Simple GitHub Bounty Scanner
- Scans GitHub issues for bounty opportunities
- No proxy - uses direct GitHub access
"""
import json, os, sys, requests
from datetime import datetime

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def github_request(url, params=None):
    """Direct GitHub API call without proxy"""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def scan_org_repos(org="sparkbountybot"):
    """Scan repos in an organization"""
    repos = github_request(f"https://api.github.com/orgs/{org}/repos?per_page=100")
    if not repos:
        return []
    
    jobs = []
    for repo in repos[:20]:  # Top 20 repos
        name = repo["name"]
        # Get open issues
        issues = github_request(f"https://api.github.com/repos/{org}/{name}/issues?state=open&per_page=50&sort=comments")
        if not issues:
            continue
        
        for issue in issues:
            # Skip PRs
            if issue.get("pull_request"):
                continue
            
            title = issue.get("title", "")
            body = (issue.get("body") or "")[:2000]
            labels = [l.get("name", "") for l in issue.get("labels", [])]
            
            # Score this issue
            score = 0
            reasons = []
            
            # Bounty-related keywords
            bounty_words = ["bounty", "reward", "paid", "sponsor", "grant", "fund"]
            if any(w in title.lower() for w in bounty_words):
                score += 30
                reasons.append("Bounty keyword")
            
            # Good first issue / easy labels
            if any(l in labels for l in ["good-first-issue", "easy", "starter", "beginner"]):
                score += 20
                reasons.append("Easy label")
            
            # Engagement
            comments = issue.get("comments", 0)
            if comments > 5:
                score += 15
                reasons.append(f"{comments} comments")
            elif comments > 2:
                score += 10
            
            # Freshness
            created = issue.get("created_at", "")
            if created and "2026" in created[:7]:  # This year
                score += 5
                reasons.append("Recent")
            
            # Tech keywords
            tech_keywords = ["rust", "typescript", "react", "python", "api", "web3", "solidity", "blockchain"]
            text = (title + " " + body).lower()
            matched = [t for t in tech_keywords if t in text]
            if matched:
                score += min(len(matched) * 3, 15)
                reasons.append(f"{len(matched)} tech keywords")
            
            if score >= 20:
                jobs.append({
                    "title": title,
                    "repo": name,
                    "url": issue.get("html_url", ""),
                    "score": score,
                    "reasons": reasons,
                    "comments": comments,
                    "labels": labels,
                    "created_at": created[:10] if created else ""
                })
    
    return sorted(jobs, key=lambda x: x["score"], reverse=True)

def scan_public_bounties():
    """Search for bounty issues across GitHub"""
    queries = [
        "bounty is:issue is:open",
        "reward is:issue is:open",
        "paid work is:issue is:open",
        "grant is:issue is:open",
    ]
    
    jobs = []
    for query in queries:
        params = {"q": f"{query}", "per_page": 30, "sort": "comments"}
        results = github_request("https://api.github.com/search/issues", params=params)
        if not results:
            continue
        
        for item in results.get("items", []):
            if item.get("pull_request"):
                continue
            
            title = item.get("title", "")
            body = (item.get("body") or "")[:2000]
            repo = item.get("repository_url", "").split("/")[-1]
            score = 0
            reasons = []
            
            # Reward detection
            if "$" in title and any(c.isdigit() for c in title):
                score += 40
                reasons.append("Monetary value")
            
            if any(w in title.lower() for w in ["bounty", "reward", "paid", "grant", "sponsor"]):
                score += 20
                reasons.append("Bounty keyword")
            
            # Engagement
            if item.get("comments", 0) > 3:
                score += 10
                reasons.append("Active")
            
            if score >= 25:
                jobs.append({
                    "title": title,
                    "repo": repo,
                    "url": item.get("html_url", ""),
                    "score": score,
                    "reasons": reasons,
                    "comments": item.get("comments", 0)
                })
    
    # Deduplicate
    seen = set()
    unique = []
    for j in jobs:
        key = f"{j['repo']}:{j['title'][:50]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    
    return sorted(unique, key=lambda x: x["score"], reverse=True)

def main():
    print("=== GitHub Bounty Scanner ===\n")
    
    # Scan our org
    print("[1/2] Scanning sparkbountybot org...")
    org_jobs = scan_org_repos()
    print(f"  Found {len(org_jobs)} opportunities\n")
    for j in org_jobs[:10]:
        print(f"  [{j['score']}] {j['title'][:80]}")
        print(f"    {j['repo']} | {', '.join(j['reasons'][:3])}")
    
    # Scan public bounties
    print("\n[2/2] Scanning public bounties...")
    public_jobs = scan_public_bounties()
    print(f"  Found {len(public_jobs)} opportunities\n")
    for j in public_jobs[:10]:
        print(f"  [{j['score']}] {j['title'][:80]}")
        print(f"    {j['repo']} | {', '.join(j['reasons'][:3])}")
    
    # Summary
    print(f"\n=== TOTAL: {len(org_jobs) + len(public_jobs)} opportunities ===")
    if org_jobs:
        print(f"Highest value in our org: {org_jobs[0]['score']}: {org_jobs[0]['title'][:60]}")
    if public_jobs:
        print(f"Highest value public: {public_jobs[0]['score']}: {public_jobs[0]['title'][:60]}")

if __name__ == "__main__":
    main()

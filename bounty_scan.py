#!/usr/bin/env python3
"""GitHub Bounty Scanner - runs from host terminal"""
import requests, json, os

def scan_org():
    r = requests.get("https://api.github.com/orgs/sparkbountybot/repos?per_page=20", timeout=10)
    if r.status_code != 200: return []
    jobs = []
    for repo in r.json():
        r2 = requests.get(f"https://api.github.com/repos/sparkbountybot/{repo['name']}/issues?state=open&per_page=30&sort=comments", timeout=10)
        if r2.status_code != 200: continue
        for issue in r2.json():
            if issue.get("pull_request"): continue
            title = issue.get("title", "")
            labels = [l.get("name","") for l in issue.get("labels",[])]
            score = 0
            if any(w in title.lower() for w in ["bounty","reward","paid","grant"]): score += 20
            if any(l in labels for l in ["good-first-issue","easy","starter","beginner"]): score += 15
            if issue.get("comments",0) > 5: score += 10
            if score >= 20:
                jobs.append({"title": title, "repo": repo["name"], "url": issue.get("html_url",""), "score": score, "comments": issue.get("comments",0)})
    return sorted(jobs, key=lambda x: x["score"], reverse=True)

def scan_public():
    queries = ["bounty is:issue is:open", "reward is:issue is:open", "paid work is:issue is:open"]
    jobs = []
    for q in queries:
        r = requests.get(f"https://api.github.com/search/issues?q={q}&per_page=30", timeout=10)
        if r.status_code != 200: continue
        for item in r.json().get("items", []):
            if item.get("pull_request"): continue
            title = item.get("title", "")
            repo = item.get("repository_url", "").split("/")[-1]
            score = 0
            if any(w in title.lower() for w in ["bounty","reward","paid","grant","sponsor"]): score += 30
            if "$" in title and any(c.isdigit() for c in title): score += 40
            if item.get("comments",0) > 3: score += 10
            if score >= 25:
                jobs.append({"title": title, "repo": repo, "url": item.get("html_url",""), "score": score})
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
    print("[1/2] Scanning sparkbountybot org...")
    org_jobs = scan_org()
    print(f"  Found {len(org_jobs)} opportunities\n")
    for j in org_jobs[:10]:
        print(f"  [{j['score']}] {j['title'][:80]}")
        print(f"    {j['repo']}")
    print("\n[2/2] Scanning public bounties...")
    pub_jobs = scan_public()
    print(f"  Found {len(pub_jobs)} opportunities\n")
    for j in pub_jobs[:10]:
        print(f"  [{j['score']}] {j['title'][:80]}")
        print(f"    {j['repo']}")
    print(f"\n=== TOTAL: {len(org_jobs) + len(pub_jobs)} opportunities ===")

if __name__ == "__main__":
    main()

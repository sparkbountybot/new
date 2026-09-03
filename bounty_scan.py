#!/usr/bin/env python3
"""GitHub Bounty Scanner - run from host terminal"""
import requests, json, os, re

def extract_reward(text):
    m = re.findall(r'\$(\d[\d,]*)', text)
    if m: return int(m[0].replace(',', ''))
    return 0

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
            body = (issue.get("body") or "")[:2000]
            labels = [l.get("name","") for l in issue.get("labels",[])]
            score = 0
            reasons = []
            if any(w in title.lower() for w in ["bounty","reward","paid","grant"]): 
                score += 20; reasons.append("bounty keyword")
            if any(l in labels for l in ["good-first-issue","easy","starter","beginner"]): 
                score += 15; reasons.append("easy label")
            if issue.get("comments",0) > 5: 
                score += 10; reasons.append(f"{issue['comments']} comments")
            elif issue.get("comments",0) > 2: 
                score += 5
            if "$" in title or "$" in body: 
                rwd = extract_reward(title + " " + body)
                if rwd > 0: score += min(rwd // 100, 30); reasons.append(f"${rwd} reward")
            if len(reasons) >= 2 and score >= 20:
                jobs.append({
                    "title": title, "repo": repo["name"], 
                    "url": issue.get("html_url",""), "score": score,
                    "comments": issue.get("comments",0), "reasons": reasons,
                    "labels": labels, "reward": extract_reward(title + " " + body)
                })
    return sorted(jobs, key=lambda x: x["score"], reverse=True)

def scan_public():
    queries = ["bounty is:issue is:open", "reward is:issue is:open", "paid work is:issue is:open", "sponsor is:issue is:open"]
    jobs = []
    for q in queries:
        r = requests.get(f"https://api.github.com/search/issues?q={q}&per_page=30", timeout=10)
        if r.status_code != 200: continue
        for item in r.json().get("items", []):
            if item.get("pull_request"): continue
            title = item.get("title", "")
            body = (item.get("body") or "")[:2000]
            repo = item.get("repository_url", "").split("/")[-1]
            score = 0
            reasons = []
            if any(w in title.lower() for w in ["bounty","reward","paid","grant","sponsor"]): 
                score += 30; reasons.append("bounty keyword")
            if "$" in title and any(c.isdigit() for c in title): 
                rwd = extract_reward(title + " " + body)
                if rwd > 0: score += min(rwd // 100, 40); reasons.append(f"${rwd}")
            if item.get("comments",0) > 3: 
                score += 10; reasons.append(f"{item['comments']} comments")
            if score >= 25:
                jobs.append({
                    "title": title, "repo": repo, "url": item.get("html_url",""), 
                    "score": score, "reasons": reasons, "reward": extract_reward(title + " " + body)
                })
    seen = set()
    unique = []
    for j in jobs:
        key = f"{j['repo']}:{j['title'][:50]}"
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return sorted(unique, key=lambda x: x["score"], reverse=True)

def main():
    print("=" * 60)
    print("  GitHub Bounty Hunter")
    print("=" * 60)
    
    print("\n[1/2] Scanning sparkbountybot org...")
    org_jobs = scan_org()
    print(f"  Found {len(org_jobs)} opportunities\n")
    for j in org_jobs[:10]:
        print(f"  [{j['score']:3d}] ${j['reward']:>6}  {j['title'][:70]}")
        print(f"        {j['repo']} | {', '.join(j['reasons'][:3])}")
    
    print("\n[2/2] Scanning public bounties...")
    pub_jobs = scan_public()
    print(f"  Found {len(pub_jobs)} opportunities\n")
    for j in pub_jobs[:15]:
        print(f"  [{j['score']:3d}] ${j['reward']:>6}  {j['title'][:70]}")
        print(f"        {j['repo']} | {', '.join(j['reasons'][:3])}")
    
    total = len(org_jobs) + len(pub_jobs)
    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {total} opportunities")
    if org_jobs or pub_jobs:
        best = max(org_jobs + pub_jobs, key=lambda x: x['score'])
        print(f"  Best match: [{best['score']}] {best['title'][:80]}")
        print(f"  {best['url']}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()

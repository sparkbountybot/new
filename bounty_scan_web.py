#!/usr/bin/env python3
"""
GitHub Bounty Hunter — Web-Scraping Edition
Scrapes GitHub's web UI for open issues with bounty/reward keywords.
Works through the sandbox proxy because github.com is allowed.
"""
import re
import json
import subprocess
import os
import sys
from datetime import datetime

GITHUB_SEARCH_URL = "https://github.com/search?q={query}&type=issues"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

BOUNTY_KEYWORDS = [
    'bounty', 'reward', 'paid', 'grant', 'sponsor', 'prize',
    'compensation', 'paid work', 'contributor reward',
]

SEARCH_QUERIES = [
    # General bounty/reward searches
    'bounty is:issue is:open',
    'reward is:issue is:open',
    '"paid work" is:issue is:open',
    '"grant" is:issue is:open',
    '"sponsor" is:issue is:open',
    # Good first issue + money
    '"good first issue" bounty',
    '"good first issue" reward',
    '"good first issue" paid',
    '"good first issue" grant',
    # Starter + money
    '"starter" bounty',
    '"starter" reward',
    '"starter" paid',
    # Beginner + money
    '"beginner" bounty',
    '"beginner" reward',
    '"beginner" paid',
    # First timers + money
    '"first-timers-only" bounty',
    '"first-timers-only" reward',
    '"first-timers-only" paid',
]

def curl_get(url):
    """Fetch a URL using curl through the sandbox proxy"""
    cmd = ['curl', '-s', '--max-time', '15', '--max-redirs', '3',
           '-H', f'User-Agent: {HEADERS["User-Agent"]}',
           '-H', f'Accept: {HEADERS["Accept"]}',
           '-L', url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if r.returncode != 0 or not r.stdout:
            return None
        return r.stdout
    except:
        return None

def extract_reward(text):
    """Extract dollar amounts from text"""
    amounts = re.findall(r'\$([0-9,]+(?:\.[0-9]+)?)', text)
    max_amount = 0
    for a in amounts:
        try:
            val = float(a.replace(',', ''))
            if val > max_amount:
                max_amount = val
        except:
            pass
    return max_amount

def parse_search_page(html):
    """Parse GitHub search results HTML for issues"""
    issues = []
    
    # Find issue links: href="/org/repo/issues/NNN"
    issue_links = re.findall(
        r'href="(/[^/]+/[^/]+)/issues/(\d+)"', html
    )
    
    # Extract issue titles - look for the title in the search result
    # GitHub search results have titles in <h3> with class "h2" or similar
    # Pattern: <h3>...<a href="/org/repo/issues/N">Title</a>...</h3>
    title_pattern = r'<h3[^>]*>.*?<a[^>]*href="(/[^/]+/[^/]+)/issues/(\d+)"[^>]*>(.*?)</a>'
    
    for m in re.finditer(title_pattern, html, re.DOTALL):
        repo_path = m.group(1)
        issue_num = m.group(2)
        title_raw = m.group(3)
        
        # Strip HTML tags from title
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        # Decode HTML entities
        title = re.sub(r'&(#\w+|\w+);', '', title)
        title = title.replace('&#x2F;', '/').replace('&#x2F;', '/')
        
        if not title or issue_num == '0':
            continue
        
        # Look for bounty amounts in nearby text
        bounty_amount = 0
        # Search a window around the title for dollar amounts
        window_start = max(0, m.start() - 500)
        window_end = min(len(html), m.end() + 500)
        window_text = html[window_start:window_end]
        
        # Check for common bounty patterns
        if '$' in window_text:
            bounty_amount = extract_reward(window_text)
        
        # Also extract from title itself (bounty titles often include amounts)
        bounty_amount = max(bounty_amount, extract_reward(title))
        
        # Check for bounty amount in the full window
        for amount_match in re.finditer(r'\$([0-9,]+)', window_text):
            try:
                val = float(amount_match.group(1).replace(',', ''))
                if val > bounty_amount:
                    bounty_amount = val
            except:
                pass
        
        issues.append({
            'repo': repo_path,
            'issue': int(issue_num),
            'title': title,
            'url': f'https://github.com{repo_path}/issues/{issue_num}',
            'reward': bounty_amount,
        })
    
    return issues

def extract_issue_details(issue_url):
    """Fetch individual issue page for more details (comments, labels, body)"""
    html = curl_get(issue_url)
    if not html:
        return None
    
    details = {}
    
    # Extract comments count
    comments_match = re.search(
        r'href="/[^/]+/[^/]+/issues/\d+#discussion_button"[^>]*>\s*([\d,]+)\s*</span>',
        html
    )
    if comments_match:
        try:
            details['comments'] = int(comments_match.group(1).replace(',', ''))
        except:
            pass
    
    # Extract labels
    labels = re.findall(r'href="/[^/]+/[^/]+/labels/([^"]+)"', html)
    details['labels'] = [l.strip().lower() for l in labels if l.strip()]
    
    # Extract body text (first 500 chars)
    body_match = re.search(
        r'<div[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)</div>\s*</article>',
        html, re.DOTALL
    )
    if body_match:
        body_text = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
        body_text = re.sub(r'&(#\w+|\w+);', '', body_text)
        details['body'] = body_text[:1000]
        
        # Check body for bounty amounts
        body_reward = extract_reward(body_text)
        details['reward'] = max(details.get('reward', 0), body_reward)
    
    # Extract time created
    created_match = re.search(
        r'href="/[^/]+/[^/]+/releases[^"]*"[^>]*>\s*([\w\s]+)\s*ago',
        html
    )
    if created_match:
        details['time_created'] = created_match.group(1).strip()
    
    return details

def score_issue(issue, details=None):
    """Score an issue for bounty quality"""
    score = 0
    reasons = []
    title_lower = issue['title'].lower()
    body_lower = (details.get('body') or '').lower() if details else ''
    combined = title_lower + ' ' + body_lower
    
    # Money signals
    if issue.get('reward', 0) > 0:
        score += min(int(issue['reward'] / 50), 40)
        reasons.append(f"${issue['reward']}")
    
    # Bounty keywords
    for kw in BOUNTY_KEYWORDS:
        if kw in title_lower or kw in body_lower:
            score += 5
            reasons.append(f"'{kw}'")
            break  # count each keyword once
    
    # Labels
    if details:
        labels = details.get('labels', [])
        if 'good-first-issue' in labels or 'starter' in labels or 'first-timers-only' in labels:
            score += 15
            reasons.append("beginner-friendly")
        if 'bounty' in labels or 'reward' in labels or 'funding' in labels:
            score += 10
            reasons.append("labeled")
    
    # Comments (engagement indicator)
    if details:
        comments = details.get('comments', 0)
        if comments > 10:
            score += 10
            reasons.append(f"{comments} comments")
        elif comments > 3:
            score += 5
    
    return score, reasons

def scrape_all(query_label):
    """Run a search query and parse results"""
    query = query_label.split(' | ')[0]
    label = query_label.split(' | ')[1] if ' | ' in query_label else query_label
    query_encoded = query.replace(' ', '+')
    url = GITHUB_SEARCH_URL.format(query=query_encoded)
    
    html = curl_get(url)
    if not html:
        return [], label
    
    issues = parse_search_page(html)
    return issues, label

def main():
    print("=" * 70)
    print("  GITHUB BOUNTY HUNTER — Web Scraping Edition")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print()
    
    # Phase 1: Web search
    print("[1/2] Searching GitHub for open bounties...")
    all_issues = {}
    
    for ql in SEARCH_QUERIES:
        issues, label = scrape_all(ql)
        if issues:
            print(f"  {label}: {len(issues)} results")
            for iss in issues[:3]:
                reward_str = f"${iss['reward']}" if iss['reward'] > 0 else ""
                print(f"    - {iss['repo']}: {iss['title'][:80]} {reward_str}")
                print(f"      {iss['url']}")
            print()
        
        for iss in issues:
            key = iss['url']
            if key not in all_issues:
                all_issues[key] = iss
    
    print(f"\n  Total unique issues: {len(all_issues)}")
    print()
    
    # Phase 2: Enrich top results with issue details
    print("[2/2] Enriching top results...")
    issues_list = list(all_issues.values())
    
    # Score and sort
    scored = []
    for iss in issues_list:
        score, reasons = score_issue(iss)
        scored.append((score, iss, reasons))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Enrich top 20
    for i, (score, iss, reasons) in enumerate(scored[:20]):
        if i >= 20:
            break
        details = extract_issue_details(iss['url'])
        if details:
            # Update reward from issue body
            if details.get('reward', 0) > iss.get('reward', 0):
                iss['reward'] = details['reward']
                score, reasons = score_issue(iss, details)
            scored[i] = (score, iss, reasons)
    
    # Print top results
    print(f"\n  {'Rank':<6}{'Score':<8}{'Reward':<10}{'Issue'}")
    print(f"  {'-'*6}{'-'*8}{'-'*10}{'-'*50}")
    
    top_issues = []
    for i, (score, iss, reasons) in enumerate(scored[:20]):
        reward_str = f"${iss['reward']}" if iss['reward'] > 0 else "-"
        repo_short = iss['repo'].split('/')[-1] if '/' in iss['repo'] else iss['repo']
        print(f"  {i+1:<6}{score:<8}{reward_str:<10}{iss['title'][:50]}")
        print(f"       {iss['repo']}/{iss['issue']} ({', '.join(reasons[:3])})")
        print(f"       {iss['url']}")
        print()
        
        top_issues.append({
            'rank': i + 1,
            'score': score,
            'repo': iss['repo'],
            'issue': iss['issue'],
            'title': iss['title'],
            'url': iss['url'],
            'reward': iss['reward'],
            'reasons': reasons,
        })
    
    # Save results
    results_file = '/sandbox/new/bounty_scan_web.json'
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_found': len(all_issues),
        'top_issues': top_issues,
    }
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {results_file}")
    print(f"Total: {len(all_issues)} bounties found, {len(top_issues)} enriched")

if __name__ == '__main__':
    main()

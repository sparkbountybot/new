#!/usr/bin/env python3
"""Scrape GitHub issue bodies via web scraping - terminal version"""
import subprocess, re, json, sys

def scrape_issue(url):
    """Fetch and extract readable content from a GitHub issue page"""
    cmd = ['curl', '-s', '--max-time', '15', url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0 or not r.stdout:
        return None
    
    html = r.stdout
    
    # Extract title from the bdi element
    title_m = re.search(r'data-testid="issue-title">([^<]+)<', html)
    title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ""
    
    # Try to get body from markdown-body section - look for ALL content after the marker
    body = ""
    if 'data-testid="markdown-body"' in html:
        idx = html.index('data-testid="markdown-body"')
        section = html[idx:idx+8000]  # First 8KB after marker
        
        # Find paragraph tags
        paras = re.findall(r'<p[^>]*>(.*?)</p>', section, re.DOTALL)
        for p in paras:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = re.sub(r'&#x\d+;', '', text)
            text = re.sub(r'&#(\w+);', '', text)
            if text and len(text) > 5:
                body += text + "\n"
    
    # Extract metadata
    comments_m = re.findall(r'discussion_button"[^>]*>\s*([\d,]+)\s*</span>', html)
    comments = int(comments_m[0].replace(',', '')) if comments_m else 0
    
    labels_m = re.findall(r'/labels/([^"]+)', html)
    labels = list(set([l.lower().strip() for l in labels_m]))
    
    # Extract email from any text content
    all_text = re.sub(r'<[^>]+>', ' ', html)
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', all_text)
    
    return {
        'title': title,
        'body': body[:2000].strip(),
        'comments': comments,
        'labels': labels,
        'emails': emails,
        'url': url,
    }

# Top bounty issues from our scan
urls = [
    'https://github.com/stanfordmlgroup/ngboost/issues/298',
    'https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/310',
    'https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/254',
    'https://github.com/openai/codex-security/issues/25',
    'https://github.com/HHS/simpler-grants-protocol/issues/1146',
    'https://github.com/zhangjiayang6835-cyber/bounty-plaza/issues/626',
]

results = []
for url in urls:
    print(f"Scraping {url}...")
    data = scrape_issue(url)
    if data:
        results.append(data)

# Save results
output = {
    'timestamp': '2026-09-03',
    'issues': results,
}
with open('/sandbox/new/bounty_report.json', 'w') as f:
    json.dump(output, f, indent=2)

print("\n=== RESULTS ===")
for r in results:
    print(f"\n{r['url']}")
    print(f"  Title: {r['title']}")
    print(f"  Comments: {r['comments']}")
    if r['labels']:
        print(f"  Labels: {', '.join(r['labels'][:5])}")
    if r['body']:
        print(f"  Body: {r['body'][:300]}...")
    if r['emails']:
        print(f"  Emails: {r['emails']}")
print("\nSaved to /sandbox/new/bounty_report.json")

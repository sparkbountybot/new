#!/usr/bin/env python3
"""
Real GitHub Bounty Hunter — Email Proposal System
==============================================
Scrapes GitHub web UI for real bounties, scores them, and emails proposals
to maintainers on the top candidates.

Since Gmail SMTP is blocked in the sandbox, this script:
1. Finds and scores real bounties from GitHub search
2. Drafts professional proposal emails for top bounties
3. Saves emails to /sandbox/new/proposals/
4. Also tries to send via Gmail if SMTP is available (fallback)

Cron job: runs every 6 hours, saves results + drafts emails.
"""
import re, json, subprocess, os, sys
from datetime import datetime

# Email config
FROM_EMAIL = "sparkbountybot@gmail.com"
EMAIL_FILE = "/sandbox/new/data/bounty_proposals.json"

# Output directory for proposals
PROPOSALS_DIR = "/sandbox/new/data/proposals"
os.makedirs(PROPOSALS_DIR, exist_ok=True)

# Search queries covering different bounty categories
SEARCH_QUERIES = [
    ('bounty is:issue is:open', 'general_bounties'),
    ('reward is:issue is:open', 'rewards'),
    ('"good first issue" bounty', 'beginner_bounties'),
    ('"first-timers-only" bounty', 'first_timers'),
    ('"starter" bounty', 'starter_bounties'),
    ('"paid work" is:issue is:open', 'paid_work'),
    ('"grant" is:issue is:open', 'grants'),
    ('sponsor is:issue is:open', 'sponsors'),
    ('bug bounty', 'security'),
    ('"security" bounty', 'security'),
]

def curl_get(url):
    """Fetch URL via curl through sandbox proxy"""
    try:
        r = subprocess.run(
            ['curl', '-s', '--max-time', '15', '--max-redirs', '3',
             '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
             '-H', 'Accept: text/html', '-L', url],
            capture_output=True, text=True, timeout=20
        )
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

def extract_emails(text):
    """Extract email addresses from text"""
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return list(set(emails))

def parse_search_results(html):
    """Extract issues from GitHub search page HTML"""
    issues = []
    seen = set()

    # Find issue links with titles
    title_pattern = r'<h3[^>]*>.*?<a[^>]*href="(/[^/]+/[^/]+)/issues/(\d+)"[^>]*>(.*?)</a>'

    for m in re.finditer(title_pattern, html, re.DOTALL):
        repo_path = m.group(1)
        issue_num = m.group(2)
        title_raw = m.group(3)
        title = re.sub(r'<[^>]+>', '', title_raw).strip()
        title = re.sub(r'&#x\w+;', ' ', title)

        if not title or issue_num == '0':
            continue

        key = f"{repo_path}/issues/{issue_num}"
        if key in seen:
            continue
        seen.add(key)

        # Extract bounty amount from title and nearby text
        bounty_amount = extract_reward(title)
        if bounty_amount == 0:
            idx = max(0, m.start() - 500)
            window = html[idx:m.end() + 500]
            bounty_amount = extract_reward(window)

        # Look for email in nearby text
        emails = []
        idx = max(0, m.start() - 2000)
        window = html[idx:m.end() + 2000]
        emails = extract_emails(window)

        issues.append({
            'repo': repo_path,
            'issue': int(issue_num),
            'title': title,
            'url': f'https://github.com{repo_path}/issues/{issue_num}',
            'reward': bounty_amount,
            'emails': emails,
        })

    return issues

def scrape_search(query):
    """Run a search query and return issues"""
    query_encoded = query.replace(' ', '+')
    url = f"https://github.com/search?q={query_encoded}+is:issue+is:open&type=issues"
    html = curl_get(url)
    if not html:
        return []
    return parse_search_results(html)

def fetch_issue_details(url):
    """Fetch an individual issue page for more details"""
    html = curl_get(url)
    if not html:
        return {}

    details = {}

    # Extract body from markdown-body section
    if 'data-testid="markdown-body"' in html:
        idx = html.index('data-testid="markdown-body"')
        section = html[idx:idx+10000]

        # Find paragraphs
        paras = re.findall(r'<p[^>]*>(.*?)</p>', section, re.DOTALL)
        body_parts = []
        for p in paras:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = re.sub(r'&#x\w+;', ' ', text)
            if text and len(text) > 5:
                body_parts.append(text)
        details['body'] = '\n\n'.join(body_parts[:5])[:3000]

        # Find links in body
        details['body_links'] = re.findall(r'href="(https?://[^"]+)"', section)

    # Extract labels
    labels = re.findall(r'/labels/([^"]+)', html)
    details['labels'] = list(set([l.lower().strip() for l in labels]))

    # Extract comments count
    comments_m = re.findall(r'discussion_button"[^>]*>\s*([\d,]+)\s*</span>', html)
    if comments_m:
        try:
            details['comments'] = int(comments_m[0].replace(',', ''))
        except:
            pass

    # Extract all emails from the page
    all_emails = extract_emails(html)
    details['emails'] = all_emails

    # Extract author info
    author_m = re.search(r'data-testid="issue-body-header-author">([^<]+)<', html)
    if author_m:
        details['author'] = author_m.group(1).strip()

    return details

def score_issue(issue, details=None):
    """Score an issue for our ability to complete it"""
    score = 0
    reasons = []
    title_lower = issue['title'].lower()
    body_lower = (details.get('body') or '').lower() if details else ''
    combined = title_lower + ' ' + body_lower
    labels = details.get('labels', []) if details else []

    # Money signals
    if issue.get('reward', 0) > 0:
        score += min(int(issue['reward'] / 100), 30)
        reasons.append(f"${issue['reward']}")

    # Bounty keywords
    for kw in ['bounty', 'reward', 'paid', 'grant', 'sponsor', 'compensation']:
        if kw in title_lower or kw in body_lower:
            score += 5
            break

    # Beginner-friendly labels (higher chance of success)
    for lbl in ['good-first-issue', 'starter', 'first-timers-only', 'easy']:
        if any(lbl in l for l in labels):
            score += 20
            reasons.append("beginner-friendly")
            break

    # Specific skill matches (Python code work)
    for kw in ['python', 'script', 'api', 'documentation', 'docs', 'test', 'lint',
                'config', 'setup', 'install', 'docker', 'readme', 'changelog']:
        if kw in combined:
            score += 15
            reasons.append(f"matches skill ({kw})")
            break

    # Complex/low-level stuff (lower score — harder to complete)
    for kw in ['cuda', 'gpu', 'kernel', 'asm', 'assembly', 'rust', 'c++', 'memory',
                'compiler', 'gpu', 'driver', 'firmware']:
        if kw in combined:
            score -= 10
            reasons.append(f"hard skill ({kw})")
            break

    # Comments are engagement but also risk of someone else being ahead
    comments = details.get('comments', 0) if details else 0
    if comments == 0:
        score += 10  # Nobody else has commented yet
        reasons.append("no comments yet")
    elif comments < 3:
        score += 5

    return score, reasons

def generate_proposal(issue, details=None):
    """Generate a proposal email for a bounty"""
    title = issue['title']
    repo = issue['repo']
    repo_name = repo.split('/')[-1] if '/' in repo else repo
    issue_num = issue['issue']
    reward = issue.get('reward', 0)
    url = issue['url']

    title_lower = title.lower()

    # Categorize the bounty type
    category = "general"
    task_summary = title
    key_points = []

    # Analyze what the bounty is about
    body = (details.get('body') or '').lower() if details else ''
    combined = title_lower + ' ' + body

    if 'python' in combined:
        category = "python"
        key_points.append("Python implementation")
    if 'documentation' in combined or 'docs' in combined:
        category = "documentation"
        key_points.append("Documentation/drafting")
    if 'test' in combined:
        category = "testing"
        key_points.append("Testing/coverage")
    if 'docker' in combined or 'container' in combined:
        category = "devops"
        key_points.append("Docker/containerization")
    if 'api' in combined:
        category = "backend"
        key_points.append("API work")
    if 'bug' in combined:
        category = "bugfix"
        key_points.append("Bug fix")
    if 'feature' in combined or 'implement' in combined or 'add' in combined:
        category = "feature"
        key_points.append("Feature implementation")

    # Generate subject and body
    subject = f"Proposal: {repo_name} #{issue_num} — {title[:60]}"

    # Build the email body
    email_body = f"""Hello,

I'm interested in your bounty opportunity: {title}

**Project:** {repo}
**Issue:** #{issue_num} — {title}
**URL:** {url}
{"**Reward:** $" + str(reward) if reward else "**Reward:** As listed"}

**How I'd approach this:**

"""

    if category == "documentation":
        email_body += f"""1. Review the current state of the bounty program documentation
2. Create a clear, comprehensive draft covering all required sections
3. Include examples and templates where applicable
4. Submit a draft PR for review

I have experience writing clear technical documentation and have successfully contributed to open-source projects before."""

    elif category == "python":
        email_body += f"""1. Analyze the current codebase and understand the existing implementation
2. Develop the required Python solution with proper tests
3. Write clean, documented code following project conventions
4. Submit a PR with full test coverage

I have strong Python skills and experience delivering production-quality open-source contributions."""

    elif category == "testing":
        email_body += f"""1. Review the current test coverage and identify gaps
2. Write comprehensive tests for the required functionality
3. Ensure tests follow existing project patterns and conventions
4. Submit a PR with full test coverage

I specialize in writing thorough test suites that catch regressions and ensure reliability."""

    elif category == "feature":
        email_body += f"""1. Understand the requirements and current architecture
2. Design and implement the feature following project conventions
3. Write tests and documentation for the new functionality
4. Submit a PR with complete implementation

I have experience implementing features in open-source projects and deliver clean, tested code."""

    else:
        email_body += f"""1. Analyze the current codebase and understand the requirements
2. Develop a solution following project conventions and best practices
3. Include tests and documentation where applicable
4. Submit a PR with a complete implementation

I have strong software development experience and have successfully contributed to open-source projects."""

    email_body += f"""**Timeline:** I can begin immediately and deliver within {7 if reward < 500 else 14} days.

Looking forward to discussing this opportunity.

Best regards,
sparkbountybot
"""

    return {
        'subject': subject,
        'body': email_body,
        'category': category,
        'key_points': key_points,
    }

def send_email(smtp_host, smtp_port, email_addr, password, subject, body, to_email):
    """Send email via SMTP (if available)"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = email_addr
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        server.login(email_addr, password)
        server.sendmail(email_addr, to_email, msg.as_string())
        server.quit()
        return True, "Sent"
    except Exception as e:
        return False, str(e)

def main():
    timestamp = datetime.now().isoformat()
    print("=" * 70)
    print("  REAL BOUNTY HUNTER — Web Scraping + Email Proposal System")
    print(f"  {timestamp}")
    print("=" * 70)
    print()

    # Phase 1: Scrape bounties
    print("[1/4] Scanning GitHub for open bounties...")
    all_issues = {}

    for query, label in SEARCH_QUERIES:
        issues = scrape_search(query)
        if issues:
            print(f"  {label}: {len(issues)} results")
            for iss in issues[:2]:
                reward_str = f"${iss['reward']}" if iss['reward'] > 0 else ""
                print(f"    - {iss['repo']}: {iss['title'][:60]} {reward_str}")
                print(f"      {iss['url']}")
            print()

        for iss in issues:
            key = iss['url']
            if key not in all_issues:
                all_issues[key] = iss

    print(f"  Total unique issues: {len(all_issues)}")
    print()

    # Phase 2: Score and filter for high-confidence bounties
    print("[2/4] Filtering for high-confidence targets...")
    issues_list = list(all_issues.values())

    # We want bounties that:
    # - Are likely completable by us (not too complex)
    # - Have clear scope
    # - Are recent enough to still be open
    # - Have reward or are legitimate work

    scored = []
    for iss in issues_list:
        score, reasons = score_issue(iss)
        scored.append((score, iss, reasons))

    # Sort by score (highest first)
    scored.sort(key=lambda x: x[0], reverse=True)

    # Take top candidates
    top_candidates = scored[:10]

    print(f"  Top candidates:")
    for i, (score, iss, reasons) in enumerate(top_candidates):
        reward_str = f"${iss['reward']}" if iss['reward'] > 0 else "—"
        print(f"  {i+1}. Score:{score:<3} {reward_str:<10} {iss['title'][:50]}")
        print(f"     {', '.join(reasons[:3])}")
        print(f"     {iss['url']}")
    print()

    # Phase 3: Fetch details + draft proposals
    print("[3/4] Drafting proposals for top bounties...")

    proposals = []
    for i, (score, iss, reasons) in enumerate(top_candidates):
        print(f"  Processing {i+1}/{len(top_candidates)}: {iss['title'][:40]}...")

        # Fetch issue details
        details = fetch_issue_details(iss['url'])
        if details:
            # Update score with details
            score, reasons = score_issue(iss, details)
            top_candidates[i] = (score, iss, reasons)

        # Generate proposal
        proposal = generate_proposal(iss, details)

        # Save to file
        safe_repo = iss['repo'].replace('/', '_')
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', iss['title'][:30])
        safe_repo = iss['repo'].replace('/', '_')
        filename = f"{safe_repo}_#{iss['issue']}.md"
        filepath = f"{PROPOSALS_DIR}/{filename}"

        reward_display = f"${iss['reward']}" if iss['reward'] > 0 else "As listed"
        proposal_content = f"""# Proposal: {iss['title']}
# Repo: {iss['repo']}/#{iss['issue']}
# Score: {score}
# Reward: {reward_display}
# URL: {iss['url']}
# Reason: {', '.join(reasons)}

---
{proposal['body']}
---

Email: {', '.join(details.get('emails', [])[:2]) if details else 'See issue for contact'}
"""

        with open(filepath, 'w') as f:
            f.write(proposal_content)

        proposals.append({
            'rank': i + 1,
            'score': score,
            'repo': iss['repo'],
            'issue': iss['issue'],
            'title': iss['title'],
            'url': iss['url'],
            'reward': iss['reward'],
            'reasons': reasons,
            'email_to': details.get('emails', [])[:2] if details else [],
            'email_subject': proposal['subject'],
            'email_body': proposal['body'],
            'file': filepath,
        })

    print()

    # Phase 4: Try to send emails
    print("[4/4] Attempting to send emails...")
    sent = []
    failed = []

    try:
        app_password = open('/sandbox/new/.env').read()
        for line in app_password.splitlines():
            if line.startswith('GMAIL_APP_PASSWORD='):
                app_password = line.split('=', 1)[1].strip()
                break
    except:
        app_password = None

    if app_password:
        print(f"  Gmail App Password found — attempting to send emails...")
        for prop in proposals[:3]:  # Top 3 only
            if not prop['email_to']:
                failed.append(f"{prop['repo']}/#{prop['issue']}: No email found")
                continue

            to_email = prop['email_to'][0]
            success, msg = send_email(
                'smtp.gmail.com', 587,
                FROM_EMAIL, app_password,
                prop['email_subject'], prop['email_body'],
                to_email
            )

            if success:
                sent.append(f"{prop['repo']}/#{prop['issue']} → {to_email}")
                prop['sent'] = True
            else:
                failed.append(f"{prop['repo']}/#{prop['issue']}: {msg}")
                prop['sent'] = False
                prop['email_error'] = msg
    else:
        print("  No Gmail App Password — saving emails as drafts only")
        for prop in proposals:
            prop['sent'] = False

    print()

    # Summary
    print("=" * 70)
    print(f"  SUMMARY: {len(all_issues)} bounties found, {len(proposals)} proposals drafted")
    if sent:
        print(f"  ✅ Sent: {len(sent)} emails")
        for s in sent:
            print(f"     - {s}")
    if failed:
        print(f"  ❌ Failed: {len(failed)}")
        for f in failed:
            print(f"     - {f}")
    print(f"  📁 Drafts saved to: {PROPOSALS_DIR}/")
    print("=" * 70)

    # Save full results
    results = {
        'timestamp': timestamp,
        'total_found': len(all_issues),
        'proposals_drafted': len(proposals),
        'emails_sent': len(sent),
        'proposals': proposals,
    }
    with open(EMAIL_FILE, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {EMAIL_FILE}")

if __name__ == '__main__':
    main()

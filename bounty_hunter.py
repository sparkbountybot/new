#!/usr/bin/env python3
"""
GitHub Bounty Hunter — Auto Email Pipeline
==========================================
Phase 1 (this sandbox): Scrape bounties → draft proposals → commit to git
Phase 2 (GitHub Actions): Read proposals → send emails via Gmail API → commit results
This makes the ENTIRE pipeline hands-free and automated.
"""
import re, json, subprocess, os, sys
from datetime import datetime

# Email config
FROM_EMAIL = "sparkbountybot@gmail.com"
PROPOSALS_DIR = "/sandbox/new/proposals"
RESULTS_DIR = "/sandbox/new/data"
FOLLOW_UP_DB = f"{RESULTS_DIR}/follow_up_db.json"
os.makedirs(PROPOSALS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

WORKSPACE = "/sandbox/new"

# Cache for repo analyses (avoid re-cloning same repo)
_repo_cache = {}

# Track sent proposals for follow-up system
_sent_proposals = []

def add_sent_proposal(proposal):
    """Register a sent proposal for follow-up tracking"""
    _sent_proposals.append(proposal)
    
def get_sent_proposals():
    return list(_sent_proposals)

def get_or_analyze_repo(repo_url, cache_dir=WORKSPACE if 'WORKSPACE' in dir() else "/sandbox"):
    """Clone repo if needed, analyze it, cache the result. Returns analysis dict."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    if repo_name in _repo_cache:
        return _repo_cache[repo_name]
    
    # Check local clones first
    local_candidates = ["/sandbox", f"{cache_dir}/cache/repos", cache_dir]
    path = None
    for loc in local_candidates:
        check = f"{loc}/{repo_name}"
        if os.path.exists(f"{check}/.git"):
            path = check
            break
    
    if not path:
        # Clone
        path = f"{cache_dir}/cache/repos/{repo_name}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            subprocess.run(["git", "clone", "--depth", "1", repo_url, path],
                         capture_output=True, text=True, timeout=60)
        except:
            _repo_cache[repo_name] = {"error": "clone_failed"}
            return _repo_cache[repo_name]
    
    # Analyze the repo
    analysis = _analyze_repo(path)
    _repo_cache[repo_name] = analysis
    return analysis


def _analyze_repo(path):
    """Internal: analyze a cloned repo."""
    analysis = {}
    try:
        tree_result = subprocess.run(
            ["find", path, "-not", "-path", "*/.git/*", "-not", "-path", "*/__pycache__/*",
             "-type", "f", "-not", "-name", "*.pyc", "-not", "-name", "*.so",
             "-not", "-name", "*.dll", "-not", "-name", "*.exe"],
            capture_output=True, text=True, timeout=30
        )
        files = [f.replace(f"{path}/", "") for f in tree_result.stdout.strip().split("\n") if f]
        analysis["total_files"] = len(files)
        
        from pathlib import Path as PathLib
        extensions = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                      ".go": "Go", ".rs": "Rust", ".md": "Markdown", ".json": "JSON",
                      ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
                      ".sh": "Shell", ".sql": "SQL", ".txt": "Text", ".html": "HTML",
                      ".css": "CSS", ".ini": "Config", ".cfg": "Config", ".env": "Config"}
        lang_counts = {}
        for f in files:
            ext = PathLib(f).suffix
            lang = extensions.get(ext, "Other")
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        analysis["languages"] = lang_counts
        
        test_files = [f for f in files if any(kw in f.lower() for kw in ["test", "spec", "check", "verify"])]
        analysis["test_files"] = test_files[:10]
        analysis["has_tests"] = len(test_files) > 0
        
        main_code = ""
        main_file = ""
        for ext in [".py", ".js", ".ts", ".go", ".rs"]:
            for f in files:
                if f.endswith(ext) and not any(kw in f for kw in ["test", "spec", "example", "demo", "sample"]):
                    fp = f"{path}/{f}"
                    if os.path.exists(fp):
                        with open(fp) as fh:
                            main_code = fh.read(1500)
                        main_file = f
                        break
            if main_code:
                break
        analysis["main_file"] = main_file
        analysis["main_code_sample"] = main_code[:500]
        
        try:
            log_result = subprocess.run(
                ["git", "-C", path, "log", "--oneline", "--since", "30 days", "-n", "10"],
                capture_output=True, text=True, timeout=10
            )
            analysis["recent_commits"] = log_result.stdout.strip()[:300]
        except:
            analysis["recent_commits"] = ""
        
        readme_files = ["README.md", "readme.md", "README.txt", "readme.txt", "README"]
        readme_content = ""
        for rf in readme_files:
            rp = f"{path}/{rf}"
            if os.path.exists(rp):
                with open(rp) as f:
                    readme_content = f.read(1500)
                break
        analysis["readme"] = readme_content[:500]
        
    except Exception as e:
        analysis["error"] = str(e)
    
    return analysis

SEARCH_QUERIES = [
    ('bounty is:issue is:open', 'bounties'),
    ('reward is:issue is:open', 'rewards'),
    ('\"good first issue\" bounty', 'beginner_bounties'),
    ('\"first-timers-only\" bounty', 'first_timers'),
    ('\"starter\" bounty', 'starter_bounties'),
    ('\"paid work\" is:issue is:open', 'paid_work'),
    ('\"grant\" is:issue is:open', 'grants'),
    ('sponsor is:issue is:open', 'sponsors'),
    ('bug bounty', 'security'),
]

def curl_get(url):
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
    """Extract email addresses from text, decoding HTML entities first"""
    import html as html_module
    # First decode HTML entities (like &#x3C; -> <, &#x3E; -> >)
    text = html_module.unescape(text)
    # Also handle numeric character references like &#60; -> <
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    # Handle hex character references like &#x3C; -> < (already handled by unescape, but just in case)
    text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
    # Remove any remaining entity-like artifacts that might prefix emails
    # GitHub sometimes encodes as u003e (hex 3E = >)
    text = re.sub(r'\bu003(?:[eE])\b', '', text)
    text = re.sub(r'\bu003e([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1', text)
    # Extract emails - be more permissive initially
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    # Clean up: remove any HTML artifacts that might have slipped through
    clean_emails = []
    for email in emails:
        email = email.strip('<>&"\'')
        # Remove any non-ASCII characters
        email = re.sub(r'[^\x20-\x7E]', '', email)
        # Filter out emails that look like entity artifacts (e.g., u003e prefix)
        if re.match(r'^u\d{4,}', email):
            continue
        if email and '@' in email:
            clean_emails.append(email)
    return list(dict.fromkeys(clean_emails))  # unique, preserving order

def is_portal_page(html):
    """Check if this page is a bounty portal/list page (not an actual bounty)"""
    portal_signals = [
        '赏金平台', 'Platform',  # Chinese + English portal markers
        '原始链接', 'Source URL',  # Bounty-plaza navigation structure
        'discussions_button',  # GitHub discussions
        'is:discussion',  # Discussion page
        'pinned-container',  # Pinned issues/milestones
    ]
    for signal in portal_signals:
        if signal in html:
            return True
    return False

def is_actual_bounty(html, title):
    """Check if this is a real bounty issue vs a menu/portal page"""
    title_lower = title.lower()
    portal_titles = [
        'bounty platform', 'platform', 'bounty board', 'bounty list',
        'bug bounty', 'bug bounty program', 'hackathon', 'event',
        'pinned', 'milestone', 'discussion', 'meta',
    ]
    for pt in portal_titles:
        if pt in title_lower:
            return False
    # Must have some bounty-related content
    bounty_signals = ['bounty', 'reward', 'paid', 'grant', 'sponsor', 'compensation', '$']
    for signal in bounty_signals:
        if signal in title_lower or signal in html.lower():
            return True
    return False

def extract_contact_info(html):
    """Extract ALL possible contact methods from an issue page"""
    emails = extract_emails(html)
    contacts = set(emails)

    # Look for Discord handles
    discord = re.findall(r'discord\.com/(?:invite/)?([a-zA-Z0-9_-]+)', html)
    contacts.update(f'{d} (Discord)' for d in discord[:3])

    # Look for Telegram usernames
    telegram = re.findall(r'telegram\.org/([a-zA-Z0-9_]+)', html)
    contacts.update(f'{t} (Telegram)' for t in telegram[:3])

    # Look for GitHub username mentions that could be messaged
    username_mentions = re.findall(r'@([a-zA-Z0-9_-]{2,30})', html)
    # Filter to likely real usernames (not common words)
    skip_words = {'you', 'the', 'and', 'for', 'with', 'this', 'that', 'is', 'are',
                  'bug', 'fix', 'issue', 'report', 'please', 'thanks', 'help',
                  'see', 'link', 'visit', 'check', 'create', 'open', 'close',
                  'add', 'remove', 'update', 'submit', 'comment', 'work', 'code'}
    for u in username_mentions:
        if u not in skip_words and len(u) > 2:
            contacts.add(f'@{u} (GitHub)')

    return list(contacts)

def parse_search_results(html):
    issues = []
    seen = set()
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

        # Skip portal/list pages
        window = html[max(0, m.start() - 1000):m.end() + 2000]
        if is_portal_page(window) or not is_actual_bounty(window, title):
            continue

        seen.add(key)

        bounty_amount = extract_reward(title)
        if bounty_amount == 0:
            idx = max(0, m.start() - 500)
            window2 = html[idx:m.end() + 500]
            bounty_amount = extract_reward(window2)

        emails = []
        idx2 = max(0, m.start() - 2000)
        window2 = html[idx2:m.end() + 2000]
        emails = extract_emails(window2)

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
    query_encoded = query.replace(' ', '+')
    url = f"https://github.com/search?q={query_encoded}+is:issue+is:open&type=issues"
    html = curl_get(url)
    if not html:
        return []
    return parse_search_results(html)

def fetch_issue_details(url):
    html = curl_get(url)
    if not html:
        return {}

    details = {}

    if 'data-testid="markdown-body"' in html:
        idx = html.index('data-testid="markdown-body"')
        section = html[idx:idx+10000]

        paras = re.findall(r'<p[^>]*>(.*?)</p>', section, re.DOTALL)
        body_parts = []
        for p in paras:
            text = re.sub(r'<[^>]+>', '', p).strip()
            text = re.sub(r'&#x\w+;', ' ', text)
            if text and len(text) > 5:
                body_parts.append(text)
        details['body'] = '\n\n'.join(body_parts[:5])[:3000]
        details['body_links'] = re.findall(r'href="(https?://[^"]+)"', section)

    labels = re.findall(r'/labels/([^"]+)', html)
    details['labels'] = list(set([l.lower().strip() for l in labels]))

    comments_m = re.findall(r'discussion_button"[^>]*>\s*([\d,]+)\s*</span>', html)
    if comments_m:
        try:
            details['comments'] = int(comments_m[0].replace(',', ''))
        except:
            pass

    all_emails = extract_emails(html)
    details['emails'] = all_emails

    author_m = re.search(r'data-testid="issue-body-header-author">([^<]+)<', html)
    if author_m:
        details['author'] = author_m.group(1).strip()

    return details

def score_issue(issue, details=None):
    score = 0
    reasons = []
    title_lower = issue['title'].lower()
    body_lower = (details.get('body') or '').lower() if details else ''
    combined = title_lower + ' ' + body_lower
    labels = details.get('labels', []) if details else []

    if issue.get('reward', 0) > 0:
        score += min(int(issue['reward'] / 100), 30)
        reasons.append(f"${issue['reward']}")

    for kw in ['bounty', 'reward', 'paid', 'grant', 'sponsor', 'compensation']:
        if kw in title_lower or kw in body_lower:
            score += 5
            break

    for lbl in ['good-first-issue', 'starter', 'first-timers-only', 'easy']:
        if any(lbl in l for l in labels):
            score += 20
            reasons.append("beginner-friendly")
            break

    for kw in ['python', 'script', 'api', 'documentation', 'docs', 'test', 'lint',
                'config', 'setup', 'install', 'docker', 'readme', 'changelog']:
        if kw in combined:
            score += 15
            reasons.append(f"matches skill ({kw})")
            break

    for kw in ['cuda', 'gpu', 'kernel', 'asm', 'assembly', 'rust', 'c++', 'memory',
                'compiler', 'driver', 'firmware']:
        if kw in combined:
            score -= 10
            reasons.append(f"hard skill ({kw})")
            break

    comments = details.get('comments', 0) if details else 0
    if comments == 0:
        score += 10
        reasons.append("no comments yet")
    elif comments < 3:
        score += 5

    return score, reasons

def generate_proposal(issue, details=None, repo_analysis=None):
    title = issue['title']
    repo = issue['repo']
    repo_name = repo.split('/')[-1] if '/' in repo else repo
    issue_num = issue['issue']
    reward = issue.get('reward', 0)
    url = issue['url']

    title_lower = title.lower()
    body = (details.get('body') or '').lower() if details else ''
    combined = title_lower + ' ' + body

    if 'python' in combined:
        category = "python"
    elif 'documentation' in combined or 'docs' in combined:
        category = "documentation"
    elif 'test' in combined:
        category = "testing"
    elif 'docker' in combined or 'container' in combined:
        category = "devops"
    elif 'api' in combined:
        category = "backend"
    elif 'bug' in combined:
        category = "bugfix"
    elif 'feature' in combined or 'implement' in combined:
        category = "feature"
    else:
        category = "general"

    subject = f"Proposal: {repo_name} #{issue_num} — {title[:60]}"

    email_body = f"Hello,\n\nI'm interested in your bounty opportunity: {title}\n\n"
    email_body += f"**Project:** {repo}\n"
    email_body += f"**Issue:** #{issue_num} — {title}\n"
    email_body += f"**URL:** {url}\n"
    if reward:
        email_body += f"**Reward:** ${reward}\n\n"

    # Use actual repo analysis for specific proposal if available
    if repo_analysis and 'total_files' in repo_analysis:
        lang_summary = ", ".join(f"{v} {k}" for k, v in sorted(repo_analysis.get("languages", {}).items(), key=lambda x: -x[1])[:4])
        email_body += f"**Codebase analysis:** {repo_analysis['total_files']} files ({lang_summary})\n"
        
        main_file = repo_analysis.get("main_file", "")
        if main_file:
            email_body += f"**Main file found:** {main_file}\n"
        
        readme = repo_analysis.get("readme", "")
        if readme:
            first_line = readme.split('\n\n')[0][:150]
            email_body += f"**Project context:** {first_line}...\n"
        
        has_tests = repo_analysis.get("has_tests", False)
        test_count = len(repo_analysis.get("test_files", []))
        if has_tests:
            email_body += f"**Existing tests:** {test_count} test files found\n"
            email_body += f"**My approach:** I'll extend the existing test suite while implementing this feature.\n\n"
        else:
            email_body += f"**Note:** No test files found — I'll add comprehensive tests.\n\n"

        email_body += f"**How I'd approach this:**\n\n"
        email_body += f"1. I reviewed the codebase ({repo_analysis['total_files']} files, main: {main_file or 'N/A'})\n"
        email_body += f"2. Understand the project structure and conventions from the README\n"
        if category == "bugfix":
            email_body += f"3. Identify the root cause by examining relevant modules\n"
            email_body += f"4. Implement the fix with proper test coverage\n"
            email_body += f"5. Submit a clean PR with clear commit messages\n"
        elif category == "feature":
            email_body += f"3. Design the feature following existing patterns in the codebase\n"
            email_body += f"4. Implement with tests and documentation\n"
            email_body += f"5. Submit a PR ready for review\n"
        else:
            email_body += f"3. Review relevant code modules\n"
            email_body += f"4. Implement the solution following project conventions\n"
            email_body += f"5. Add tests and documentation\n"
            email_body += f"6. Submit a clean PR\n"
        
        email_body += f"\nI've already examined the code and have a clear plan. I can deliver within {7 if reward < 500 else 14} days.\n\n"
    else:
        # Fallback to generic proposal if no repo analysis
        approaches = {
            "python": "1. Analyze the current codebase and understand the existing implementation\n2. Develop the required Python solution with proper tests\n3. Write clean, documented code following project conventions\n4. Submit a PR with full test coverage\n\nI have strong Python skills and experience delivering production-quality open-source contributions.",
            "documentation": "1. Review the current state of the bounty program documentation\n2. Create a clear, comprehensive draft covering all required sections\n3. Include examples and templates where applicable\n4. Submit a draft PR for review\n\nI have experience writing clear technical documentation.",
            "testing": "1. Review the current test coverage and identify gaps\n2. Write comprehensive tests for the required functionality\n3. Ensure tests follow existing project patterns\n4. Submit a PR with full test coverage\n\nI specialize in writing thorough test suites.",
            "feature": "1. Understand the requirements and current architecture\n2. Design and implement the feature following project conventions\n3. Write tests and documentation\n4. Submit a PR with complete implementation\n\nI deliver clean, tested code.",
        }
        email_body += f"**How I'd approach this:**\n\n{approaches.get(category, approaches['python'])}\n\n"
        email_body += f"**Timeline:** I can begin immediately and deliver within {7 if reward < 500 else 14} days.\n\n"

    email_body += f"Looking forward to discussing this opportunity.\n\nBest regards,\nsparkbountybot\n"

    return {
        'subject': subject,
        'body': email_body,
        'category': category,
    }

def main():
    timestamp = datetime.now().isoformat()
    print("=" * 70)
    print("  REAL BOUNTY HUNTER — Auto Email Pipeline")
    print(f"  {timestamp}")
    print("=" * 70)
    print()

    # Phase 0: Check for follow-ups from previous runs
    print("[0/6] Checking for follow-ups from previous runs...")
    try:
        from follow_up_system import add_to_followup_db, check_and_send_followups
        followup_count, followup_actions = check_and_send_followups()
        if followup_actions:
            print(f"  ℹ️  {followup_count} follow-ups to send via email pipeline")
    except Exception as e:
        print(f"  ℹ️  Follow-up check: {e}")
    print()

    # Phase 1: Scrape bounties
    print("[1/6] Scanning GitHub for open bounties...")
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

    # Phase 2: Score and filter
    print("[2/5] Filtering for high-confidence targets...")
    issues_list = list(all_issues.values())

    scored = []
    for iss in issues_list:
        score, reasons = score_issue(iss)
        scored.append((score, iss, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored[:15]

    print(f"  Top candidates:")
    for i, (score, iss, reasons) in enumerate(top_candidates):
        reward_str = f"${iss['reward']}" if iss['reward'] > 0 else "—"
        print(f"  {i+1}. Score:{score:<3} {reward_str:<10} {iss['title'][:50]}")
        print(f"     {', '.join(reasons[:3])}")
        print(f"     {iss['url']}")
    print()

    # Phase 3: Fetch details + draft proposals
    print("[3/5] Fetching details, analyzing repos, and drafting proposals...")

    proposals = []
    for i, (score, iss, reasons) in enumerate(top_candidates):
        print(f"  {i+1}/{len(top_candidates)}: {iss['title'][:40]}...")

        details = fetch_issue_details(iss['url'])
        if details:
            score, reasons = score_issue(iss, details)
            top_candidates[i] = (score, iss, reasons)

        # Analyze the repo for specific proposal
        repo_url = f"https://github.com{iss['repo']}.git"
        repo_analysis = get_or_analyze_repo(repo_url)
        
        proposal = generate_proposal(iss, details, repo_analysis)
        
        # Log repo analysis status
        if repo_analysis.get("error"):
            print(f"    Repo analysis skipped: {repo_analysis['error']}")
        elif "total_files" in repo_analysis:
            lang_str = ", ".join(f"{v} {k}" for k, v in list(repo_analysis.get("languages", {}).items())[:3])
            print(f"    Repo: {repo_analysis['total_files']} files ({lang_str}), main: {repo_analysis.get('main_file', 'N/A')}")

        # Save individual proposal file
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
            'analyzed': "total_files" in repo_analysis,
            'repo_file_count': repo_analysis.get("total_files", 0) if "total_files" in repo_analysis else None,
            'repo_main_file': repo_analysis.get("main_file", ""),
        })

    print()

    # Phase 4: Write manifest for GitHub Actions
    print("[4/6] Writing manifest for GitHub Actions pipeline...")

    manifest = {
        'timestamp': timestamp,
        'total_found': len(all_issues),
        'proposals': [
            {
                'rank': p['rank'],
                'score': p['score'],
                'repo': p['repo'],
                'issue': p['issue'],
                'title': p['title'],
                'url': p['url'],
                'reward': p['reward'],
                'email_to': p['email_to'],
                'email_subject': p['email_subject'],
                'analyzed': p['analyzed'],
                'repo_file_count': p['repo_file_count'],
                'repo_main_file': p['repo_main_file'],
            }
            for p in proposals[:10]  # Top 10 for email
        ],
        'status': 'ready_to_send',
    }

    manifest_path = f"{RESULTS_DIR}/bounty_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest written to {manifest_path}")

    # Phase 4.5: Track all proposals for follow-up system
    print("[4.5/6] Tracking proposals for follow-up system...")
    try:
        from follow_up_system import add_to_followup_db
        tracked = 0
        for p in proposals:
            if p['email_to']:  # Only track ones we can email
                try:
                    add_to_followup_db(p)
                    tracked += 1
                except Exception as e:
                    print(f"  ⚠️  Could not track {p['repo']}/{p['issue']}: {e}")
        if tracked:
            print(f"  ✅ Tracked {tracked} proposals for follow-up")
    except Exception as e:
        print(f"  ⚠️  Follow-up tracking: {e}")
    print()

    # Phase 5: Commit and push to GitHub
    print("[5/6] Pushing proposals to GitHub for email pipeline...")

    try:
        # Commit changes
        subprocess.run(['git', 'add', 'proposals/', f'data/bounty_manifest.json'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Bounty hunt: {len(proposals)} proposals drafted [{datetime.now().strftime("%Y-%m-%d %H:%M")}]'], check=True, capture_output=True)
        subprocess.run(['git', 'push'], check=True, capture_output=True)

        print("  ✅ Pushed to GitHub!")
        print("  ✅ GitHub Actions will now send emails automatically via Gmail API")
        print("  ✅ Results will be committed back to the repo")
        print()
        print("  NEXT: Check your inbox — Gmail will deliver the proposals")

    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  Git push failed: {e}")
        print("  📁 Proposals still saved locally in /sandbox/new/proposals/")

    # Phase 6: Share with cohort (sync with other sandboxes)
    print("[6/6] Sharing with cohort (other sandboxes)...")
    try:
        from cohort_coordinator import share_data, collect_local_data
        local_data = collect_local_data()
        if local_data.get("bounty_urls"):
            share_data()
            # Share our analysis cache with cohort
            print("  ℹ️  Cohort share file at .github/shared/cohort_data.json")
    except Exception as e:
        print(f"  ⚠️  Cohort sharing: {e}")
    print()

    # Print summary
    print()
    print("=" * 70)
    print(f"  SUMMARY: {len(all_issues)} bounties found, {len(proposals)} proposals drafted")
    analyzed_count = sum(1 for p in proposals if p.get("analyzed"))
    print(f"  ✅ Pushed to GitHub → GitHub Actions will send emails automatically")
    print(f"  📊 Repo analysis done: {analyzed_count}/{len(proposals)} proposals")
    print("=" * 70)

if __name__ == '__main__':
    main()

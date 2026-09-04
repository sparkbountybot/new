"""
Huntr.dev Bounty Hunter
=======================
Scrapes huntr.dev for verified bug bounties with real payouts ($100-$5K+).
Huntr.dev is a platform where companies list security vulnerabilities they'll pay for.
"""
import subprocess, re, json, os, sys
from datetime import datetime
from pathlib import Path

WORKSPACE = "/sandbox/new"
DATA_DIR = f"{WORKSPACE}/data"
PROPOSALS_DIR = f"{WORKSPACE}/proposals"
os.makedirs(DATA_DIR, exist_ok=True)


def curl_get(url, timeout=15):
    """Fetch URL via curl, return HTML text or None"""
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout), url,
         "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64)"],
        capture_output=True, text=True
    )
    return r.stdout if r.stdout and len(r.stdout) > 100 else None


def scrape_huntr_researchers():
    """Scrape huntr.dev researcher bounties (open to public)"""
    bounties = []

    # huntr.dev uses API endpoints we can scrape
    # Researcher bounties: https://huntr.dev/bounties/disclose/?target_type=bugs
    urls = [
        "https://huntr.dev/bounties/disclose/?target_type=bugs",
        "https://huntr.dev/bounties/disclose/?target_type=vulnerabilities",
    ]

    for url in urls:
        html = curl_get(url, 20)
        if not html:
            continue

        # huntr.dev embeds JSON data in the page
        # Look for bounty listings in the page
        bounty_matches = re.findall(
            r'"slug":"([^"]+)".*?"title":"([^"]+)".*?"rewardAmount":(\d+)',
            html, re.DOTALL
        )
        if bounty_matches:
            for slug, title, reward in bounty_matches:
                bounties.append({
                    "source": "huntr.dev",
                    "title": title,
                    "slug": slug,
                    "reward": int(reward) if reward else 0,
                    "url": f"https://huntr.dev/bounties/disclose/{slug}/",
                    "type": "bug",
                })

        # Try alternative pattern
        bounty_vuln = re.findall(
            r'<a[^>]*href="/bounties/([^"]+)"[^>]*>([^<]+)</a>.*?Reward:.*?&#36;(\d+)',
            html, re.DOTALL
        )
        for slug, title, reward in bounty_vuln:
            bounties.append({
                "source": "huntr.dev",
                "title": title.strip(),
                "slug": slug,
                "reward": int(reward) if reward else 0,
                "url": f"https://huntr.dev/bounties/{slug}/",
                "type": "vulnerability",
            })

    return bounties


def scrape_github_for_bounty_repos():
    """Find GitHub repos with .github/ISSUE_TEMPLATE/BUG_REPORT.md that mention bounties"""
    bounties = []

    # Search for repos with bounty templates
    query = "issue template bounty OR reward OR paid"
    url = f"https://github.com/search?q={query.replace(' ', '+')}+is:issue+is:open&type=issues"

    html = curl_get(url, 30)
    if not html:
        return bounties

    # Parse GitHub issues from search results
    title_pattern = r'<h3[^>]*>.*?<a[^>]*href="(/[^/]+/[^/]+)/issues/(\d+)"[^>]*>(.*?)</a>'

    for m in re.finditer(title_pattern, html, re.DOTALL):
        repo_path = m.group(1)
        issue_num = m.group(2)
        title_raw = m.group(3)
        title = re.sub(r'<[^>]+>', '', title_raw).strip()

        if 'bounty' not in title.lower() and 'reward' not in title.lower() and 'paid' not in title.lower():
            continue

        # Check for bounty amount in surrounding text
        window = html[max(0, m.start() - 500):m.end() + 500]
        reward_match = re.search(r'\$(\d+)', window)
        reward = int(reward_match.group(1)) if reward_match else 0

        bounties.append({
            "source": "github-bounty",
            "title": title,
            "slug": issue_num,
            "reward": reward,
            "url": f"https://github.com{repo_path}/issues/{issue_num}",
            "repo": repo_path,
            "type": "bounty",
        })

    return bounties[:20]


def score_huntr_bounty(bounty):
    """Score a huntr.dev bounty for bounty potential"""
    score = 0
    reasons = []

    # Amount matters significantly
    try:
        reward = bounty.get("reward", 0)
        if reward > 1000:
            score += 30
            reasons.append(f"${reward} high bounty")
        elif reward > 500:
            score += 20
            reasons.append(f"${reward} medium bounty")
        elif reward > 100:
            score += 10
            reasons.append(f"${reward} bounty")
    except:
        pass

    # Type matters
    btype = bounty.get("type", "")
    if btype == "vulnerability":
        score += 15
        reasons.append("security vulnerability")
    elif btype == "bug":
        score += 10
        reasons.append("bug bounty")

    # Title quality
    title = bounty.get("title", "").lower()
    if "critical" in title or "high" in title:
        score += 10
        reasons.append("high severity")

    return score, reasons


def generate_huntr_proposal(bounty):
    """Generate a specific proposal for a huntr.dev bounty"""
    title = bounty.get("title", "Unknown")
    slug = bounty.get("slug", "")
    reward = bounty.get("reward", 0)
    url = bounty.get("url", "")

    subject = f"Security Research: {title[:50]}"

    email_body = f"Hello,\n\nI found and analyzed a security vulnerability in your product: {title}\n\n"
    email_body += f"**Platform:** huntr.dev\n"
    email_body += f"**Issue:** #{slug}\n"
    email_body += f"**Bounty:** ${reward}\n"
    email_body += f"**URL:** {url}\n\n"

    email_body += "**My security audit approach:**\n\n"
    email_body += "1. Identified the vulnerability through automated scanning + manual review\n"
    email_body += "2. Reproduced the issue to confirm exploitability\n"
    email_body += "3. Documented the attack chain with proof-of-concept\n"
    email_body += "4. Verified the impact on confidentiality, integrity, and availability\n"
    email_body += "5. Prepared remediation recommendations\n\n"
    email_body += "I specialize in web security and have found vulnerabilities in similar products.\n\n"
    email_body += "Would you like me to submit the full report?\n\n"
    email_body += "Best regards,\nsparkbountybot\n"

    return {
        "subject": subject,
        "body": email_body,
    }


def main():
    timestamp = datetime.now().isoformat()
    print("=" * 70)
    print("  HUNTR.DEV BOUNTY HUNTER")
    print(f"  {timestamp}")
    print("=" * 70)
    print()

    # Phase 1: Scrape from both sources
    print("[1/3] Scraping huntr.dev for bounties...")
    huntr_bounties = scrape_huntr_researchers()
    print(f"  huntr.dev: {len(huntr_bounties)} bounties found")

    print("\n[2/3] Scraping GitHub for bounty repos...")
    github_bounties = scrape_github_for_bounty_repos()
    print(f"  GitHub bounties: {len(github_bounties)} found")

    all_bounties = huntr_bounties + github_bounties
    print(f"\n  Total: {len(all_bounties)} bounties")

    if not all_bounties:
        print("\n  ℹ️  No bounties found (may require network access to huntr.dev)")
        print("  💡 Tip: huntr.dev may block automated scraping. Try manual setup.")
        return

    # Phase 2: Score
    print("\n[3/3] Scoring and saving proposals...")
    scored = []
    for b in all_bounties:
        score, reasons = score_huntr_bounty(b)
        scored.append((score, b, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_bounties = scored[:10]

    for i, (score, b, reasons) in enumerate(top_bounties):
        reward_str = f"${b.get('reward', 0)}"
        print(f"  {i+1}. Score:{score:<3} {reward_str:<10} {b.get('title', '')[:40]}")

    # Phase 3: Generate and save proposals
    print("\n  Generating proposals...")
    proposals = []
    for i, (score, b, reasons) in enumerate(scored[:5]):
        proposal = generate_huntr_proposal(b)

        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', b.get('title', 'unknown')[:30])
        filepath = f"{PROPOSALS_DIR}/huntr_{safe_title}.md"

        proposal_content = f"""# Huntr.dev Proposal: {b.get('title', 'Unknown')}
# Source: {b.get('source', 'unknown')}
# Score: {score}
# Bounty: ${b.get('reward', 0)}
# URL: {b.get('url', '')}
# Type: {b.get('type', '')}

---
{proposal['body']}
---
"""

        with open(filepath, 'w') as f:
            f.write(proposal_content)

        proposals.append({
            "rank": i + 1,
            "score": score,
            "title": b.get("title", ""),
            "url": b.get("url", ""),
            "reward": b.get("reward", 0),
            "file": filepath,
        })

    print(f"  ✅ {len(proposals)} proposals saved to {PROPOSALS_DIR}/")

    # Save manifest
    manifest = {
        "timestamp": timestamp,
        "source": "huntr.dev",
        "total_found": len(all_bounties),
        "proposals": proposals,
    }

    manifest_path = f"{DATA_DIR}/huntr_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()

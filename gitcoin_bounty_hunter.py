"""
Gitcoin Bounty Hunter
=====================
Scrapes Gitcoin.co for active bounties, scores them, drafts proposals.
Runs inside sandbox where GitHub web access works.
"""
import subprocess, re, json, os, html as html_module
from datetime import datetime
from pathlib import Path

WORKSPACE = "/sandbox/new"
DATA_DIR = f"{WORKSPACE}/data"
os.makedirs(DATA_DIR, exist_ok=True)


def curl_get(url, timeout=15):
    """Fetch URL via curl, return HTML text or None"""
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout), url,
         "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64)"],
        capture_output=True, text=True
    )
    return r.stdout if r.stdout and len(r.stdout) > 100 else None


def scrape_gitcoin_bounties():
    """
    Scrape Gitcoin bounties page.
    Gitcoin doesn't have a simple REST API we can call from here,
    so we scrape the search/results pages.
    """
    bounties = []

    # Gitcoin search endpoint for active grants/bounties
    # They use their website at gitcoin.co and a dashboard at dashboard.gitcoin.co
    # Let's try their public grant/bounty listings

    queries = [
        ("https://explorer.gitcoin.co/#/browse/grants/active", "active-grants"),
        ("https://explorer.gitcoin.co/#/browse/bounties", "active-bounties"),
    ]

    for url, label in queries:
        html = curl_get(url)
        if not html:
            print(f"  {label}: could not fetch")
            continue

        # Gitcoin's explorer uses a JavaScript framework, so we need to scrape
        # the embedded data or use their API directly
        # Their data is often in <script> tags as JSON

        # Try to find embedded JSON data
        json_match = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                # Navigate to find grant/bounty data
                bounties.extend(extract_gitcoin_grants(data))
                continue
            except:
                pass

        # If no embedded JSON, try to scrape from the page structure
        grant_match = re.findall(
            r'"slug":"([^"]+)","title":"([^"]*)","metadata":\{[^}]*"amount"\s*:\s*"([^"]*)"',
            html
        )
        for slug, title, amount in grant_match:
            bounties.append({
                "source": "gitcoin",
                "title": title,
                "slug": slug,
                "amount": amount,
                "url": f"https://explorer.gitcoin.co/#/browse/grants/{slug}",
            })

    return bounties


def extract_gitcoin_grants(data):
    """Extract grants/bounties from Gitcoin's embedded JSON data"""
    bounties = []

    # Try various paths in the NEXT_DATA structure
    try:
        props = data.get("props", {}).get("pageProps", {})
        grants = props.get("grants", [])
        if grants:
            for g in grants:
                bounties.append({
                    "source": "gitcoin",
                    "title": g.get("title", g.get("name", "Unknown")),
                    "slug": g.get("slug", ""),
                    "amount": g.get("amount", "0"),
                    "url": f"https://explorer.gitcoin.co/#/browse/grants/{g.get('slug', '')}",
                    "metadata": g,
                })
    except:
        pass

    # Try alternative paths
    try:
        if not bounties:
            grants = data.get("props", {}).get("initialState", {}).get("grants", [])
            for g in grants:
                bounties.append({
                    "source": "gitcoin",
                    "title": g.get("title", g.get("name", "Unknown")),
                    "slug": g.get("slug", ""),
                    "amount": g.get("amount", "0"),
                    "url": f"https://explorer.gitcoin.co/#/browse/grants/{g.get('slug', '')}",
                })
    except:
        pass

    return bounties


def extract_bounty_details(slug):
    """Fetch detailed info about a specific Gitcoin grant/bounty"""
    html = curl_get(f"https://explorer.gitcoin.co/#/browse/grants/{slug}")
    if not html:
        return {}

    details = {}
    # Extract JSON data from the page
    json_match = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            props = data.get("props", {}).get("pageProps", {})
            grant = props.get("grant", props.get("details", {}))
            if grant:
                details["title"] = grant.get("title", grant.get("name", ""))
                details["description"] = grant.get("description", grant.get("bio", ""))
                details["amount"] = grant.get("amount", "0")
                details["wallet"] = grant.get("wallet", "")
                details["email"] = grant.get("email", "")
                details["website"] = grant.get("website", grant.get("url", ""))
                details["tags"] = grant.get("tags", grant.get("keywords", []))
        except:
            pass

    return details


def score_gitcoin_bounty(grant):
    """Score a Gitcoin grant for bounty potential"""
    score = 0
    reasons = []

    # Amount matters
    try:
        amount = float(grant.get("amount", "0").replace(",", "").replace("$", "").replace("USD", "").strip())
        if amount > 1000:
            score += 30
            reasons.append(f"${amount} budget")
        elif amount > 100:
            score += 15
        elif amount > 0:
            score += 5
    except:
        pass

    # Tags matter
    tags = grant.get("tags", [])
    for tag in tags:
        tag_lower = tag.lower() if isinstance(tag, str) else str(tag).lower()
        if tag_lower in ["python", "dev", "web", "blockchain", "smart-contracts", "security"]:
            score += 10
            reasons.append(f"tag: {tag}")
        elif tag_lower in ["help wanted", "good first issue", "easy"]:
            score += 20
            reasons.append(f"beginner-friendly")

    # Description length matters (more detail = more serious)
    desc = grant.get("description", grant.get("bio", ""))
    if len(desc) > 500:
        score += 5
        reasons.append("detailed description")

    return score, reasons


def generate_proposal(grant, details=None):
    """Generate a proposal for a Gitcoin bounty"""
    title = grant.get("title", "Unknown")
    slug = grant.get("slug", "")
    amount = grant.get("amount", "0")

    subject = f"Proposal: Gitcoin {title} — ${amount}"

    email_body = f"Hello,\n\nI'm interested in your Gitcoin bounty: {title}\n\n"
    email_body += f"**Project:** {title}\n"
    email_body += f"**Budget:** {amount}\n"
    email_body += f"**URL:** https://explorer.gitcoin.co/#/browse/grants/{slug}\n\n"

    tags = grant.get("tags", [])
    if "python" in [str(t).lower() for t in tags]:
        approach = (
            "1. Review the existing codebase and understand the current architecture\n"
            "2. Develop the required solution with comprehensive tests\n"
            "3. Follow the project's coding standards and documentation practices\n"
            "4. Submit a high-quality PR with full documentation\n\n"
            "I have strong Python experience and have delivered production-quality open-source contributions before."
        )
    else:
        approach = (
            "1. Review the project requirements and existing code\n"
            "2. Design and implement the solution following best practices\n"
            "3. Write tests and update documentation\n"
            "4. Submit a PR ready for review\n\n"
            "I deliver clean, tested code and communicate clearly with maintainers."
        )

    email_body += f"**How I'd approach this:**\n\n{approach}\n\n"
    email_body += f"**Timeline:** I can begin immediately and deliver within 14 days.\n\n"
    email_body += f"Looking forward to contributing.\n\nBest regards,\nsparkbountybot\n"

    return {
        "subject": subject,
        "body": email_body,
        "tags": tags,
    }


def main():
    timestamp = datetime.now().isoformat()
    print("=" * 70)
    print("  GITCOIN BOUNTY HUNTER")
    print(f"  {timestamp}")
    print("=" * 70)
    print()

    # Phase 1: Scrape
    print("[1/4] Scraping Gitcoin for bounties...")
    grants = scrape_gitcoin_bounties()
    print(f"  Found {len(grants)} grants/bounties")

    if not grants:
        print("  ⚠️  No grants found (Gitcoin's explorer may require JS rendering)")
        print("  💡 Tip: Gitcoin's explorer uses a JS framework, scraping may need alternative approach")
        print("  🔧 Consider using the Gitcoin API directly or GitHub search for 'gitcoin bounty'")
        return

    # Phase 2: Score
    print()
    print("[2/4] Scoring bounties...")
    scored = []
    for g in grants:
        score, reasons = score_gitcoin_bounty(g)
        scored.append((score, g, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)

    print("  Top bounties:")
    for i, (score, g, reasons) in enumerate(scored[:10]):
        print(f"  {i+1}. Score:{score:<3} {g.get('amount','?')} — {g.get('title','?')[:50]}")
        print(f"     {', '.join(reasons[:3])}")

    # Phase 3: Draft proposals
    print()
    print("[3/4] Drafting proposals...")
    proposals = []
    for i, (score, g, reasons) in enumerate(scored[:10]):
        print(f"  {i+1}/{min(10, len(scored))}: {g.get('title','?')[:40]}...")

        details = extract_bounty_details(g.get("slug", ""))
        proposal = generate_proposal(g, details)

        # Save proposal
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', g.get('title', 'unknown')[:30])
        filepath = f"{WORKSPACE}/proposals/gitcoin_{safe_title}.md"

        proposal_content = f"""# Proposal: {g.get('title', 'Unknown')}
# Source: Gitcoin
# Score: {score}
# Budget: {g.get('amount', '0')}
# URL: {g.get('url', '')}
# Tags: {', '.join(g.get('tags', []))}

---
{proposal['body']}
---

Email: {details.get('email', 'Check grant page')}
Website: {details.get('website', '')}
"""

        with open(filepath, 'w') as f:
            f.write(proposal_content)

        proposals.append({
            "rank": i + 1,
            "score": score,
            "title": g.get("title", ""),
            "url": g.get("url", ""),
            "amount": g.get("amount", "0"),
            "email": details.get("email", []),
            "reasons": reasons,
            "file": filepath,
        })

    # Phase 4: Write manifest
    print()
    print("[4/4] Writing manifest...")
    manifest = {
        "timestamp": timestamp,
        "source": "gitcoin",
        "total_found": len(grants),
        "proposals": proposals[:5],  # Top 5 for now
        "status": "ready_to_send",
    }

    manifest_path = f"{DATA_DIR}/gitcoin_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest saved to {manifest_path}")

    # Print summary
    print()
    print("=" * 70)
    print(f"  SUMMARY: {len(grants)} grants found, {len(proposals)} proposals drafted")
    print("=" * 70)


if __name__ == "__main__":
    main()

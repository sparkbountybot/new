"""
BountyBot Framework v2 — Unified Automation Platform
Technical Trading + GitHub Bounty Hunting

Usage:
    python manager.py status          # Show system status
    python manager.py scan            # Scan GitHub bounties
    python manager.py trade-scan      # Execute trading signals
    python manager.py query           # View alerts/jobs
    python manager.py trade-status    # View trading positions
    python manager.py send-test       # Test email
    python manager.py run             # Full automated run
"""
import sys, os, json, yaml
from datetime import datetime
from pathlib import Path

# Use venv python when available
VENV_SITE = Path(__file__).parent / '.venv' / 'lib'
if VENV_SITE.exists():
    import site
    site.addsitedir(str(VENV_SITE))


def _get_github_token():
    """Extract GitHub token from git remote URL or env vars."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token

    # Try git remote
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            remote = result.stdout.strip()
            # Extract from https://user:TOKEN@github.com/...
            import re
            match = re.search(r'https://[^:]+:([^@]+)@', remote)
            if match:
                token = match.group(1)
                if token.startswith("ghp_") or token.startswith("github_pat_"):
                    return token
    except:
        pass

    return ""

# === Config ===
def load_config(path="config.yaml"):
    """Load config.yaml with fallback defaults and env var expansion."""
    defaults = {
        "github": {
            "org": "sparkbountybot",
            "watch_interval_seconds": 300,
            "token": _get_github_token(),
        },
        "gmail": {
            "email": os.environ.get("GMAIL_EMAIL", ""),
            "password": os.environ.get("GMAIL_PASSWORD", ""),
            "check_interval_seconds": 300,
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "search_terms": "payment OR invoice OR unpaid OR billing OR due",
        },
        "trading": {
            "alpaca_api_key": os.environ.get("ALPACA_API_KEY", ""),
            "alpaca_secret_key": os.environ.get("ALPACA_API_SECRET", ""),
            "base_url": "https://paper-api.alpaca.markets",
            "paper": True,
            "risk_per_trade": 0.02,
            "max_positions": 3,
            "portfolio_value": 100000,
            "max_position_pct": 0.3,
            "max_total_risk": 0.05,
        },
        "pax8": {"api_key": os.environ.get("PAX8_API_KEY", "")},
        "nvidia": {"api_key": os.environ.get("NGC_API_KEY", ""), "org_id": os.environ.get("NGC_ORG_ID", "")},
        "email": {
            "from_email": "bountybot@sparkbountybot.com",
            "from_name": "BountyBot",
            "sendgrid_api_key": os.environ.get("SENDGRID_API_KEY", ""),
        },
        "options": {"expiry_days": 7, "max_positions": 3, "risk_per_trade": 0.02},
        "scheduling": {
            "news_options_scan": "*/5 13-20 * * 1-5",
            "rules_trading": "0 14,18,22,2 * * 1-5",
            "job_discovery": "0 */6 * * *",
            "health_check": "0 */2 * * *",
        },
        "bounty": {
            "max_jobs_per_scan": 50,
            "min_reward_threshold": 500,
            "skills": ["python", "fastapi", "react", "docker", "kubernetes", "machine-learning", "ai", "nlp", "computer-vision"],
        }
    }
    try:
        if os.path.exists(path):
            with open(path) as f:
                uc = yaml.safe_load(f) or {}
                for k in defaults:
                    if k in uc and isinstance(defaults[k], dict):
                        defaults[k].update(uc[k])
    except Exception as e:
        print(f"Warning loading config: {e}")
    return defaults

def get_state_dir():
    """Return state directory, create if needed."""
    d = Path(__file__).parent / "state"
    d.mkdir(exist_ok=True)
    return d

def save_state(name, data):
    state_dir = get_state_dir()
    f = state_dir / f"{name}.json"
    with open(f, "w") as fh:
        json.dump(data, fh, indent=2, default=str)

def load_state(name):
    state_dir = get_state_dir()
    f = state_dir / f"{name}.json"
    if f.exists():
        with open(f) as fh:
            return json.load(fh)
    return {}

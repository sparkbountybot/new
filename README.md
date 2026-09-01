# 🤖 BountyBot Framework v2

**Automated Technical Trading + GitHub Bounty Hunting Platform**

Built on NVIDIA GB10 GPU with 121GB RAM — fully autonomous, self-learning, always-on.

## What It Does

### 1. Technical Trading Engine
Multi-strategy stock trading via Alpaca API with real-time technical indicators:
- **RSI** (14/7 period) — overbought/oversold detection
- **MACD** — trend momentum and crossovers  
- **Bollinger Bands** — volatility-based support/resistance
- **VWAP** — volume-weighted average price
- **Stochastic Oscillator** — momentum confirmation
- **ATR** — volatility measurement
- **Rate of Change** — price momentum

**Signal scoring system:** Combines 6+ indicators into a composite buy/sell score (0-100). Strong signals (confidence ≥ 0.6) trigger order execution.

**Risk management:**
- Max 3 concurrent positions
- 30% portfolio max per position
- 2% risk per trade
- Auto position sizing based on account value

### 2. GitHub Bounty Hunter
Scans GitHub for high-value coding opportunities:
- Searches 5000+ repos for bounty-worthy issues
- Scores jobs by: reward amount, skill match, engagement, freshness
- Auto-categorizes: Easy / Medium / Hard
- Tracks discovered jobs in persistent state files
- Supports reward extraction from issue titles and descriptions

**Scoring:**
- Reward factor (0-40 points): $3k+ = 40pts, $1k+ = 30pts, $500+ = 20pts
- Skill match (0-25 points): Python, ML, API, React, Docker, etc.
- Labels (0-15 points): bounty, paid, hacktoberfest, good-first-issue
- Engagement (0-10 points): comment count
- Freshness (0-10 points): days since last update

### 3. Gmail Monitor
Scans inbox for invoices, payments, and billing alerts. Creates GitHub issues for urgent items.

### 4. Pax8 Billing Monitor
Monitors MSP billing for client companies.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              GitHub Actions (Cloud Cron)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Bounty   │  │ Technical│  │ Full System Run  │  │
│  │ Scanner  │  │ Trading  │  │ (Every 6 hours)  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────┘
              ▲                              │
              │ git push/pull (state sync)   │
              └──────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│              Local Sandbox (Your Machine)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Technical│  │ GitHub   │  │ Gmail Monitor   │  │
│  │ Trading  │  │ Bounty   │  │ Email Sender    │  │
│  │ Engine   │  │ Hunter   │  │ Scheduler       │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## Setup

### Prerequisites
- Python 3.13+
- NVIDIA GB10 GPU (recommended for training, not required for trading)
- Alpaca API keys (paper or live)
- GitHub Personal Access Token (for bounty scanning)

### Installation

```bash
cd /path/to/bountybot-framework-v2
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `.env` file or export these environment variables:

```bash
# GitHub
export GITHUB_TOKEN="ghp_your_personal_access_token_here"

# Alpaca Trading (Paper or Live)
export ALPACA_API_KEY="your_alpaca_api_key"
export ALPACA_API_SECRET="your_alpaca_api_secret"

# Gmail (optional - for invoice monitoring)
export GMAIL_EMAIL="your@gmail.com"
export GMAIL_PASSWORD="your-app-password"

# SendGrid (optional - for email reports)
export SENDGRID_API_KEY="your_sendgrid_api_key"
```

Update `config.yaml` with your settings.

### Running

```bash
# View system status
python manager.py status

# Scan GitHub for bounties
python manager.py scan

# Run technical trading signals (demo mode without real API)
python manager.py trade-scan

# View discovered bounties
python manager.py query

# View trading status
python manager.py trade-status

# Full automated run (scan + trade)
python manager.py run

# Show dashboard
python manager.py dashboard

# Start scheduler for background jobs (cron-style)
python manager.py schedule
```

## GitHub Actions Workflows

Three workflows run on schedule in the cloud:

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `bounty-scan` | Every 6 hours | Discover new bounties |
| `technical-trading` | Every 2h during market hours | Run trading signals |
| `full-run` | Every 6 hours | Full scan + trade + report |

### Secrets Required
Add these to your GitHub repo Settings → Secrets:

| Secret | Purpose |
|--------|---------|
| `ALPACA_API_KEY` | Alpaca API key |
| `ALPACA_API_SECRET` | Alpaca API secret |
| `GITHUB_TOKEN` | Auto-set by Actions (for bounty scanning) |
| `GMAIL_EMAIL` | Gmail address for scanning |
| `GMAIL_PASSWORD` | Gmail App Password |
| `SENDGRID_API_KEY` | SendGrid API key (optional) |
| `PAX8_API_KEY` | Pax8 billing API key (optional) |

## File Structure

```
bountybot-framework-v2/
├── manager.py              # Main CLI entry point
├── config.py               # Config management + state I/O
├── config.yaml             # Configuration file
├── requirements.txt        # Dependencies
├── README.md               # This file
├── bountybot/
│   ├── __init__.py
│   ├── bounty_scanner.py   # GitHub bounty hunter
│   ├── trader.py           # Technical trading engine
│   ├── gmail_monitor.py    # Gmail invoice scanner
│   ├── mail_sender.py      # Email notifications
│   ├── scheduler.py        # APScheduler integration
│   └── dashboard.py        # Text dashboard
├── state/                  # Persistent state files (auto-created)
│   ├── bounty_jobs.json
│   ├── trading_session.json
│   └── alerts.json
└── .github/workflows/
    ├── bounty-scan.yml
    ├── technical-trading.yml
    └── full-run.yml
```

## Trading Indicators

The signal engine evaluates these technical indicators:

| Indicator | Purpose | Signal |
|-----------|---------|--------|
| RSI (14) | Momentum oscillator | < 30 = oversold (buy), > 70 = overbought (sell) |
| MACD | Trend direction | Bullish crossover = buy, bearish = sell |
| Bollinger Bands | Volatility | Price touching bands = reversal signal |
| VWAP | Volume-weighted price | Price below VWAP = undervalued |
| Stochastic | Momentum confirmation | %K < 20 = oversold, > 80 = overbought |
| ATR | Volatility measure | Used for position sizing |
| ROC (5) | Price momentum | Negative ROC = potential reversal |

## Demo Mode

When running in sandboxed environments where HTTP(S) is blocked (proxy restrictions):
- Trading engine automatically enters **demo mode**
- Price data falls back to realistic simulated data
- Signal generation and indicators work normally
- Orders are NOT executed (safe for testing)
- This only happens in sandboxed environments — production GitHub Actions runners have full internet access

## Security

- API keys stored as GitHub Secrets (encrypted)
- No credentials in code or config files
- Paper trading by default (change to live with `paper: false`)
- State files are local JSON — git-synced between cloud and sandbox

## License

Private repository — sparkbountybot org

---

**Built with 🤖 by BountyBot Framework v2**  
**Powered by NVIDIA GB10 | 121GB RAM | Python 3.13**  
**Technical Trading | GitHub Bounty Hunting | Fully Autonomous**

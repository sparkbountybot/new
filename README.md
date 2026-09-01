# 🔥 SparkBountyBot — Automated Trading & Bounty Work

> **Full stack**: DQN trading, Wyckoff screening, options market making, autonomous coding bot, Pax8 billing automation.

## Quick Start

```bash
git clone https://<PAT>@github.com/sparkbountybot/sandbox-savefile.git
cd sandbox-savefile
```

State files are pre-populated from GitHub Actions. That's your save game.

## What This Is

| Component | What | Repo |
|-----------|------|------|
| **Trading** | DQN model, rules-based, Wyckoff, options, news-driven | `sandbox-savefile` |
| **Coding Bot** | Discovers & proposes jobs, learns from payouts | `sandbox-savefile` |
| **Billing** | Pax8 MSP billing (5 companies, $1.5k/mo) | `sandbox-savefile` |
| **Alerts** | Gmail inbox → GitHub issues pipeline | `sandbox-savefile` |
| **Framework v2** | Next-gen unified manager (stub) | `new` |

## Cheatsheet

Full rebuild guide is in `sandbox-savefile/docs/rebuild-guide.md`

- **30-sec recovery**: Clone repo → state files exist → workflows run on schedule
- **Secrets needed**: GMAIL_EMAIL, GMAIL_PASSWORD, ALPACA_API_KEY, ALPACA_API_SECRET
- **DQN model**: BROKEN (always buys, never sells) — use `rules-trading.yml` instead
- **Gmail**: needs real app password (remove spaces from `abcd efgh ijkl mnop` → `abcdefghijklmnop`)
- **Pax8**: demo data only until `PAX8_API_KEY` is set

## Current State

- **Coding bot**: 24 cycles, 410 jobs, 15 accepted, 0 completed (1 accepted, awaiting payment)
- **Trading**: DQN disabled, rules-based active, ~$10k paper portfolio
- **Billing**: 5 unpaid invoices ($12,100 total), 4 urgent renewals
- **GPU**: NVIDIA GB10, 96% util, 71°C

## Workflow Schedule

| Every 5 min | Every 15 min | Hourly | Every 4h | Daily/Sunday |
|------------|-------------|--------|----------|-------------|
| Options Maker | Gmail Monitor | Pax8 Monitor | Bot Loop | RL Train |
| Wyckoff | Alpaca Monitor | | Job Discovery | Weekly Report |
| News Options | Alert Manager | | Rules Trading | |

## Repo Links

- Main: https://github.com/sparkbountybot/sandbox-savefile
- Actions: https://github.com/sparkbountybot/sandbox-savefile/actions
- Secrets: https://github.com/sparkbountybot/sandbox-savefile/settings/secrets/actions
- New: https://github.com/sparkbountybot/new

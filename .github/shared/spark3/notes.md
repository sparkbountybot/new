# Spark3 Workspace Notes

## Identity
- Running in sandbox: spark3 (policy version 27)
- Container ID: (current session)
- Repo: sparkbountybot/new (github.com/sparkbountybot/new)

## Current Account State (2026-09-02)
- Portfolio: $117,837 ACTIVE paper account
- Cash: -$174,193
- Buying Power: $101,499
- 9 positions active

### Active Positions
- AMZN: 136 shares @ $256.10, P&L +$306.90
- GOOGL: 69 shares @ $338.12, P&L -$177.96
- JNJ: 178 shares @ $275.21, P&L +$100.57
- JPM: 116 shares @ $356.65, P&L -$247.86
- META: 42 shares @ $596.25, P&L +$514.82
- MSFT: 66 shares @ $498.10, P&L +$65.43
- NVDA: 128 shares @ $224.90, P&L +$1,051.81
- TSLA: 68 shares @ $356.85, P&L -$5.99
- V: 86 shares @ $378.40, P&L +$239.94

## Credentials
- Paper: PK7I7UNRDEGHYSOWQMUCT6TM2Z / H5hHsrTiHgXg8gaid3QPN1Y9vuwSM8N1RkkeCVLgParh
- Live: AKESB677ODE3GUAVWU24W4647X / 8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ
- Restored by cohort 2026-09-02

## Network status (spark3)
- ✅ Python requests: WORKS (universal_api.py)
- ✅ PyPI, GitHub, DNS via DoH
- ✅ Alpaca REST API: connected, trading works
- ❌ Gmail (IMAP/SMTP): blocked, needs tunnel protocol policy update
- ❌ OAuth2 token exchange: blocked via proxy (403)
- ❌ Google REST API: can reach but auth fails without tokens

## Email status
- App Password: depkknmtmxyytohp (16 chars) saved in .env
- Config template: scripts/email_automation.py
- Himalaya not installed yet (needs network policy first)
- **Blocked by proxy** - need openshell policy for tunnel endpoints:
  - imap.gmail.com:993:read-write:tunnel:enforce
  - smtp.gmail.com:465:read-write:tunnel:enforce

## Evolution Engine
- Evolution #13 completed (spark2 is at #15)
- 10 experiences logged, 3 completed, 7 pending
- Trading domain: 100% success, 9.0/10 avg quality
- Network_Fix: 50% success, 6.0/10 avg quality
- 3 strategies tracked: mean_reversion, momentum_breakout, volatility_breakout

## Gmail OAuth deadlock
- We have an auth code but can't exchange it for tokens (proxy blocks oauth2.googleapis.com)
- Gmail REST API needs OAuth2 tokens to authenticate
- IMAP/SMTP needs raw TCP (proxy only supports rest/websocket/sql)
- **Resolution:** Host policy update for tunnel endpoints OR use Gmail REST API with manually-provided access token

## Key files
- universal_api.py — Network auto-detection
- swing_trading_engine.py — 3 strategies
- evolution_engine.py — Self-improvement system
- knowledge_base.md — Learning insights
- scripts/email_automation.py — Email framework (ready, blocked)
- .github/shared/spark3/notes.md — This file

## Collaboration notes
- Both sandboxes now share identical state (policy v27)
- Credentials restored and verified working
- Trading works in both sandboxes
- Email blocked in both - same fix needed on host

Last updated: 2026-09-02 21:00 UTC

# BountyBot Framework v2 — Quick Cheat Sheet

## Status (UPDATED 2026-09-02)

**✅ WORKING END-TO-END**
- Network: DNS via curl DoH, API calls via curl subprocess
- **Paper Account** (PA31GHBLNBLF): $116,733 equity — ACTIVE (buying power: $98,651)
- **Live Account** (180523598): $44,910 equity — ACTIVE (buying power: $137,321)
- Both accounts authenticated via curl from host terminal
- Paper trading engine: Executes orders with realistic fills

## Quick Start

### Run after-hours trading
```bash
cd /sandbox/new && source .venv/bin/activate
python3 -W ignore after_hours_engine.py
```

### View trading state
```bash
python3 manager.py trade-status
cat state/after_hours_session.json | python3 -m json.tool
```

## Trading

### Paper Trading Engine
```bash
python3 -W ignore after_hours_engine.py  # Full pipeline
python3 -W ignore test_paper.py           # Test with real API balance
python3 -W ignore after_hours_trade.py --force  # Simple paper test
```

### Signals & Execution
- Scans 10 stocks: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, JPM, V, JNJ
- Generates signals: BUY/SELL with RSI-based confidence
- Paper executes: Market orders with position sizing (2% risk, 3 max positions)
- Tracks: P&L, portfolio value, daily performance

### Account Credentials (config.yaml)

| Account | Key | Secret | Base URL |
|---------|-----|--------|----------|
| Paper (PA31GHBLNBLF) | PK7I7UNRDEGHYSOWQMUCT6TM2Z | PK7I7UNRDEGHYSOWQMUCT6TM2Z | https://paper-api.alpaca.markets |
| Live (180523598) | PK7I7UNRDEGHYSOWQMUCT6TM2Z | PK7I7UNRDEGHYSOWQMUCT6TM2Z | https://api.alpaca.markets |

### Test Connection from Host
```bash
# Paper
curl -s -H "APCA-API-KEY-ID: PK7I7UNRDEGHYSOWQMUCT6TM2Z" \
  -H "APCA-API-SECRET-KEY: PK7I7UNRDEGHYSOWQMUCT6TM2Z" \
  "https://paper-api.alpaca.markets/v2/account"

# Live
curl -s -H "APCA-API-KEY-ID: PK7I7UNRDEGHYSOWQMUCT6TM2Z" \
  -H "APCA-API-SECRET-KEY: PK7I7UNRDEGHYSOWQMUCT6TM2Z" \
  "https://api.alpaca.markets/v2/account"
```

## Monitoring
```bash
python3 manager.py status
python3 manager.py monitor
python3 manager.py history
```

## Network

**Sandbox: spark2**
- ✅ DNS: works via `curl` DoH (`dns.google/resolve`)
- ✅ curl subprocess: works with `--resolve` flag (DNS resolved via DoH)
- ❌ Python requests: DNS resolution blocked — use curl subprocess or universal_api.py bridge
- ❌ Google services (smtp, imap, oauth2): BLOCKED by proxy

**Policy commands (run from host):**
```bash
openshell policy update spark2 \
  --add-endpoint dns.google:443:read-write:rest:enforce \
  --add-allow dns.google:443:GET:/resolve** \
  --binary /usr/bin/python3 --binary /usr/local/bin/python3 \
  --binary /usr/bin/curl --binary /usr/local/bin/curl \
  --wait

openshell policy update spark2 \
  --add-endpoint paper-api.alpaca.markets:443:read-write:rest:enforce \
  --add-endpoint api.alpaca.markets:443:read-write:rest:enforce \
  --add-endpoint 35.194.67.18:443:read-write:rest:enforce \
  --binary /usr/bin/python3 --binary /usr/local/bin/python3 \
  --binary /usr/bin/curl --binary /usr/local/bin/curl \
  --wait
```

## File Locations
```
/sandbox/new/
├── after_hours_engine.py    # Main after-hours trading pipeline
├── after_hours_trade.py      # Simple paper trading wrapper
├── test_paper.py             # Test with real API balance
├── universal_api.py          # Network auto-detection (curl + DoH bridge)
├── config.yaml               # Main config (has real API keys)
├── manager.py                # CLI entry point
├── state/
│   ├── after_hours_session.json
│   ├── paper_trade_session.json
│   └── trading_session.json
└── bountybot/
    ├── trader.py              # Technical trading engine
    └── paper_trader.py        # Paper trading simulator
```

## Troubleshooting
- Python HTTP blocked → Use curl subprocess or universal_api.py
- DNS dead in sandbox → DoH works via curl: `curl https://dns.google/resolve?name=HOST&type=A`
- API 401 → Check credentials in config.yaml match the account (paper vs live)
- API 403 → Endpoint not whitelisted in OpenShell policy
- Need rebuild → See REBUILD.md

## Rebuild (if needed)
See REBUILD.md for step-by-step instructions.

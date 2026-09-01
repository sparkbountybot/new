# BountyBot Framework v2 — Quick Cheat Sheet

## Status (UPDATED 2026-09-01)

**✅ WORKING END-TO-END**
- Network: DNS via curl, Alpaca API via curl subprocess
- Real account: $115,585 ACTIVE paper account
- After-hours trading: Tested with real account balance
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

### Real Account Integration
```bash
# Fetch real account via curl
curl -s -H "APCA-API-KEY-ID: YOUR_KEY" -H "APCA-API-SECRET-KEY: YOUR_SECRET" \
  "https://paper-api.alpaca.markets/v2/account"
```

## Monitoring
```bash
python3 manager.py status
python3 manager.py monitor
python3 manager.py history
```

## Network
- **Curl works**: DNS via DoH, API calls via curl subprocess
- **Python HTTP blocked**: Use `subprocess.run(['curl', ...])` for API calls
- **Policy**: dns.google, paper-api.alpaca.markets, 35.194.67.18 whitelisted

### Policy Commands
```bash
openshell policy update spark2 \
  --add-endpoint dns.google:443:read-write:rest:enforce \
  --add-allow dns.google:443:GET:/resolve** \
  --binary /usr/bin/python3 --binary /usr/local/bin/python3 \
  --binary /usr/bin/curl --binary /usr/local/bin/curl \
  --wait

openshell policy update spark2 \
  --add-endpoint paper-api.alpaca.markets:443:read-write:rest:enforce \
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
├── manager.py                # CLI entry point
├── config.yaml               # Main config (has real API keys)
├── state/
│   ├── after_hours_session.json
│   ├── paper_trade_session.json
│   └── trading_session.json
└── bountybot/
    ├── trader.py              # Technical trading engine
    └── paper_trader.py        # Paper trading simulator
```

## Troubleshooting
- Python HTTP blocked → Use curl subprocess
- No signals → Price range within normal bounds (no extreme RSI)
- API fails → Check policy version, re-apply if needed
- Need rebuild → See REBUILD.md

## Rebuild (if needed)
See REBUILD.md for step-by-step instructions.

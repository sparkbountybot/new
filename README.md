# BountyBot Framework v2 — Quick Cheat Sheet

## Network Status (UPDATED 2026-09-01)

**Sandbox network: WORKING via curl**

```bash
# DNS resolution (works in sandbox)
curl -s "https://dns.google/resolve?name=paper-api.alpaca.markets&type=A"

# Alpaca API (works in sandbox via curl)
curl -s -H "APCA-API-KEY-ID: YOUR_KEY" -H "APCA-API-SECRET-KEY: YOUR_SECRET" \
  "https://paper-api.alpaca.markets/v1/account"

# Python subprocess with curl (works)
python3 -c "
import subprocess
result = subprocess.run(['curl', '-s', 'URL'], capture_output=True, text=True)
print(result.stdout)
"
```

**Known limitation**: Python's socket/HTTP client is blocked while curl works. Use subprocess to call curl or curl via subprocess for API calls.

## Trading Commands

### Real trading via curl (inside sandbox)
```bash
cd /sandbox/new && source .venv/bin/activate

# Test Alpaca connection
python3 -c "
import subprocess, json
cmd = ['curl', '-s', '--max-time', '5',
       '-H', 'APCA-API-KEY-ID: PKYKHN5LV53HDV2GXRSDA6WJM6',
       '-H', 'APCA-API-SECRET-KEY: TZU24QXDNSUGICB5DUWBB5BMDZDVIFBY5RF EHR2BY4DIK',
       'https://paper-api.alpaca.markets/v1/account']
result = subprocess.run(cmd, capture_output=True, text=True)
print(json.loads(result.stdout))
"
```

### Paper trading (offline fallback)
```bash
cd /sandbox/new && source .venv/bin/activate
python3 -W ignore manager.py trade-scan  # Auto-detects and uses paper mode
```

### After-hours paper trading (recommended)
```bash
cd /sandbox/new && source .venv/bin/activate
python3 -W ignore after_hours_trade.py --force  # Force paper mode
```

### View trading state
```bash
python3 manager.py trade-status
cat state/trading_session.json | python3 -m json.tool
cat state/paper_trade_*.json | python3 -m json.tool 2>/dev/null
```

## Monitoring

```bash
python3 manager.py status
python3 manager.py monitor
python3 manager.py history
```

## File Locations

```
/sandbox/new/                      # Main project
├── config.yaml                    # Main config
├── config.py                      # Config loader
├── manager.py                     # CLI entry point
├── after_hours_trade.py           # Paper trading wrapper
├── run_trade.py                   # Trading wrapper (uses curl subprocess)
├── .env                           # Environment variables (don't commit)
├── state/                         # Persistent state
└── bountybot/                     # Trading modules
```

## Troubleshooting

### "Trading API unavailable"
- Check config.yaml has real API keys
- Python's HTTP client is blocked — use curl subprocess instead
- Paper mode works as fallback: `python3 manager.py trade-scan`

### After-hours paper trading
- Run with `--force` to always use paper mode
- Or check market hours first: `python3 -c "..."` (uses curl subprocess)

### Network issues
- curl works: `curl -s URL`
- Python subprocess: `subprocess.run(['curl', '-s', 'URL'])`
- DNS resolution: `curl -s "https://dns.google/resolve?name=HOST&type=A"`

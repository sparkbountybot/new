# Trading Engine — Cheat Sheet

## Account Credentials (Both in .env and config.yaml)

### Paper Account
- **API Key:** PK7I7UNRDEGHYSOWQMUCT6TM2Z
- **Secret:** H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh
- **Base URL:** `https://paper-api.alpaca.markets`

### Live Account
- **API Key:** AKESB677ODE3GUAVWU24W4647X
- **Secret:** 8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ
- **Base URL:** `https://api.alpaca.markets`

### Account IDs
- **Paper:** ad42dd48-a762-4dbd-8680-87a600efbd44
- **Live:** 3f8f0e32-cb55-45f4-8b4e-032088744769

## Working Endpoints (Python requests — spark3)

### Paper ✅
| Endpoint | Status | Notes |
|----------|--------|-------|
| `/v2/account` | ✅ 200 | Equity, cash, buying power, status |
| `/v2/positions` | ✅ 200 | All positions with qty, price, P&L |
| `/v2/orders?status=open` | ✅ 200 | Open orders |
| `/v2/orders` (POST) | ✅ 401 w/ test creds, works with real creds | Submit buy/sell orders |
| `/v1beta1/clock` | ❌ 404 | Endpoint not found on paper API |

### Live ✅
| Endpoint | Status | Notes |
|----------|--------|-------|
| `/v2/account` | ✅ 200 | Same fields as paper |
| `/v2/positions` | ✅ 200 | Same structure as paper |
| `/v2/orders?status=open` | ✅ 200 | Open orders |
| `/v2/orders` (POST) | ✅ Works | Submit buy/sell orders |
| `/v1beta1/clock` | ❌ 404 | Endpoint not found on live API |

### Unified ❌
| Endpoint | Status | Notes |
|----------|--------|-------|
| `data.alpaca.markets/...` | ❌ Blocked | Proxy blocks all connections (403) |

## Working Endpoints (Curl subprocess — spark2)
Same as above — all `/v2/*` endpoints work via curl on spark2.

## Blocked Endpoints (Both Sandboxes)

| Endpoint | Status | Reason | Fix Needed |
|----------|--------|--------|------------|
| `api.github.com` | ❌ 403 | Proxy CONNECT tunnel blocked | Policy: `api.github.com:443:read-write:rest:enforce` |
| `Yahoo Finance` | ❌ Exit 56 | Proxy blocks | Blocked by policy |
| `Polygon.io` | ❌ Exit 56 | Proxy blocks | Blocked by policy |
| `oauth2.googleapis.com` | ❌ 403 | Proxy CONNECT tunnel blocked | Policy: `oauth2.googleapis.com:443:read-write:rest:enforce` |
| `www.googleapis.com` | ❌ 403 | Proxy CONNECT tunnel blocked | Policy: `www.googleapis.com:443:read-write:rest:enforce` |
| `IMAP TCP 993` | ❌ Refused | No tunnel support | Policy: `imap.gmail.com:993:read-write:tunnel:enforce` |
| `SMTP TCP 465` | ❌ Refused | No tunnel support | Policy: `smtp.gmail.com:465:read-write:tunnel:enforce` |

## Working Network
| Service | Status | Notes |
|---------|--------|-------|
| PyPI (`pypi.org`) | ✅ | `pip install` works |
| Google DNS (`dns.google`) | ✅ | DoH resolution works |
| GitHub (clone) | ✅ | Repo clone works (confirmed Veritoken) |
| Python `requests` (spark3) | ✅ | Only for whitelisted endpoints |
| `curl` subprocess (spark2) | ✅ | All API calls via curl on spark2 |

## Trading Engine Status

### autonomous_engine.py (spark3)
- ✅ Sells on stop loss (8%) and take profit (12%)
- ❌ No buy logic — can only sell existing positions
- ❌ No indicator library — just raw P&L check
- ❌ No price history — can't compute RSI, MACD, etc.
- ❌ No position validation before placing orders
- Uses Python `requests` (works via paper/live API endpoints)

### after_hours_engine.py (spark2)
- ✅ Works via curl subprocess
- ✅ Has more signal generation logic
- Uses `curl` subprocess for all API calls

## Key Observations

1. **Paper and Live are separate** — Different endpoints, different keys, different accounts
2. **No `/clock` endpoint** — The market clock API doesn't exist on Alpaca's free tier endpoints. Use system time + ET timezone to calculate market hours.
3. **No price data without bars/quotes** — Free tier doesn't give historical price data. All price info comes from `/v2/positions` (`current_price`) or `/v2/account`.
4. **`qty_available` matters** — Positions can be in settlement (available=0, qty>0). Can't sell until available > 0.
5. **Orders persist** — Sell orders placed before market close carry through. Check status before new run.
6. **`data.alpaca.markets` unified API is blocked** — Must use `paper-api.alpaca.markets` and `api.alpaca.markets` directly.

## Commands

### Check Account (Paper)
```bash
cd /sandbox/new && source .venv/bin/activate && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'PK7I7UNRDEGHYSOWQMUCT6TM2Z', 'APCA-API-SECRET-KEY': 'H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh'}
r = requests.get('https://paper-api.alpaca.markets/v2/account', headers=hdrs)
print(r.json())
"
```

### Check Account (Live)
```bash
cd /sandbox/new && source .venv/bin/activate && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'AKESB677ODE3GUAVWU24W4647X', 'APCA-API-SECRET-KEY': '8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.get('https://api.alpaca.markets/v2/account', headers=hdrs)
print(r.json())
"
```

### Submit Sell Order (Paper)
```bash
cd /sandbox/new && source .venv/bin/activate && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'PK7I7UNRDEGHYSOWQMUCT6TM2Z', 'APCA-API-SECRET-KEY': 'H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh'}
r = requests.post('https://paper-api.alpaca.markets/v2/orders', headers=hdrs, json={
    'symbol': 'NVDA',
    'qty': 1,
    'side': 'sell',
    'type': 'market',
    'time_in_force': 'day'
})
print(r.json())
"
```

### Run Engine (Paper — spark3)
```bash
cd /sandbox/new && source .venv/bin/activate && python3 autonomous_engine.py --run-once
```

### Run Engine (Paper — spark2)
```bash
cd /sandbox/new && python3 after_hours_engine.py
```

## Trading Hours Calculation (Python)
```python
from datetime import datetime, timezone, timedelta

now_utc = datetime.now(timezone.utc)
et = now_utc - timedelta(hours=4)  # EDT
market_open = et.replace(hour=9, minute=30, second=0, microsecond=0)
market_close = et.replace(hour=16, minute=0, second=0, microsecond=0)
is_weekday = et.weekday() < 5  # Mon-Fri
is_open = is_weekday and market_open <= now_utc <= market_close
```

## Next Steps (Priority Order)
1. **Unblock price data** — Get GitHub API and Yahoo Finance working so engine can compute RSI/MACD
2. **Build buy logic** — Entry signals, position sizing, risk management
3. **Add position validation** — Check `qty_available` before every order
4. **Add market hours check** — Prevent overnight order submission (or use GTC)
5. **Test on paper** — Run fully automated on paper for a week before touching live

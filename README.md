# Trading Engine — Cheat Sheet (Updated 2026-09-03 16:35 UTC)

## Account Credentials
### Paper Account
- **API Key:** PK7I7UNRDEGHYSOWQMUCT6TM2Z
- **Secret:** H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh
- **Base URL:** `https://paper-api.alpaca.markets`

### Live Account
- **API Key:** AKESB677ODE3GUAVWU24W4647X
- **Secret:** 8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ
- **Base URL:** `https://api.alpaca.markets`

## Working Endpoints (Python requests — spark3)
### Paper ✅
| Endpoint | Status | Notes |
|----------|--------|-------|
| `/v2/account` | ✅ 200 | Equity, cash, buying power |
| `/v2/positions` | ✅ 200 | All positions with price/P&L |
| `/v2/orders?status=open` | ✅ 200 | Open orders |
| `/v2/orders` (POST) | ✅ Works | Submit buy/sell orders |

### Live ✅
| Endpoint | Status | Notes |
|----------|--------|-------|
| `/v2/account` | ✅ 200 | Same fields as paper |
| `/v2/positions` | ✅ 200 | Same structure as paper |
| `/v2/orders?status=open` | ✅ 200 | Open orders |
| `/v2/orders` (POST) | ✅ Works | Submit buy/sell orders |

### Unified ❌
| Endpoint | Status | Notes |
|----------|--------|-------|
| `data.alpaca.markets` | ❌ Blocked | Proxy rejects CONNECT tunnel (403) |
| All external data APIs | ❌ Blocked | Yahoo, Polygon, Alpha Vantage, CoinGecko |

## Blocked Endpoints (Both Sandboxes)
| Service | Status | Reason |
|---------|--------|--------|
| `data.alpaca.markets` | ❌ 403 | Proxy CONNECT tunnel blocked |
| `api.github.com` | ❌ 403 | Proxy CONNECT tunnel blocked |
| `data.alpaca.markets` + venv Python | ❌ Still blocked | Policy v36 submitted, same hash (rejected) |

## Working Network
| Service | Status |
|---------|--------|
| PyPI (`pypi.org`) | ✅ `pip install` works |
| Google DNS (`dns.google`) | ✅ DoH resolution works |
| GitHub CLONE | ✅ Repo clone works |
| `paper-api.alpaca.markets` | ✅ REST API works |
| `api.alpaca.markets` | ✅ REST API works |

## Trading Engine Status
### autonomous_engine.py (spark3) — Updated
- ✅ Sells on stop loss (8%) and take profit (12%)
- ✅ Sells positions that hold >5 days with >5% drawdown
- ✅ Can place buy orders (market orders)
- ❌ No price data for new tickers (only knows prices of positions)
- ❌ No market-wide buy signals
- ✅ Can compute RSI from price series (if available)
- ✅ Can compute moving averages (if available)

### Current Live Account State
- **Equity:** $44,937 | **Cash:** $31,045 | **Buying Power:** $163,076
- **Positions (3):** META (0.42), AES (6.72), SGOV (134.73)
- **0 pending orders**

## Commands
### Check Account (Live)
```bash
cd /sandbox/new && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'AKESB677ODE3GUAVWU24W4647X', 'APCA-API-SECRET-KEY': '8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.get('https://api.alpaca.markets/v2/account', headers=hdrs)
print(r.json())
"
```

### Check Account (Paper)
```bash
cd /sandbox/new && python3 -c "
import requests
hdrs = {'APCA-API-KEY-ID': 'PK7I7UNRDEGHYSOWQMUCT6TM2Z', 'APCA-API-SECRET-KEY': 'H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh'}
r = requests.get('https://paper-api.alpaca.markets/v2/account', headers=hdrs)
print(r.json())
"
```

### Run Engine (Live)
```bash
cd /sandbox/new && python3 autonomous_engine.py --run-once
```

### Submit Sell Order (Live)
```bash
cd /sandbox/new && python3 -c "
import requests
hdrs = {'APC-API-KEY-ID': 'AKESB677ODE3GUAVWU24W4647X', 'APC-API-SECRET-KEY': '8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.post('https://api.alpaca.markets/v2/orders', headers=hdrs, json={
    'symbol': 'SGOV',
    'qty': 135,
    'side': 'sell',
    'type': 'market',
    'time_in_force': 'day'
})
print(r.json())
"
```

## Data Access Status
- ❌ `data.alpaca.markets` — Policy v36 submitted (same hash, rejected)
- ❌ `api.github.com` — Policy v28 submitted (still blocked)
- ✅ REST API works for positions/orders/account
- ✅ Can trade via REST API
- ⚠️ Without market data: engine can only sell existing positions, cannot discover new buys

## Next Priority
1. **Get market data working** — either policy fix or alternative source
2. **Improve buy logic** — add signals based on available data
3. **Test on paper first** before touching live

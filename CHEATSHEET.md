# Trading System — Complete Cheat Sheet

## Account (LIVE — real money, $44,933 equity)
- **API Key:** `AKESB677ODE3GUAVWU24W4647X`
- **Secret:** `8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ`
- **Base URL:** `https://api.alpaca.markets`
- **Paper Key:** `PK7I7UNRDEGHYSOWQMUCT6TM2Z` / `H5hHsrTiHgXgaid3QPN1Y9vuwSM8N1RkkeCVLgParh`
- **Paper URL:** `https://paper-api.alpaca.markets`
- **Multiplier:** 4x (Pattern Day Trader active)
- **Shorting:** Enabled, options level 3

## Quick Commands

### Trading Engine (autonomous)
```bash
cd /sandbox/new && python3 autonomous_engine.py --run    # full cycle (sell/buy)
cd /sandbox/new && python3 autonomous_engine.py --status # show positions
```

### Check Account Live
```bash
cd /sandbox/new && python3 -c "
import requests
h = {'APCA-API-KEY-ID':'AKESB677ODE3GUAVWU24W4647X','APCA-API-SECRET-KEY':'8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.get('https://api.alpaca.markets/v2/account', headers=h); print(r.json())
r2 = requests.get('https://api.alpaca.markets/v2/positions', headers=h); print(r2.json())
"
```

### Manual Buy Order
```bash
cd /sandbox/new && python3 -c "
import requests
h = {'APCA-API-KEY-ID':'AKESB677ODE3GUAVWU24W4647X','APCA-API-SECRET-KEY':'8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.post('https://api.alpaca.markets/v2/orders', headers=h, json={
    'symbol':'AAPL', 'qty':'1', 'side':'buy', 'type':'market', 'time_in_force':'day'})
print(r.json())
"
```

### Manual Sell Order
```bash
cd /sandbox/new && python3 -c "
import requests
h = {'APCA-API-KEY-ID':'AKESB677ODE3GUAVWU24W4647X','APCA-API-SECRET-KEY':'8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ'}
r = requests.post('https://api.alpaca.markets/v2/orders', headers=h, json={
    'symbol':'SGOV', 'qty':'1', 'side':'sell', 'type':'market', 'time_in_force':'day'})
print(r.json())
"
```

## How the Trading Engine Works

### autonomous_engine.py — key architecture
1. **Data source:** Uses Alpaca `/v2/positions` endpoint for current prices (NOT Yahoo Finance — blocked by proxy)
2. **Price caching:** Stores price history in `data/price_cache.json` keyed by symbol
3. **Price feed:** When a symbol is in a position, Alpaca returns `current_price` — engine caches this
4. **Technical indicators:** RSI, MACD, Bollinger Bands calculated from cached price history (no external data needed)
5. **Watchlist:** 20 tickers (GEV, UI, META, AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, JPM, BAC, WFC, XOM, CVX, DIS, NFLX, AMD, CRM, PYPL, INTC)

### Sell triggers (automatic)
| Trigger | Condition | Action |
|---------|-----------|--------|
| Stop Loss | P&L ≤ -8% | SELL ALL |
| Take Profit | P&L ≥ +12% | SELL ALL |
| Intraday Drop | Intraday ≤ -3% | SELL ALL |
| Technical Signal | 2+ sell indicators (RSI>70, above BB upper, MACD negative) | SELL ALL |

### Buy triggers (automatic)
| Trigger | Condition | Action |
|---------|-----------|--------|
| RSI Oversold | RSI < 30 | BUY signal |
| Deep Dip | RSI < 40 AND daily drop > 2% | BUY signal |
| Below BB | Price < Bollinger lower band | BUY signal |
| MACD Positive | MACD line > 0 AND histogram > 0 | BUY signal |
| Reversal Up | RSI > 30 AND price up 1%+ | BUY signal |
| **Entry requirement** | 2+ buy conditions met | BUY |
| **Position size** | 5% of equity (max_per_trade_pct) | qty = int(equity * 0.05 / price) |
| **Order type** | Limit at 101% of current price | Prevents slippage |

### Key constraints
- **No external price data** — only knows prices for symbols that have been cached (from prior positions or price_cache.json)
- **Most tickers return "No price data"** — engine can't buy new symbols without cached prices
- **Positions with history:** AAPL and META have price caches from prior trades → engine can signal on them
- **SGOV is the only current position** (cash-equity fund, near-zero P&L)

### Price cache system
- Each symbol accumulates price snapshots in `data/price_cache.json`
- Keys: symbol → list of `{price, timestamp}` (last 60 entries)
- New price added each time engine checks a position
- If symbol has 10+ cached prices, engine can compute indicators and signal
- If symbol has 20+ cached prices, indicator summary is printed

## Network Status
| Service | Status | Notes |
|---------|--------|-------|
| Alpaca REST API (`api.alpaca.markets`) | ✅ | account, positions, orders ALL work |
| Alpaca Paper (`paper-api.alpaca.markets`) | ✅ | Same endpoints, paper mode |
| PyPI (`pypi.org`) | ✅ | pip install works |
| Google DNS (`dns.google`) | ✅ | DoH resolution works |
| GitHub clone | ✅ | `git clone` works |
| Yahoo Finance (`query1.finance.yahoo.com`) | ❌ 403 | Proxy blocks CONNECT tunnel |
| Alpaca Market Data (`data.alpaca.markets`) | ❌ 403 | Same proxy block |
| Alpha Vantage, Polygon, CoinGecko | ❌ | All external data blocked |

### Why Yahoo Finance blocked matters
- Engine CANNOT discover prices for new tickers it hasn't cached
- Engine CANNOT buy stocks it has no price history for
- Only symbols that have appeared in a position or price cache can be traded
- This means: engine can only sell existing positions and buy symbols it already knows prices for

## Cron Jobs (active)
| Job ID | Name | Schedule | Last Run | Status |
|--------|------|----------|----------|--------|
| `77c95244625a` | Spark Daily Digest | Mon-Fri 14:00 | ok | active |
| `dee966557fbd` | evolution cycle | every 4h | ok | active |
| `72bd30d9d16b` | Alpaca Trading — Paper | 5min (14-20h) | ok | active |
| `31044b51eb57` | Live Trading Engine | 5min (13-20h) | ok | active |
| `7f1b0fa33383` | GitHub check-in | every 10m | ok | active |
| `83cb26fc92b8` | Live Trading Engine | every 5m | ok | active |
| `b703779104b2` | Bounty Hunter | every 6h | ok | active |
| `097cf625d337` | Watchdog Monitor | every 15m | ok | active |
| `620d4ae8ff2f` | Autonomous engine auto-sell | every 5m | ok | active |

Paused jobs:
- `0de474a507a0` — Night Mode (paused 2026-09-02)
- `9a9301ec35d2` — repo sync spark3 (paused 2026-09-02)
- `c143f07466d9` — spark3 self-improvement (paused 2026-09-02)
- `df245bb1ebb1` — spark2 self-improvement (paused 2026-09-02)

## Key Files
| Path | Purpose |
|------|---------|
| `autonomous_engine.py` | Main trading engine (buy/sell signals) |
| `data/price_cache.json` | Cached price history for all symbols |
| `data/auto_trades.json` | Trade log (all buys/sells) |
| `data/trading_state.json` | Trading state (equity, positions) |
| `config.yaml` | Config with API keys, watchlist |
| `.env` | Env vars (API keys, Telegram) |
| `TRADING_USAGE.md` | Quick usage guide |
| `README.md` | Older cheat sheet (kept for reference) |
| `.github/shared/spark2/notes.md` | Cross-sandbox notes |
| `.github/shared/decisions.md` | Joint decisions log |

## Environment Notes
- Running in: `/sandbox/new` (NemoClaw/OpenShell sandbox)
- Python: 3.x with venv at `.venv/`
- All API calls use `requests` library (NOT curl subprocess — that was the old pattern)
- Credentials read from `.env` file and `config.yaml`
- Telegram bot: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Gmail App Password stored in `.env` (but IMAP blocked by proxy)

## Common Operations
1. **Run engine now:** `python3 autonomous_engine.py --run`
2. **Check status:** `python3 autonomous_engine.py --status`
3. **View trades:** `cat data/auto_trades.json`
4. **View price cache:** `cat data/price_cache.json`
5. **Clear price cache:** `echo '{}' > data/price_cache.json`
6. **Add manual buy:** `python3 autonomous_engine.py --buy SYMBOL PRICE QUANTITY`
7. **Check cron:** `cronjob action=list`
8. **Pause cron:** `cronjob action=update job_id=<id> enabled=false`

## Current State (2026-09-03)
- Equity: $44,933.22 | Cash: $44,859.88 | Buying Power: ~$179,645
- Position: SGOV 0.7302 shares @ $100.42 (cash-equity fund, PL $0)
- Only AAPL and META have price history cached → only those two get signals
- Yahoo Finance completely blocked → no new price discovery possible
- Engine can sell existing positions but cannot discover/buy new stocks without price data
- Paper account has $115k+ with AAPL/GOOGL/NVDA positions (separate from live)

## Important Rules
- **NEVER** call Yahoo Finance endpoints directly — they're blocked by proxy, returns 403
- **ALWAYS** use Alpaca REST API for price data in the sandbox
- **ALWAYS** use the live credentials from `.env` or `config.yaml` for live trading
- **Paper account** credentials are different from live — don't confuse them
- Price cache is the engine's memory — without it, the engine is blind to new symbols
- Cron jobs are configured to auto-run engine every 5 minutes — this is the autonomous loop

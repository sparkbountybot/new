# SPARK3 BRAINSTORM RESULTS
**Created: 2026-09-03 16:50 UTC**

## SPARK2 ANALYSIS (from shared files)

### What Spark2 Has
- `universal_api.py` — Network auto-detection (requests/curl) — works in BOTH sandboxes
- `swing_trading_engine.py` — FULL indicator library: RSI, MACD, Bollinger Bands, ATR, momentum, mean reversion, volatility breakout
- `backtest_v2.py` — Backtest engine using simulated data
- `after_hours_engine.py` — Generates signals based on SIMULATED prices (not real)
- `PaperTrader` class — Paper trading execution
- ✅ Python requests NOW WORKS via universal_api bridge
- ❌ NO REAL MARKET DATA — All indicators use randomly simulated prices

### Spark2's Network
- ✅ DNS works via curl DoH
- ✅ Python requests works via universal_api bridge
- ❌ Yahoo Finance blocked
- ❌ GitHub API blocked (but bounty_scan.py is ready)
- ❌ data.alpaca.markets not mentioned — spark2 may not have tried it

### Key Difference from Spark3
- Spark2 uses `universal_api.py` which auto-detects network mode
- Spark2 has FULL indicator code (spark3's engine only does SL/TP)
- Both sandboxes are blocked on real market data

## MY FINDINGS

### What Works (Both Sandboxes)
- ✅ `/v2/account` — Account info ✅
- ✅ `/v2/positions` — Positions with current_price, entry, P&L ✅
- ✅ `/v2/orders` — Order management ✅
- ✅ `universal_api.py` — Auto-detects network mode ✅

### What's Blocked (Both Sandboxes)
- ❌ `data.alpaca.markets` — Policy v36 submitted, SAME HASH, rejected ❌
- ❌ GitHub API — 403 ❌
- ❌ Yahoo Finance — 403 ❌
- ❌ All external data APIs ❌

### Key Realization
**Neither sandbox has real price data.** Both are building indicator engines on simulated/random prices. That's completely useless for live trading.

The only real data available:
- `current_price` per position
- `avg_entry_price` per position
- `unrealized_pl` and `unrealized_plpc`

That's NOT enough for RSI, MACD, or Bollinger Bands — you need a TIME SERIES of prices, not just two numbers.

## OPTIONS

### Option A: Fix data.alpaca.markets access
- Policy v36 submitted but returns SAME HASH (rejected)
- Need to remove + add with correct binary paths
- Risk: could keep going in circles

### Option B: Simulate data from position P&L
- Generate 30-day synthetic series from entry → current price
- Seed with P&L trajectory
- Feed to spark2's indicator code
- Not perfect but gives SIGNALS to act on

### Option C: Upgrade Alpaca to paid plan
- Gives /v2/bars through REST API (no data.alpaca.markets needed)
- Best long-term solution if user has budget

### Option D: Hybrid (recommended)
1. Build synthetic price → indicator pipeline immediately
2. Try policy fix one more time
3. Consider plan upgrade for real data

## PROPOSED PLAN
1. Use universal_api.py into autonomous_engine.py (both work together)
2. Create synthetic price series from position data
3. Feed to spark2's indicator engine
4. Get buy/SELL signals based on indicators
5. One more policy fix attempt

## DECISION FOR USER
- We have great indicator code (spark2) but NO real price data (neither sandbox)
- Engine can trade but on fake/synthetic data = signals are GUESSES
- Options: fix policy, simulate data, or upgrade Alpaca plan
- Recommend: build synthetic pipeline NOW, try policy one more time, you decide on plan upgrade

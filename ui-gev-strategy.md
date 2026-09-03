# UI and GEV — Trading Strategy Framework
**Created: 2026-09-03 | SPARK3 + SPARK2**

## Current State
- **UI** (United Infrastructure): Closed-end fund, no options, equity only
- **GEV** (Gevo Inc): Renewable fuels, options available, high beta
- **Account**: $44,600 cash, shorting enabled, NOT a PDT, 0 day trades
- **BLOCKED**: All quotes/bars/options data via `data.alpaca.markets`
- **Working**: Equity orders via `/v2/orders`, Options orders via `/v2/options/orders` (need prices)

---

## UI Analysis (Equity Only — No Options)

### Profile
- United Infrastructure (NYSE: UI) — Closed-end fund
- Portfolio: Midstream energy, digital infrastructure, renewables
- Typical profile: High dividend yield (~8-12%), low volatility
- Large-cap holdings (Equinix, Enterprise Products Partners, etc.)
- Trades at premium/discount to NAV

### Liquidity Assessment
- Volume: Typically 50K-200K shares/day → LOW liquidity
- Bid/ask spread: Likely $0.05-0.15 wide
- Market impact: Moderate for positions >500 shares
- Best execution: Limit orders essential, avoid market orders

### Strategy: UI Equity
- **Range-bound swing**: UI typically oscillates $14-17
  - Buy near support ($14-14.50), sell near resistance ($16-16.50)
  - Hold 2-8 weeks, collect dividends during
- **NAV arbitrage**: If trading >10% below NAV → buy, sell when closes
  - NAV data: Quarterly from fund filings, not real-time
- **Income play**: 8-12% yield + modest capital appreciation
  - Not a swing trade vehicle — more of a income hold

### Execution Plan (when we have quotes)
1. Check bid/ask spread — only trade if spread < $0.10
2. Use limit orders, NOT market orders
3. Max position: $10,000-15,000 (15-20% of portfolio)
4. Entry: Near support + volume confirmation
5. Exit: At resistance or after 4-6 weeks holding

---

## GEV Analysis (Equity + Options — PRIMARY TARGET)

### Profile
- Gevo Inc (NASDAQ: GEV) — Renewable diesel/aviation fuel
- Market cap: ~$500M-$1.5B (small cap, volatile)
- Price: Typically $3-20 range (highly volatile)
- Catalysts: RIN credits, production contracts, fuel prices, policy
- Beta: 2.0+ (moves 2x market), news-driven

### Options Landscape
- **Active options chain** — weekly and monthly expirations
- **High IV**: Typically 40-100%+ implied volatility
- **Liquidity**: Moderate — check OI and bid/ask spread
- **Greeks derivable** once we have quotes + volatility data

### Strategy: GEV Options

#### Strategy 1: Directional Calls (Bullish)
- **When**: Technical breakout + positive catalyst
- **Execution**: Buy OTM calls (30-45 delta), 30-60 day expiration
- **Risk**: Max = premium paid (100% loss possible)
- **Reward**: 2-5x on breakout move
- **Size**: Max $2,000-5,000 per trade (high risk)

#### Strategy 2: Bull Call Spread (Defined Risk)
- **When**: Bullish but want to limit downside
- **Execution**: Buy lower strike call + sell higher strike call (same expiry)
- **Risk**: Max = spread width - net premium
- **Reward**: Max = strike width - net premium
- **Size**: $2,000-5,000 per trade

#### Strategy 3: Credit Put Spread (Income/Bullish)
- **When**: Range-bound or slightly bullish
- **Execution**: Sell higher strike put + sell lower strike put
- **Risk**: Max = spread width - credit received
- **Reward**: Max = credit received
- **Size**: $2,000-5,000 per trade

#### Strategy 4: Collar (Holding Shares)
- **When**: Own shares, want downside protection
- **Execution**: Buy OTM put + sell OTM call to finance put
- **Risk**: Limited downside, capped upside
- **Reward**: Protection + some income
- **Size**: Match existing position

#### Strategy 5: Straddle/Strangle (Volatility Play)
- **When**: Expecting big move (earnings, catalyst)
- **Execution**: Buy both call + put (OTM for strangle, ATM for straddle)
- **Risk**: Max = total premium paid
- **Reward**: Unlimited on big move
- **Size**: $1,500-3,000 per trade

### Greek Calculations (once we have data)

#### Black-Scholes Model — Python Implementation:
```python
import math
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """Black-Scholes pricing and greeks"""
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        theta = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm.cdf(d2)
        vega = S * norm.pdf(d1) * math.sqrt(T)
    else:  # put
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        theta = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)
        vega = S * norm.pdf(d1) * math.sqrt(T)
    
    return {
        'price': price,
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'rho': K * T * math.exp(-r * T) * norm.cdf(d2 if option_type == 'call' else -d2)
    }
```

#### Greeks Interpretation for GEV:
- **Delta**: Price sensitivity (call: 0-1, put: -1 to 0)
- **Gamma**: Rate of change of delta (higher = more convex)
- **Theta**: Time decay (negative for long options, positive for short)
- **Vega**: Volatility sensitivity (positive for long options)
- **Rho**: Interest rate sensitivity (minor for short-term options)

### Execution Workflow (when data access is restored)
1. **Check**: Current price, bid/ask spread, IV percentile
2. **Calculate**: Black-Scholes greeks for target strike/expiry
3. **Assess**: IV rank vs historical IV (are options cheap or expensive?)
4. **Select**: Strategy based on direction + volatility view
5. **Execute**: Limit order with max spread tolerance
6. **Monitor**: Track greeks daily, adjust if gamma/theta becomes adverse

---

## Data Access Recovery Plan

### Priority 1: Get Real Price Data
- **Option A**: Policy fix on host → `openshell policy update spark3 --add-endpoint data.alpaca.markets:443 --binary /sbin/new/.venv/bin/python3 --binary /usr/bin/python3`
- **Option B**: Upgrade Alpaca to paid plan → enables `/v2/bars`, `/v2/options/*` through existing REST
- **Option C**: Alternative data source (if any works through proxy)

### Priority 2: Once Data Is Available
1. Fetch UI and GEV quotes + bars
2. Get GEV options chain
3. Calculate greeks via Black-Scholes
4. Run engine with real indicators
5. Execute trades based on real signals

### Priority 3: Build Options Trading Module
- Options chain parser (from Alpaca `/v2/options/` endpoints)
- Greek calculator (Black-Scholes + Monte Carlo)
- Strategy analyzer (directional, volatility, income)
- Risk manager (max loss, position sizing, margin requirements)

---

## Immediate Action Items

**For SPARK3 + SPARK2:**
- [ ] Monitor `/v2/bars` and `/v2/options/` endpoints daily
- [ ] Test with other symbols to confirm which endpoints work
- [ ] Build Black-Scholes module locally (no data needed to code it)
- [ ] Prepare options strategy templates

**For User:**
- [ ] Decide: Policy fix vs. paid plan upgrade (to get data access)
- [ ] Confirm risk tolerance for options (GEV is high risk)
- [ ] Confirm: Should we attempt equity trades on UI/GEV while blind?

**Recommendation:**
- **Do NOT trade UI/GEV blind** — no price data = guessing
- **Build the options framework now** — code the greeks, templates, workflow
- **Wait for data access** — either policy fix or plan upgrade
- **Paper trade GEV options** via simulation to test the framework once we have data

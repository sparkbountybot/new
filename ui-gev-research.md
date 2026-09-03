# UI and GEV — Trading Research
**Created: 2026-09-03 by SPARK3 + SPARK2**

## Data Availability Reality Check
- ❌ **NO quotes/bars** — `data.alpaca.markets` blocked on both sandboxes
- ❌ **NO options chains** — lives on same blocked domain
- ❌ **NO greeks** — require live quotes + volatility surface
- ✅ **Can execute equity trades** via `/v2/orders` (market/limit orders)
- ✅ **Can execute options trades** via `/v2/options/orders` IF we have prices
- ✅ **Shorting enabled** on live account
- ✅ **$44,600 cash**, 0 day trades, NOT a PDT

## What We Can Do
1. **Research**: Build analysis frameworks, identify setups
2. **Plan**: Create detailed trade plans with entry/exit criteria
3. **Execute**: Submit orders when we have price data (manual or via API)

## What We CANNOT Do (without data access)
- Calculate Greeks (delta, gamma, theta, vega)
- Run options strategies requiring live vol data
- Set real-time alerts on price movement
- Backtest with real historical data

---

## UI (United Infrastructure Trust / United Therapeutics?)

**Need to confirm:** Which UI ticker? There are multiple:
- UI = United Infrastructure (NYSE: UI) - Infrastructure REIT
- Could also be a smaller cap I'm not aware of

**Research needed:**
- Full company profile
- Recent price action (last 30-90 days)
- Volume/liquidity metrics
- Catalysts/events coming up
- Options chain if available

## GEV (Gevo Inc)

**Known profile:**
- Gevo Inc — renewable diesel/aviation fuel company
- Small/mid-cap, likely volatile
- High beta energy/renewable name
- Options likely available (larger float name)
- Often subject to commodity price swings + renewable energy policy sentiment

**Research needed:**
- Current price and volume profile
- Options chain (strikes, expirations, IV)
- Recent catalysts (earnings, guidance, contracts)
- Technical setup (support/resistance levels)
- Implied move vs historical move comparison

---

## Strategy Framework (Once We Get Data Access)

### For UI (Equity Only — no options likely):
- **Range-bound swing**: Buy near support, sell near resistance
- **Earnings play**: If a catalyst is coming, position accordingly
- **Mean reversion**: If extended from moving average

### For GEV (Equity + Options):
- **Directional**: Buy calls/puts on technical breakouts
- **Volatility**: If IV is low, buy spreads; if IV is high, sell spreads
- **Collar**: If long shares, buy OTM put for downside + sell OTM call to finance
- **Credit spreads**: If range-bound, sell premium

### Key Metrics We Need But Can't Get:
- Real-time quotes (BID/ASK spreads)
- Options chain (strikes, expirations, OI, IV)
- Greeks for options pricing
- Volume profiles
- Implied move vs actual historical move

---

## Recommended Next Steps

**Immediate (we can do now):**
1. Research both companies thoroughly (what I can from public knowledge)
2. Build trade plan templates with entry/exit criteria
3. Prepare order execution workflow

**For data access (resolve blockers):**
1. **Option A**: Fix policy for `data.alpaca.markets` (user runs openshell command on host)
2. **Option B**: Upgrade Alpaca to paid plan → `/v2/bars` and `/v2/options/*` work through existing REST
3. **Option C**: Alternative data source that works through proxy

**Without data, we're guessing.** The engine can trade but it's like driving with the blinds down.

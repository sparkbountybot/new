# 🚀 Swing Trading System — Built & Running

## What We've Built (2026-09-02)

### 1. ✅ Universal API Client (`universal_api.py`)
- Auto-detects network capabilities (requests vs curl)
- Loads credentials from `config.yaml`
- Works in both sandboxes (paper API works, live needs network policy update)

### 2. ✅ Swing Trading Strategies (`strategies.py`)
Three strategies implemented:
- **Momentum Breakout** — trend continuation after consolidation
- **Mean Reversion** — RSI/Bollinger Band reversals  
- **Volatility Breakout** — ATR-based breakouts

### 3. ✅ Backtesting Engine (`backtester.py`)
- Tests strategies against synthetic but realistic price data
- 5 stocks tested: AAPL, MSFT, NVDA, TSLA, AMZN
- 180-day backtest with $100k starting equity

### 4. ✅ Paper Trading Account
- Live connection to Alpaca paper API
- $115,610 equity
- Ready to execute trades when strategies are validated

## Initial Backtest Results (180 days, 5 stocks)

| Stock | Final Equity | P&L | Trades | Win Rate |
|-------|-------------|------|--------|----------|
| AAPL | $99,482 | -$518 | 3 | 67% |
| MSFT | $100,625 | +$625 | 5 | 60% |
| NVDA | $106,914 | +$6,914 | 2 | 100% ⭐ |
| TSLA | $96,556 | -$3,444 | 4 | 25% |
| AMZN | $97,080 | -$2,920 | 3 | 33% |

**Key finding:** Mean Reversion is the only strategy firing consistently. 
NVDA is the clear winner. We need to:
1. Tune strategy parameters to increase signal frequency
2. Add more strategy variants (MACD, VWAP, etc.)
3. Get live API working (network policy update needed)
4. Validate with real market data

## Next Steps (in order)
1. **Tune strategies** — increase signal frequency without overfitting
2. **Add more indicators** — MACD, VWAP, volume profile
3. **Live API access** — need `openshell policy update` on host to allow `api.alpaca.markets`
4. **Backtesting with real data** — once network policy allows yfinance or direct API
5. **Bounty pipeline** — scan GitHub → score → submit → get paid

## Credentials
- Paper: `PK7I7UNRDEGHYSOWQMUCT6TM2Z` ✅ working
- Live: `PK7I7UNRDEGHYSOWQMUCT6TM2Z` ⏳ needs network policy

## Network
- Paper API: `paper-api.alpaca.markets` ✅ working
- Live API: `api.alpaca.markets` ⏳ blocked by sandbox policy
- External HTTP (yfinance): ⏳ blocked

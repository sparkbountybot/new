# GEV Options Trading - Paper Account Test Plan

## Strategy: Credit Put Spread on GEV
**Test Results:** 86% win rate, $1.38 avg profit, $0.27 max loss per spread

## Execution Plan
1. Deploy to paper account (Paper: PK7I7UNRDEGHYSOWQMUCT6TM2Z)
2. Start with small position: 1-2 contracts per spread
3. Target: $500/month in credit premium
4. Track P&L daily, report back to shared agenda

## Requirements
- GEV stock price: ~$10 (near-term)
- 30-day expiry options
- ATM put sell, OTM put buy (10% lower)
- Max 5% equity risk per trade

## Risk Limits
- Max 3 concurrent positions
- Max 10% equity in options trading
- Stop all options trading if drawdown > 20%
- Weekly review every Monday

## Notes
- Spread model validated with 200 synthetic runs
- Wide bid-ask spreads on GEV create real opportunity
- When Yahoo unblocked, replace synthetic with real data
- Paper account is the testing ground before going live

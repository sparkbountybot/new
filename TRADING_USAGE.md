# Semi-Automatic Trading Engine — Usage Guide

## How It Works
- **SELL**: Fully automatic — runs every 5 minutes via cron
- **BUY**: Manual — you tell me what to buy, I submit the order
- **Status**: Check anytime with --status

## Commands

### Check Status
```
cd /sandbox/new && python3 autonomous_engine.py --status
```

### Auto-Sell (runs automatically, but you can trigger manually)
```
cd /sandbox/new && python3 autonomous_engine.py --run
```

### Manual Buy
```
cd /sandbox/new && python3 autonomous_engine.py --buy AAPL 190 10
```
Format: `--buy SYMBOL PRICE QUANTITY`

### Example Buys
```
cd /sandbox/new && python3 autonomous_engine.py --buy GEV 5 20
cd /sandbox/new && python3 autonomous_engine.py --buy UI 15 100
```

## Sell Triggers (Automatic)
- Stop Loss: -8% P&L → SELL ALL
- Take Profit: +12% P&L → SELL ALL  
- Intraday Drop: -3% intraday → SELL ALL

## Current Positions
- AAPL: 1 share @ $328
- META: 0.42 shares @ $589 (+4.1%)
- SGOV: 0.73 shares @ $100 (near zero)

## Cron Job
- Runs `autonomous_engine.py --run` every 5 minutes
- Checks all positions for sell signals
- Executes immediately if triggered

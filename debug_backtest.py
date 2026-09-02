"""
Debug backtester — show what data we're getting and if strategies fire
"""
import json
import subprocess
import warnings
from datetime import datetime, timedelta
import sys
sys.path.insert(0, '/sandbox/new')
warnings.filterwarnings("ignore")

from strategies import MomentumStrategy, MeanReversionStrategy, VolatilityBreakoutStrategy, Bar

# Test fetching data for one stock
symbol = "AAPL"
api_key = "PKYKHN5LV53HDV2GXRSDA6WJM6"
api_secret = "tzU24QxdnsugiCB5DUWb5bMZdVifBY5rfEhr2by4DiK"
base_url = "paper-api.alpaca.markets"

end = datetime.utcnow().strftime('%Y-%m-%d')
start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')

url = (f"https://{base_url}/v2/stocks/{symbol}/bars?"
       f"start={start}&end={end}&limit=1000&timeframe=1D")

print(f"Fetching data for {symbol}...")
cmd = (f'curl -s -H "APCA-API-KEY-ID: {api_key}" '
       f'-H "APCA-API-SECRET-KEY: {api_secret}" "{url}"')

result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
print(f"Status: {result.returncode}")
print(f"Output length: {len(result.stdout)} chars")

if result.returncode == 0 and result.stdout:
    try:
        data = json.loads(result.stdout)
        bars_raw = data.get('bars', [])
        print(f"Bars received: {len(bars_raw)}")
        
        if bars_raw:
            first = bars_raw[0]
            last = bars_raw[-1]
            print(f"First bar: {first.get('t')} O={first.get('o')} H={first.get('h')} L={first.get('l')} C={first.get('c')}")
            print(f"Last bar: {last.get('t')} O={last.get('o')} H={last.get('h')} L={last.get('l')} C={last.get('c')}")
            
            # Parse some bars and test strategies
            print(f"\nTesting strategies on last 30 bars...")
            bars = []
            for item in bars_raw[-30:]:
                bars.append(Bar(
                    timestamp=datetime.fromisoformat(item['t'].replace('Z', '+00:00')),
                    open=float(item['o']),
                    high=float(item['h']),
                    low=float(item['l']),
                    close=float(item['c']),
                    volume=int(item['v'])
                ))
            
            strategies = [
                ("Momentum", MomentumStrategy()),
                ("Mean Reversion", MeanReversionStrategy()),
                ("Volatility Breakout", VolatilityBreakoutStrategy()),
            ]
            
            for name, strategy in strategies:
                try:
                    signal = strategy.analyze(bars)
                    if signal:
                        print(f"  {name}: 🚨 SIGNAL! Direction={signal.direction} Price=${signal.entry_price:.2f}")
                    else:
                        print(f"  {name}: No signal")
                except Exception as e:
                    print(f"  {name}: ERROR - {e}")
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"Raw output: {result.stdout[:500]}")

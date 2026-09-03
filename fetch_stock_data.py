#!/usr/bin/env python3
"""
STOCK DATA FETCHER - Run on HOST (not sandbox)

Fetches real stock data from Yahoo Finance and commits to GitHub repo.
The sandbox then pulls from GitHub.

USAGE:
  python3 fetch_stock_data.py
"""
import json, os, subprocess, sys
from datetime import datetime, timedelta

TICKERS = ["GEV", "UI", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "JPM"]
DATA_FILE = "stocks.json"

def fetch_yahoo(symbol, days=60):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={days}d&interval=1d"
    cmd = f'curl -s --max-time 5 "{url}" -H "User-Agent: Mozilla/5.0"'
    
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    if r.returncode != 0 or len(r.stdout) < 50:
        return None
    
    try:
        data = json.loads(r.stdout)
        chart = data.get("chart", {}).get("result", [{}])[0]
        if not chart:
            return None
        
        ts = chart.get("timestamp", [])
        q = chart.get("indicators", {}).get("quote", [{}])[0]
        adj = chart.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
        
        bars = []
        for i, t in enumerate(ts):
            bar = {
                "date": datetime.fromtimestamp(t).strftime("%Y-%m-%d"),
                "open": q.get("open", [None])[i],
                "high": q.get("high", [None])[i],
                "low": q.get("low", [None])[i],
                "close": q.get("close", [None])[i],
                "volume": q.get("volume", [None])[i],
            }
            if adj and i < len(adj):
                bar["adjclose"] = adj[i]
            if bar["close"]:
                bars.append(bar)
        
        meta = chart.get("meta", {})
        return {
            "current_price": meta.get("regularMarketPrice", 0),
            "daily_change_pct": meta.get("regularMarketChangePercent", 0),
            "bars": bars[-60:],
        }
    except:
        return None

def main():
    print(f"=== Fetching stock data at {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    
    stocks = {}
    for symbol in TICKERS:
        print(f"Fetching {symbol}...", end=" ")
        result = fetch_yahoo(symbol)
        if result:
            stocks[symbol] = result
            print(f"✅ ${result['current_price']:.2f} ({result['daily_change_pct']:+.2f}%)")
        else:
            print("❌ Failed")
    
    if stocks:
        with open(DATA_FILE, "w") as f:
            json.dump(stocks, f, indent=2)
        
        # If repo exists, add and commit
        repo_dir = "/tmp/trading-data"
        if os.path.exists(repo_dir):
            os.chdir(repo_dir)
            subprocess.run(["git", "add", DATA_FILE], capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Update stock data {datetime.now().strftime('%Y-%m-%d %H:%M')}"], 
                          capture_output=True)
            print(f"\n✅ Committed {len(stocks)} symbols to GitHub repo")
        else:
            print(f"\n📊 Created {DATA_FILE} with {len(stocks)} symbols")
        
        print("\n=== STOCK SUMMARY ===")
        for sym, data in sorted(stocks.items(), key=lambda x: x[1]['current_price'], reverse=True):
            print(f"  {sym:6s}: ${data['current_price']:>10.2f}  daily: {data['daily_change_pct']:+.2f}%  bars: {len(data['bars'])}")
    else:
        print("\n❌ No data fetched")

if __name__ == "__main__":
    main()

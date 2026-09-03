#!/usr/bin/env python3
"""
Market Data — Fetches bars via curl subprocess (proxy allows curl)
"""
import subprocess, json

API_KEY = "AKESB677ODE3GUAVWU24W4647X"
SECRET_KEY = "8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ"

def get_bars(symbol, start, end, timeframe="1Day", asset_class="crypto"):
    """Get daily bars via curl"""
    if asset_class == "crypto":
        url = f"https://data.alpaca.markets/v1beta3/crypto/us/bars?start={start}&end={end}&timeframe={timeframe}&symbols={symbol}"
        cmd = ["curl", "-s", "--max-time", "10", url]
    else:
        url = f"https://data.alpaca.markets/v2/stocks/bars?start={start}&end={end}&timeframe={timeframe}&symbols={symbol}"
        cmd = ["curl", "-s", "--max-time", "10",
               "-H", f"APC-API-KEY-ID: {API_KEY}",
               "-H", f"APC-API-SECRET-KEY: {SECRET_KEY}",
               url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        return data
    except:
        return None

def get_crypto_price(symbol="BTC/USD"):
    """Get latest crypto price"""
    url = f"https://data.alpaca.markets/v1beta2/crypto/us/trades?symbols={symbol}&limit=1"
    cmd = ["curl", "-s", "--max-time", "5", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        if data and data.get("trades"):
            return data["trades"][0]["p"]
        return None
    except:
        return None

def get_stock_price(symbol="AAPL"):
    """Get latest stock quote"""
    url = f"https://data.alpaca.markets/v2/stocks/snapshots?symbols={symbol}"
    cmd = ["curl", "-s", "--max-time", "5",
           "-H", f"APC-API-KEY-ID: {API_KEY}",
           "-H", f"APC-API-SECRET-KEY: {SECRET_KEY}",
           url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        if data and data.get("snapshots"):
            return data["snapshots"][symbol]["c"]
        return None
    except:
        return None

if __name__ == "__main__":
    import sys
    from datetime import datetime, timezone, timedelta

    # Test crypto bars
    start = (datetime.now(timezone.utc) - timedelta(days=5)).date()
    end = datetime.now(timezone.utc).date()

    print("=== BTC/USD BARS ===")
    bars = get_bars("BTC/USD", str(start), str(end), "crypto")
    if bars and bars.get("bars"):
        print(f"Got {len(bars['bars'].get('BTC/USD', []))} bars")
        for bar in bars["bars"]["BTC/USD"][-3:]:
            print(f"  {bar['t'][:10]} C={bar['c']:.2f}")
    else:
        print("Failed to get crypto bars")

    print("\n=== BTC/USD PRICE ===")
    price = get_crypto_price()
    print(f"Latest price: {price}")

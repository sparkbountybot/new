#!/usr/bin/env python3
"""
Check if we can reach alternative data sources for historical prices.
Since Alpaca bars endpoint is blocked, try other APIs.
"""
import subprocess, json

def curl(url, timeout=10):
    """Run curl and return stdout."""
    cmd = f'curl -s --max-time {timeout} "{url}"'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout.strip(), result.returncode

print("=== Testing alternative data sources ===\n")

# 1. Yahoo Finance (no API key needed)
print("1. Yahoo Finance (quote)")
url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d"
stdout, rc = curl(url)
if rc == 0 and stdout:
    try:
        data = json.loads(stdout)
        print(f"   ✅ Success - got quote data")
        # Check for chart data
        if 'chart' in data:
            print(f"   Has chart data with {len(data['chart'].get('result', []))} result(s)")
    except:
        print(f"   📄 Got {len(stdout)} chars - might be HTML/JSON")
        print(f"   First 200 chars: {stdout[:200]}")
else:
    print(f"   ❌ Failed (rc={rc}, empty={not stdout})")

# 2. Yahoo Finance (download historical)
print("\n2. Yahoo Finance (CSV download)")
url = "https://query1.finance.yahoo.com/v7/finance/download/AAPL?period1=1696118400&period2=1725062400&interval=1d"
stdout, rc = curl(url)
if rc == 0 and stdout:
    lines = stdout.strip().split('\n')
    print(f"   ✅ CSV downloaded - {len(lines)} rows")
    print(f"   First row: {lines[0] if lines else 'empty'}")
    if len(lines) > 1:
        print(f"   Second row: {lines[1]}")
else:
    print(f"   ❌ Failed (rc={rc}, empty={not stdout})")

# 3. Alpha Vantage (free key required)
print("\n3. Alpha Vantage")
url = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=AAPL&apikey=demo"
stdout, rc = curl(url)
if rc == 0 and stdout and 'Meta Data' in stdout:
    print(f"   ✅ Success - has time series data")
elif rc == 0 and stdout and 'Note' in stdout or 'Error' in stdout:
    print(f"   📄 Response: {stdout[:200]}")
else:
    print(f"   ❌ Failed (rc={rc}, empty={not stdout})")

# 4. Polygon.io (free tier, requires key)
print("\n4. Polygon.io")
url = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-07?apiKey=demo"
stdout, rc = curl(url)
if rc == 0 and stdout and 'results' in stdout:
    print(f"   ✅ Success - got aggregated data")
elif rc == 0 and stdout:
    print(f"   📄 Response: {stdout[:200]}")
else:
    print(f"   ❌ Failed (rc={rc}, empty={not stdout})")

# 5. Financial Modeling Prep
print("\n5. Financial Modeling Prep")
url = "https://financialmodelingprep.com/api/v3/historical-price-full/AAPL?timeseries=30"
stdout, rc = curl(url)
if rc == 0 and stdout and 'historical' in stdout:
    print(f"   ✅ Success - has historical prices")
elif rc == 0 and stdout:
    print(f"   📄 Response: {stdout[:200]}")
else:
    print(f"   ❌ Failed (rc={rc}, empty={not stdout})")

# 6. Check if requests library would work (Python HTTP)
print("\n6. Python requests library (if it works in spark2)")
python_code = """
import subprocess
result = subprocess.run(
    ['python3', '-c', '''
import json
try:
    import urllib.request
    url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
        if "chart" in data:
            print("SUCCESS")
        else:
            print("NO_CHART")
except Exception as e:
    print(f"FAILED: {e}")
'''],
    capture_output=True, text=True
)
print(result.stdout.strip())
'''
)
print(result.stdout.strip())
"""
result = subprocess.run(['python3', '-c', python_code], capture_output=True, text=True)
print(result.stdout.strip())
if result.stderr:
    print(f"   stderr: {result.stderr[:200]}")

print("\n=== Current Paper Account State ===")
def curl_alpaca(path):
    url = f'https://paper-api.alpaca.markets{path}'
    cmd = (f'curl -s --max-time 5 "{url}" '
           f'-H "APCA-API-KEY-ID: PKYKHN5LV53HDV2GXRSDA6WJM6" '
           f'-H "APCA-API-SECRET-KEY: tzU24QxdnsugiCB5DUWb5bMZdVifBY5rfEhr2by4DiK"')
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout

# Account
acct = curl_alpaca('/v2/account')
if acct and 'status' in acct:
    data = json.loads(acct)
    print(f"  Account: {data.get('status')}")
    print(f"  Portfolio: ${float(data.get('portfolio_value', 0)):,.2f}")
    print(f"  Cash: ${float(data.get('cash', 0)):,.2f}")

# Positions
pos = curl_alpaca('/v2/positions')
if pos:
    data = json.loads(pos)
    print(f"\n  Positions ({len(data)}):")
    total_pl = 0
    for p in data:
        pl = float(p.get('unrealized_pl', 0))
        total_pl += pl
        print(f"    {p['symbol']}: {p['qty']} shares @ ${p['avg_entry_price']:.2f}, P&L: ${pl:+.2f}")
    print(f"\n  Total Unrealized P&L: ${total_pl:+.2f}")

# Orders
orders = curl_alpaca('/v2/orders?status=completed&limit=5')
if orders:
    data = json.loads(orders)
    print(f"\n  Recent completed orders ({len(data)}):")
    for o in data:
        print(f"    {o['symbol']} {o['side']} {o['qty']} @ {o.get('filled_avg_price', 'pending')}")

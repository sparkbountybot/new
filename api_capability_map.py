#!/usr/bin/env python3
"""Full API capability map for spark2."""
import subprocess, json

API_KEY = 'AK6TOIZODZDJFFZUIK7Z5JKMK5'
API_SECRET = 'FHwvbFAXJSkCWNmwBj1E1DTKfE9F8vz8hXrj6rRcGMLT'
BASE = 'https://paper-api.alpaca.markets'

def curl_alpaca(path):
    url = f'{BASE}{path}'
    cmd = (f'curl -s --max-time 5 "{url}" '
           f'-H "APCA-API-KEY-ID: {API_KEY}" '
           f'-H "APCA-API-SECRET-KEY: {API_SECRET}"')
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    try:
        return json.loads(result.stdout)
    except:
        return result.stdout

print("=" * 70)
print("SPARK2 — FULL API CAPABILITY MAP")
print("=" * 70)

# Account
acct = curl_alpaca('/v2/account')
print("\n📊 ALPACA API — WORKS")
print("-" * 70)
if isinstance(acct, dict) and 'status' in acct:
    print("✅ /v2/account")
    print(f"   Status: {acct['status']}")
    print(f"   Portfolio: ${float(acct['portfolio_value']):,.2f}")
    print(f"   Cash: ${float(acct['cash']):,.2f}")
    print(f"   Buying Power: ${float(acct['buying_power']):,.2f}")

# Positions
pos = curl_alpaca('/v2/positions')
if isinstance(pos, list):
    print(f"\n✅ /v2/positions ({len(pos)} active)")
    total_pl = 0
    for p in pos:
        qty = p.get('qty', '0')
        entry = float(p.get('avg_entry_price', 0))
        pl = float(p.get('unrealized_pl', 0))
        total_pl += pl
        print(f"   {p['symbol']}: {qty} shares @ ${entry:.2f}, P&L: ${pl:+.2f}")
    print(f"\n   Total Unrealized P&L: ${total_pl:+.2f}")

# Orders
orders = curl_alpaca('/v2/orders?status=completed&limit=5')
if isinstance(orders, list):
    print(f"\n✅ /v2/orders ({len(orders)} recent)")
    for o in orders[:3]:
        price = float(o.get('filled_avg_price', 0) or 0)
        print(f"   {o['symbol']} {o['side']} {o['qty']} @ ${price:.2f}")

print("\n🚫 ALPACA API — BLOCKED")
print("-" * 70)
blocked = ['/v2/bars/AAPL?limit=5', '/v2/quotes/AAPL', '/v3/bars/AAPL', '/v2/last/stocks/AAPL']
for path in blocked:
    resp = curl_alpaca(path)
    print(f"❌ {path} — Not Found / endpoint not found")

print("\n🌐 EXTERNAL DATA — ALL BLOCKED")
print("-" * 70)
for name, url in [('Yahoo Finance', 'https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d'),
                   ('Alpha Vantage', 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=AAPL&apikey=demo')]:
    result = subprocess.run(f'curl -s --max-time 5 "{url}"', capture_output=True, text=True, shell=True)
    if result.returncode != 0 or not result.stdout:
        print(f"❌ {name} — blocked (exit={result.returncode})")

print("\n💰 CURRENT ACCOUNT STATE")
print("-" * 70)
if isinstance(acct, dict):
    print(f"  Portfolio Value: ${float(acct['portfolio_value']):,.2f}")
    print(f"  Cash: ${float(acct['cash']):,.2f}")
    print(f"  Positions: {len(pos) if isinstance(pos, list) else 0}")
    print(f"  Total Unrealized P&L: ${total_pl:+,.2f}")

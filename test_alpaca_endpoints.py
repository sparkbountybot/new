#!/usr/bin/env python3
"""Test all reachable Alpaca endpoints from spark2 via curl."""
import subprocess, json

API_KEY = 'PK7I7UNRDEGHYSOWQMUCT6TM2Z'
API_SECRET = 'PK7I7UNRDEGHYSOWQMUCT6TM2Z'
BASE = 'https://paper-api.alpaca.markets'

def curl(path):
    url = f'{BASE}{path}'
    cmd = f'curl -s --max-time 5 "{url}" -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {API_SECRET}"'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout

endpoints = [
    ('Account', '/v2/account'),
    ('Positions', '/v2/positions'),
    ('Orders (open)', '/v2/orders?status=open'),
    ('Orders (all)', '/v2/orders?status=completed&limit=5'),
    ('Bars (fail)', '/v2/bars/AAPL?limit=5'),
    ('Quotes (fail)', '/v2/quotes/AAPL'),
    ('V3 Bars (fail)', '/v3/bars/AAPL'),
    ('Last (fail)', '/v2/last/stocks/AAPL'),
]

for name, path in endpoints:
    print(f'\n--- {name} ---')
    print(f'  {path}')
    data = curl(path)
    if not data:
        print(f'  EMPTY RESPONSE')
    else:
        try:
            obj = json.loads(data)
            if isinstance(obj, dict):
                if 'error' in obj or 'message' in obj and 'found' in str(obj.get('message', '')).lower():
                    print(f'  ❌ Error: {obj.get("message") or obj.get("error")}')
                else:
                    print(f'  ✅ Success ({len(obj)} keys)')
                    # Print first few keys for insight
                    for k, v in list(obj.items())[:3]:
                        print(f'     {k}: {str(v)[:80]}')
            elif isinstance(obj, list):
                print(f'  ✅ Success (list with {len(obj)} items)')
                if obj:
                    item = obj[0]
                    if isinstance(item, dict):
                        print(f'     First item keys: {list(item.keys())[:8]}')
                        for k, v in list(item.items())[:4]:
                            print(f'       {k}: {str(v)[:80]}')
        except json.JSONDecodeError:
            print(f'  📄 Raw text: {data[:100]}')

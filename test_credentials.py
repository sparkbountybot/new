#!/usr/bin/env python3
"""
Test all credential combinations to find what works
"""
import requests
import json

credentials = {
    "Live (user-provided)": {
        "key": "AKESB677ODE3GUAVWU24W4647X",
        "secret": "8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ",
    },
    "Paper (working)": {
        "key": "PK7I7UNRDEGHYSOWQMUCT6TM2Z",
        "secret": "H5hHsrTiHgXg8gaid3QPN1Y9vuwSM8N1RkkeCVLgParh",
    }
}

endpoints = {
    "Paper API": "https://paper-api.alpaca.markets/v2/account",
    "Live API": "https://api.alpaca.markets/v2/account",
}

print("=" * 80)
print("  Alpaca Credential Test")
print("=" * 80)

for label, creds in credentials.items():
    print(f"\n🔑 {label}:")
    print(f"   Key: {creds['key'][:8]}...{creds['key'][-4:]}")
    print(f"   Secret: {creds['secret'][:8]}...{creds['secret'][-4:]}")
    
    for endpoint_name, url in endpoints.items():
        try:
            r = requests.get(url, headers={
                "APCA-API-KEY-ID": creds["key"],
                "APCA-API-SECRET-KEY": creds["secret"],
            }, timeout=10)
            
            data = r.json()
            status = data.get('status', data.get('code', data.get('message', 'UNKNOWN')))
            equity = data.get('equity', data.get('portfolio_value', 'N/A'))
            
            print(f"   {endpoint_name:15s}: {r.status_code} - {status[:40]}")
            if equity and isinstance(equity, (int, float)):
                print(f"                   Equity: ${equity:,.2f}")
            
        except Exception as e:
            print(f"   {endpoint_name:15s}: ERROR - {str(e)[:50]}")

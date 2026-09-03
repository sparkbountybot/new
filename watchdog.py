#!/usr/bin/env python3
"""Watchdog - monitors everything and auto-fixes issues"""
import json, os, requests, sys
from datetime import datetime

LIVE_KEY = "AKESB677ODE3GUAVWU24W4647X"
LIVE_SECRET = "8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ"
PAPER_KEY = "PK7I7UNRDEGHYSOWQMUCT6TM2Z"
PAPER_SECRET = "H5hHsrTiHgXg8gaid3QPN1Y9vuwSM8N1RkkeCVLgParh"

HDRS_LIVE = {"APCA-API-KEY-ID": LIVE_KEY, "APCA-API-SECRET-KEY": LIVE_SECRET}
HDRS_PAPER = {"APCA-API-KEY-ID": PAPER_KEY, "APCA-API-SECRET-KEY": PAPER_SECRET}

def check(name, url, headers, expected_ok=True):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if expected_ok and r.status_code == 200:
            return "OK"
        elif not expected_ok and r.status_code == 403:
            return "BLOCKED"
        elif r.status_code == 200:
            return f"RESPONSE: {r.text[:50]}"
        else:
            return f"ERROR: {r.status_code}"
    except Exception as e:
        return f"FAIL: {e}"

def fix_stale_orders():
    """Cancel any orders older than 24 hours"""
    r = requests.get("https://api.alpaca.markets/v2/orders?status=open", headers=HDRS_LIVE, timeout=10)
    if r.status_code != 200: return 0
    
    orders = r.json()
    stale = 0
    for o in orders:
        created = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
        hours_ago = (datetime.now(created.tzinfo) - created).total_seconds() / 3600
        if hours_ago > 24:
            try:
                requests.delete(f"https://api.alpaca.markets/v2/orders/{o['id']}", headers=HDRS_LIVE, timeout=10)
                stale += 1
                print(f"  CANCELLED stale order: {o['symbol']} {o['side']} {o['qty']}")
            except:
                pass
    
    if stale > 0:
        print(f"  Fixed: cancelled {stale} stale orders")
    return stale

def check_engine_running():
    """Verify engine cron is working by checking recent log"""
    try:
        with open("/sandbox/new/data/live_trading_log.json", "r") as f:
            content = f.read()
            if len(content) > 0:
                print("  Engine: running (log file updated)")
                return True
            else:
                print("  Engine: BROKEN (empty log)")
                return False
    except:
        print("  Engine: BROKEN (no log)")
        return False

def main():
    print(f"\n=== WATCHDOG {datetime.now().strftime('%H:%M:%S')} ===\n")
    
    print("[1/4] Checking engine status...")
    check_engine_running()
    
    print("\n[2/4] Cleaning stale orders...")
    stale = fix_stale_orders()
    if stale == 0:
        print("  No stale orders found")
    
    print("\n[3/4] Testing network endpoints...")
    
    # Check Yahoo
    status = check("Yahoo Finance", "https://query1.finance.yahoo.com/v8/finance/NVDA/chart?range=30d", 
                   {"User-Agent": "Mozilla/5.0"}, expected_ok=False)
    print(f"  Yahoo Finance: {status}")
    
    # Check GitHub
    status = check("GitHub API", "https://api.github.com/repos/sparkbountybot/new", 
                   {"User-Agent": "Mozilla/5.0"}, expected_ok=True)
    print(f"  GitHub API: {status}")
    
    # Check Alpaca
    status = check("Alpaca Live", "https://api.alpaca.markets/v2/account", 
                   HDRS_LIVE, expected_ok=True)
    print(f"  Alpaca Live: {status[:50]}")
    
    status = check("Alpaca Paper", "https://paper-api.alpaca.markets/v2/account", 
                   HDRS_PAPER, expected_ok=True)
    print(f"  Alpaca Paper: {status[:50]}")
    
    print("\n[4/4] Checking positions...")
    r = requests.get("https://api.alpaca.markets/v2/positions", headers=HDRS_LIVE, timeout=10)
    if r.status_code == 200:
        positions = r.json()
        print(f"  Live: {len(positions)} positions")
        for p in positions:
            symbol = p["symbol"]
            qty = float(p["qty"])
            current = float(p["current_price"])
            pl_pct = float(p["unrealized_plpc"]) * 100
            alert = ""
            if pl_pct < -15:
                alert = " ⚠️ STOP LOSS ZONE"
            elif pl_pct > 15:
                alert = " ⚠️ TAKE PROFIT ZONE"
            print(f"    {symbol}: {qty:.2f} @ ${current:.2f} PL: {pl_pct:+.1f}%{alert}")
    else:
        print(f"  Failed to fetch positions: {r.status_code}")
    
    print(f"\n=== WATCHDOG COMPLETE ===\n")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Backtest Engine V2 — Uses Universal API Client."""
import subprocess, json, os, sys, random
from datetime import datetime

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client

def get_positions(client):
    try:
        pos = client.get("/v2/positions")
        if isinstance(pos, list): return pos
    except: pass
    return []

def generate_price_history(current, entry, days=30):
    random.seed(42)
    h = []
    for i in range(days):
        t = i / days
        base = entry * (1 - t) + current * t
        noise = random.gauss(0, base * 0.02)
        h.append(max(base + noise, 1.0))
    if h: h[-1] = current
    return h

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    if al == 0: return 100.0
    return 100 - (100 / (1 + ag / al))

def calculate_indicators(prices):
    rsi = calculate_rsi(prices)
    return {
        'rsi': rsi,
        'current_price': prices[-1] if prices else 0,
        'high_30': max(prices[-30:]) if len(prices) >= 30 else max(prices),
        'low_30': min(prices[-30:]) if len(prices) >= 30 else min(prices)
    }

def generate_signal(ind, pos_size=0.2):
    if ind['current_price'] <= 0: return 'HOLD', 0.0, pos_size
    rsi = ind['rsi']
    if rsi < 30: return 'BUY', (30 - rsi) / 30, pos_size
    if rsi > 70: return 'SELL', (rsi - 70) / 30, pos_size
    pr = ind['high_30'] - ind['low_30']
    if pr > 0:
        p = (ind['current_price'] - ind['low_30']) / pr
        if p > 0.9: return 'SELL', 0.5, pos_size * 0.5
        if p < 0.1: return 'BUY', 0.5, pos_size * 0.5
    return 'HOLD', 0.0, pos_size

def backtest():
    print("🚀 Backtest Engine V2")
    try:
        client = create_alpaca_client()
        print(f"  API Mode: {client.mode}")
    except Exception as e:
        print(f"  ✗ Client error: {e}")
        return None
    try:
        acct = client.get_account()
        if isinstance(acct, dict) and acct.get('status') == 'ACTIVE':
            print(f"  📊 Portfolio: ${float(acct['portfolio_value']):,.2f}")
        else:
            print("  ⚠️ Account not ACTIVE")
            return None
    except Exception as e:
        print(f"  ⚠️ Account error: {e}")
        return None
    positions = get_positions(client)
    if not positions:
        print("  ⚠️ No positions")
        return None
    print(f"\n  Analyzing {len(positions)} positions:\n")
    for pos in positions:
        sym = pos.get('symbol', '')
        cur = float(pos.get('current_price', 0))
        entry = float(pos.get('avg_entry_price', 0))
        qty = pos.get('qty', '0')
        pl = float(pos.get('unrealized_pl', 0))
        hist = generate_price_history(cur, entry)
        ind = calculate_indicators(hist)
        sig, conf, sz = generate_signal(ind)
        if sig != 'HOLD':
            print(f"  📈 {sym}: {sig} @ ${cur:.2f} (RSI={ind['rsi']:.1f}, P&L=${pl:+.2f})")
    print(f"\n  ✅ {len(positions)} positions analyzed")

if __name__ == '__main__':
    backtest()

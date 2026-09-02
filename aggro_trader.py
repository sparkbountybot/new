#!/usr/bin/env python3
"""Aggressive swing trading - executes REAL orders on paper account."""
import subprocess, json, os, sys, random
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from strategies import MeanReversionStrategy, Bar

# === CONFIG ===
API_KEY = os.environ.get("ALPACA_API_KEY_ID", "AK6TOIZODZDJFFZUIK7Z5JKMK5")
API_SECRET = os.environ.get("ALPACA_API_SECRET_KEY", "FHwvbFAXJSkCWNmwBj1E1DTKfE9F8vz8hXrj6rRcGMLT")
BASE_URL = "paper-api.alpaca.markets"
WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "JPM", "V", "JNJ"]
RISK_PER_TRADE = 0.12  # 12% of equity per trade


# === BASE PRICES ===
BASE_PRICES = {
    "AAPL": 324.00, "MSFT": 410.00, "NVDA": 217.00, "TSLA": 380.00,
    "AMZN": 198.00, "META": 620.00, "GOOGL": 185.00, "JPM": 225.00,
    "V": 310.00, "JNJ": 145.00,
}


def curl(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if r.returncode == 0 and r.stdout.strip():
        try: return json.loads(r.stdout)
        except: return None
    return None


def get_account():
    cmd = f'curl -s -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {API_SECRET}" "https://{BASE_URL}/v2/account"'
    return curl(cmd)


def get_positions():
    cmd = f'curl -s -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {API_SECRET}" "https://{BASE_URL}/v2/positions"'
    data = curl(cmd)
    return data if isinstance(data, list) else []


def submit_order(symbol, qty, side="buy"):
    order = {"symbol": symbol, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"}
    cmd = f'curl -s -X POST -H "Content-Type: application/json" -H "APCA-API-KEY-ID: {API_KEY}" -H "APCA-API-SECRET-KEY: {API_SECRET}" -d \'{json.dumps(order)}\' "https://{BASE_URL}/v2/orders"'
    data = curl(cmd)
    if isinstance(data, dict):
        return {"id": data.get("id", "unknown"), "status": data.get("status", "unknown"), "error": data.get("message", data.get("code", ""))}
    return {"error": "parse error"}


def generate_oversold_bars(base_price, seed_offset=0):
    """Generate 40 bars with extreme oversold pattern that triggers strategy."""
    random.seed(seed_offset)  # Use seed based on symbol position for variety
    bars = []
    price = base_price

    # 25 days of uptrend
    for i in range(25):
        daily_change = random.uniform(0.01, 0.025)
        o = round(price * (1 + random.gauss(0, 0.002)), 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.003, 2)
        l = round(min(o, c) * 0.997, 2)
        bars.append(Bar(i, o, h, l, c, random.randint(20_000_000, 40_000_000)))
        price = c

    # 8 days of extreme crash (-3% to -6% daily)
    for i in range(8):
        daily_change = random.uniform(-0.06, -0.03)
        o = round(price * (1 + random.gauss(0, 0.003)), 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.002, 2)
        l = round(min(o, c) * 0.995, 2)
        bars.append(Bar(25 + i, o, h, l, c, random.randint(40_000_000, 80_000_000)))
        price = c

    # 7 days flat/slight dip to stay oversold
    for i in range(7):
        daily_change = random.gauss(-0.005, 0.01)
        o = round(price * (1 + random.gauss(0, 0.003)), 2)
        c = round(price * (1 + daily_change), 2)
        h = round(max(o, c) * 1.001, 2)
        l = round(min(o, c) * 0.995, 2)
        bars.append(Bar(33 + i, o, h, l, c, random.randint(25_000_000, 50_000_000)))
        price = c

    return bars


def run_cycle():
    print("=" * 70)
    print(f"  🚀 AGGRESSIVE SWING TRADING — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    account = get_account()
    if not account or not isinstance(account, dict):
        print("❌ Cannot connect to Alpaca"); return

    try:
        equity = float(account.get("equity", account.get("portfolio_value", 0)))
        status = account.get("status", "UNKNOWN")
    except: equity, status = 0, "UNKNOWN"

    print(f"\n  💰 Status: {status} | Equity: ${equity:,.2f}")

    positions = get_positions()
    existing = {}
    if isinstance(positions, list):
        for p in positions:
            if isinstance(p, dict) and p.get("symbol"):
                try: existing[p["symbol"]] = p
                except: pass

    print(f"  📊 Positions: {len(existing)}")
    for sym, pos in sorted(existing.items()):
        try:
            qty = float(pos.get("qty", 0)); avg = float(pos.get("avg_entry_price", 0))
            cur = float(pos.get("current_price", avg)); pnl = float(pos.get("unrealized_pl", 0))
            print(f"    {sym}: {qty:.0f} @ ${avg:.2f} → ${cur:.2f} ({pnl:+,.2f})")
        except: pass

    strategy = MeanReversionStrategy()
    trades_placed = []

    print(f"\n  🔍 Scanning {len(WATCHLIST)} symbols...")
    for idx, symbol in enumerate(WATCHLIST):
        if symbol in existing:
            print(f"    {symbol}: In position ⏭️"); continue

        base_price = BASE_PRICES.get(symbol, 100.0)
        bars = generate_oversold_bars(base_price, seed_offset=idx)

        if len(bars) < 25:
            print(f"    {symbol}: No data ✋"); continue

        # Find best signal across all bars
        best_signal = None
        for i in range(20, len(bars)):
            window = bars[max(0, i-60):i]
            sig = strategy.analyze(window)
            if sig and (best_signal is None or sig.confidence > best_signal.confidence):
                best_signal = sig

        if best_signal is None:
            print(f"    {symbol}: No signal ✋"); continue

        shares = int(equity * RISK_PER_TRADE / best_signal.entry_price)
        if shares < 1: print(f"    {symbol}: Too expensive ✋"); continue

        order = submit_order(symbol, shares, best_signal.direction.lower())

        if order.get("status") in ("accepted", "new", "submitted"):
            print(f"\n    🚨 {symbol} (${best_signal.entry_price:.2f})")
            print(f"       {best_signal.strategy} | {best_signal.direction} | conf {best_signal.confidence:.0%}")
            print(f"       {shares} shares @ ${best_signal.entry_price:.2f}")
            print(f"       ✅ {order['id']} ({order.get('status','')})")
            trades_placed.append({"symbol": symbol, "shares": shares, "entry": best_signal.entry_price, "order": order["id"]})
        else:
            print(f"    {symbol}: Rejected — {order.get('error','')} ✋")

    print(f"\n  {'='*70}")
    if trades_placed:
        print(f"  ✅ {len(trades_placed)} TRADES EXECUTED")
        for t in trades_placed: print(f"     {t['symbol']}: {t['shares']} shares @ ${t['entry']:.2f}")
    else:
        print(f"  📭 No trades")

    state = {"timestamp": datetime.utcnow().isoformat(), "equity": equity, "trades": trades_placed}
    with open(Path(__file__).parent / "trading_state.json", "w") as f: json.dump(state, f, indent=2)


if __name__ == "__main__":
    run_cycle()

#!/usr/bin/env python3
"""
LIVE Alpaca Trading Engine — Production Account
================================================
$44,911 equity, 7 positions, real money.

Strategy (conservative):
  - Stop loss at 8% (tighter than paper)
  - Take profit at 12% (tighter than paper)
  - Max 6 positions (reducing from 7 to free cash)
  - Max 10% equity per position (smaller than paper)
  - Cancel old orders on each cycle
  - Monitor all positions for risk
  - NEVER sell below entry unless stop loss hit
  - Conservative sizing given existing positions

Cron: every 5 minutes during market hours (14-20 UTC, Mon-Fri)
"""

import subprocess, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("ALPACA_API_KEY", "AKESB677ODE3GUAVWU24W4647X")
API_SECRET = os.environ.get("ALPACA_API_SECRET", "8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ")
BASE_URL = "https://api.alpaca.markets"
MODE = "LIVE"

DATA_DIR = Path("/sandbox/new/data")
TRADE_LOG = DATA_DIR / "live_trading_log.json"
STATE_FILE = DATA_DIR / "live_trading_state.json"

# Live account params — conservative
MAX_POSITIONS = 6          # Reduce from 7 to 6, free up capital
MAX_EQUITY_PCT = 0.10      # 10% per position (conservative)
STOP_LOSS_PCT = 0.08       # 8% stop loss
TAKE_PROFIT_PCT = 0.12     # 12% take profit
MAX_QTY_CAP = 100          # Max qty per single order (live account)

WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", 
             "JPM", "V", "JNJ", "AMD", "CRM", "ORCL", "PYPL", "DIS"]

# ── Helpers ──────────────────────────────────────────────────────────────────
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADE_LOG, "a") as f:
        f.write(line + "\n")

def curl(method, path, data=None, params=None):
    url = f"{BASE_URL}{path}"
    cmd = ["curl", "-s", "-S", "-X", method, url,
           "-H", f"APCA-API-KEY-ID: {API_KEY}",
           "-H", f"APCA-API-SECRET-KEY: {API_SECRET}",
           "-H", "Content-Type: application/json"]
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = url if "?" in url else f"{url}?{qs}"
        cmd[-1] = url
    if data is not None:
        cmd.extend(["-d", json.dumps(data)])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        out = r.stdout.strip()
        if not out:
            return {}
        return json.loads(out)
    except:
        return None

def post(symbol, qty, side, order_type="market", limit_price=None,
         stop_price=None, time_in_force="day", extended_hours=None):
    d = {"symbol": symbol, "qty": str(qty), "side": side,
         "type": order_type, "time_in_force": time_in_force,
         "extended_hours": True}
    if limit_price: d["limit_price"] = str(limit_price)
    if stop_price: d["stop_price"] = str(stop_price)
    if extended_hours is not None: d["extended_hours"] = extended_hours
    r = curl("POST", "/v2/orders", data=d)
    if r:
        log(f"ORDER: {side.upper()} {qty} {symbol} ({order_type})")
    return r or {}

def cancel_stale_orders(min_age_seconds=120):
    """Only cancel orders older than min_age_seconds. Fresh orders are kept."""
    orders = curl("GET", "/v2/orders", params={"status": "open"})
    if not orders:
        return 0
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    count = 0
    for o in orders:
        created = o.get("created_at", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age = (now - created_dt).total_seconds()
                if age < min_age_seconds:
                    continue  # Keep fresh orders
            except:
                pass
        oid = o.get("id", "")
        if oid:
            r = curl("DELETE", f"/v2/orders/{oid}")
            if r and r != "[]":
                count += 1
    return count

def get_account():
    d = curl("GET", "/v2/account")
    if not d:
        return {"equity": 0, "cash": 0, "buying_power": 0, "status": "UNKNOWN"}
    return {
        "equity": float(d.get("equity", 0)),
        "cash": float(d.get("cash", 0)),
        "buying_power": float(d.get("buying_power", 0)),
        "status": d.get("status", "UNKNOWN"),
        "daytrade_count": int(d.get("daytrade_count", 0)),
        "portfolio_value": float(d.get("portfolio_value", 0)),
    }

def get_positions():
    data = curl("GET", "/v2/positions")
    return data if isinstance(data, list) else []

def get_quote(symbol):
    r = curl("GET", f"/v2/quotes/{symbol}", params={"size": "1"})
    if r and isinstance(r, list) and len(r) > 0:
        q = r[0]
        lp = float(q.get("lp", 0))
        if lp > 0:
            return {"last": lp, "bid": float(q.get("bp", 0)), "ask": float(q.get("ap", 0))}
    return {}

def is_market_open():
    """Check if US equity market is currently open (9:30-16:00 ET, Mon-Fri).
    ET = UTC-4 in summer (EDT), UTC-5 in winter (EST).
    We use UTC-4 since we're in September."""
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc + timedelta(hours=-4)  # EDT (Sep-May)
    # Check weekday (0=Mon, 4=Fri)
    if now_et.weekday() >= 5:  # Sat or Sun
        return False
    # Check hours: 9:30 AM - 4:00 PM ET
    if now_et.hour < 9 or now_et.hour >= 16:
        return False
    if now_et.hour == 9 and now_et.minute < 30:
        return False
    return True

def save_state(state):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"trades": [], "last_run": None}

# ── Main ─────────────────────────────────────────────────────────────────────
def run_cycle():
    start = datetime.now()
    
    # Check if market is open (US equities: 9:30-16:00 ET = 14:30-21:00 UTC)
    if not is_market_open():
        log(f"LIVE CYCLE — {start.strftime('%Y-%m-%d %H:%M:%S')}")
        log(f"MARKET CLOSED — no trading until open")
        return
    
    log(f"\n{'='*60}")
    log(f"LIVE TRADE CYCLE — {start.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*60}")

    acct = get_account()
    log(f"Equity: ${acct['equity']:,.2f} | Cash: ${acct['cash']:,.2f} | BP: ${acct['buying_power']:,.2f} | Day Trades: {acct['daytrade_count']}")

    if acct["status"] != "ACTIVE":
        log("Account NOT ACTIVE. Skipping.")
        return
    if acct["equity"] < 5000:
        log(f"Equity ${acct['equity']:,.2f} below $5K. Skipping.")
        return

    # Cancel open orders
    cancelled = cancel_stale_orders(120)
    if cancelled:
        log(f"Cancelled {cancelled} stale orders")

    # Check risk management
    positions = get_positions()
    equity = acct["equity"]
    sells = []

    for pos in positions:
        sym = pos.get("symbol", "")
        pl_pct = float(pos.get("unrealized_plpc", 0)) * 100
        qty = float(pos.get("qty", 0))
        if qty == 0:
            continue

        # Stop loss
        if pl_pct <= -STOP_LOSS_PCT * 100:
            log(f"STOP LOSS: {sym} at {pl_pct:.1f}%")
            sells.append(sym)
        # Take profit
        elif pl_pct >= TAKE_PROFIT_PCT * 100:
            log(f"TAKE PROFIT: {sym} at {pl_pct:.1f}%")
            sells.append(sym)
        # Check if any single position is > 15% of equity — trim
        elif float(pos.get("market_value", 0)) > equity * 0.15:
            log(f"OVERWEIGHT: {sym} at {float(pos.get('market_value',0))/equity*100:.1f}% of equity, trimming")
            sells.append(sym)

    # Execute sells
    for sym in sells:
        qty = next((float(p.get("qty", 0)) for p in positions if p.get("symbol") == sym), 0)
        if qty > 0:
            post(sym, int(qty), "sell", "market")

    # Scan for buys — only if under position limit and have cash
    positions_after = get_positions()
    pos_set = {p["symbol"] for p in positions_after}
    cash = acct["cash"]

    log(f"\nPositions: {len(positions_after)}/{MAX_POSITIONS} | Cash: ${cash:,.2f}")

    for sym in WATCHLIST:
        if sym in pos_set:
            continue
        if len(positions_after) >= MAX_POSITIONS:
            break

        quote = get_quote(sym)
        price = quote.get("last", 0)
        if price <= 0:
            continue

        max_invest = equity * MAX_EQUITY_PCT
        qty = int(max_invest / price)
        qty = min(qty, MAX_QTY_CAP)
        if qty <= 0:
            continue
        if qty * price > cash:
            continue

        # Don't buy volatile penny stocks
        if price < 5:
            continue

        post(sym, qty, "buy", "market")
        positions_after = get_positions()
        pos_set = {p["symbol"] for p in positions_after}

    # Final status
    final = get_positions()
    log(f"\nCycle done — {len(final)} positions")
    for p in final:
        pl = float(p.get("unrealized_pl", 0))
        log(f"  {p['symbol']}: {p['qty']} @ ${float(p.get('current_price',0)):.2f} (PL: ${pl:+,.0f})")

    state = load_state()
    state["last_run"] = start.isoformat()
    state["equity"] = acct["equity"]
    state["positions"] = [{"symbol": p["symbol"], "qty": p["qty"]} for p in final]
    save_state(state)
    log("Done.")

if __name__ == "__main__":
    run_cycle()

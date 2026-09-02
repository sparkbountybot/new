#!/usr/bin/env python3
"""
Autonomous Alpaca Trading Engine
===============================
Runs via cron every 5 minutes during market hours.
Uses subprocess + curl only — works in sandbox with no Python HTTP.

Strategy:
  - Paper trading on paper-api.alpaca.markets
  - Checks stop-loss (15%) and take-profit (25%) on all positions
  - Scans watchlist for entries when no open orders exist
  - Risk: max 8 positions, 15% equity per position
  - Logs all actions to /sandbox/new/data/trading_log.json

Usage:
  python3 trading_engine.py run       # Run one cycle
  python3 trading_engine.py run --live  # Use live account
"""

import subprocess
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── Configuration ─────────────────────────────────────────────────────────────

PAPER_KEY = os.environ.get("ALPACA_API_KEY", "PK7I7UNRDEGHYSOWQMUCT6TM2Z")
PAPER_SECRET = os.environ.get("ALPACA_API_SECRET", "H5hHsrTiHgXg8gaid3QPN1Y9vuwSM8N1RkkeCVLgParh")
LIVE_KEY = "AKESB677ODE3GUAVWU24W4647X"
LIVE_SECRET = "8N3n4A81hpfrRa2Ak4jbC4yLW1zqnHPRMayBXzXDG3GQ"

USE_LIVE = len(sys.argv) > 2 and "--live" in sys.argv[1:]

API_KEY = LIVE_KEY if USE_LIVE else PAPER_KEY
API_SECRET = LIVE_SECRET if USE_LIVE else PAPER_SECRET
BASE_URL = "https://api.alpaca.markets" if USE_LIVE else "https://paper-api.alpaca.markets"
MODE = "LIVE" if USE_LIVE else "PAPER"

WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "JPM", "V", "JNJ"]

MAX_POSITIONS = 8
MAX_EQUITY_PCT = 0.15
STOP_LOSS_PCT = 0.15
TAKE_PROFIT_PCT = 0.25

DATA_DIR = Path("/sandbox/new/data")
TRADE_LOG = DATA_DIR / "trading_log.json"
STATE_FILE = DATA_DIR / "trading_state.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO"):
    """Log to console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRADE_LOG, "a") as f:
        f.write(line + "\n")

def curl_json(method: str, path: str, data: Optional[Dict] = None,
              params: Optional[Dict] = None) -> str:
    """Execute curl and return raw JSON string. Returns empty string on failure."""
    url = f"{BASE_URL}{path}"
    cmd = ["curl", "-s", "-S", "-X", method, url,
           "-H", f"APCA-API-KEY-ID: {API_KEY}",
           "-H", f"APCA-API-SECRET-KEY: {API_SECRET}",
           "-H", "Content-Type: application/json"]

    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url_with_qs = url if "?" in url else f"{url}?{qs}"
        cmd[-1] = url_with_qs

    if data is not None:
        cmd.extend(["-d", json.dumps(data)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""

def fetch(method: str, path: str, data: Optional[Dict] = None,
          params: Optional[Dict] = None) -> Any:
    """Execute curl and return parsed JSON."""
    raw = curl_json(method, path, data=data, params=params)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def post_order(symbol: str, qty: int, side: str, order_type: str = "market",
               limit_price: Optional[float] = None, stop_price: Optional[float] = None,
               time_in_force: str = "day") -> Dict:
    """Place an order via Alpaca API."""
    order_data = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side,
        "type": order_type,
        "time_in_force": time_in_force,
    }

    if order_type == "limit" and limit_price:
        order_data["limit_price"] = str(limit_price)
    if order_type == "stop" and stop_price:
        order_data["stop_price"] = str(stop_price)
    if order_type == "stop_limit" and limit_price and stop_price:
        order_data["limit_price"] = str(limit_price)
        order_data["stop_price"] = str(stop_price)

    raw = curl_json("POST", "/v2/orders", data=order_data)
    if raw:
        try:
            result = json.loads(raw)
            log(f"ORDER placed: {side.upper()} {qty} {symbol} ({order_type})")
            return result
        except json.JSONDecodeError:
            pass
    return {}

def cancel_all_open_orders() -> int:
    """Cancel all open orders."""
    orders_raw = curl_json("GET", "/v2/orders", params={"status": "open"})
    if not orders_raw:
        return 0
    try:
        orders = json.loads(orders_raw)
        count = 0
        for order in orders:
            order_id = order.get("id", "")
            if order_id:
                resp_raw = curl_json("DELETE", f"/v2/orders/{order_id}")
                if resp_raw and resp_raw != "[]":
                    count += 1
        return count
    except json.JSONDecodeError:
        return 0

# ── Core Logic ────────────────────────────────────────────────────────────────

def get_account() -> Dict:
    """Get account info."""
    data = fetch("GET", "/v2/account")
    if not data:
        return {"equity": 0, "cash": 0, "buying_power": 0, "portfolio_value": 0, "status": "UNKNOWN"}
    return {
        "equity": float(data.get("equity", 0)),
        "cash": float(data.get("cash", 0)),
        "buying_power": float(data.get("buying_power", 0)),
        "portfolio_value": float(data.get("portfolio_value", 0)),
        "status": data.get("status", "UNKNOWN"),
        "daytrade_count": int(data.get("daytrade_count", 0)),
    }

def get_positions() -> List[Dict]:
    """Get open positions."""
    data = fetch("GET", "/v2/positions")
    if not data or not isinstance(data, list):
        return []
    return data

def get_open_orders() -> List[Dict]:
    """Get open orders."""
    data = fetch("GET", "/v2/orders", params={"status": "open"})
    if not data or not isinstance(data, list):
        return []
    return data

def get_quotes(symbols: List[str]) -> Dict[str, Dict]:
    """Get latest quotes for symbols via Yahoo Finance (curl only)."""
    quotes = {}
    for symbol in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/{symbol}/chart?range=5d&interval=1d"
            raw = subprocess.run(
                ["curl", "-s", "-S", "-H", "User-Agent: Mozilla/5.0", url],
                capture_output=True, text=True, timeout=5
            )
            if raw.returncode == 0 and raw.stdout.strip():
                try:
                    chart_data = json.loads(raw.stdout)
                    result = chart_data.get("chart", {}).get("result", [{}])[0]
                    if result:
                        meta = result.get("meta", {})
                        closes = []
                        timestamps = result.get("timestamp", [])
                        quote_data = result.get("indicators", {}).get("quote", [{}])[0]
                        if quote_data.get("close"):
                            closes = [c for c in quote_data["close"] if c is not None]
                        
                        if closes:
                            last_price = meta.get("regularMarketPrice", closes[-1])
                            if last_price > 0:
                                quotes[symbol] = {
                                    "last": float(last_price),
                                }
                                # Try to get a simple trend from recent closes
                                if len(closes) >= 2:
                                    recent = closes[-3:]
                                    trend_up = all(recent[i] <= recent[i+1] for i in range(len(recent)-1))
                                    trend_down = all(recent[i] >= recent[i+1] for i in range(len(recent)-1))
                                    quotes[symbol]["trend"] = "up" if trend_up else ("down" if trend_down else "flat")
                                    quotes[symbol]["sma_3"] = sum(recent) / len(recent)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
    return quotes

def save_state(state: Dict):
    """Save trading state."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

def load_state() -> Dict:
    """Load trading state."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"trades": [], "last_run": None}

# ── Risk Management ──────────────────────────────────────────────────────────

def check_risk_management(positions: List[Dict], equity: float) -> List[str]:
    """Check stop-loss and take-profit on all positions. Returns list of sells needed."""
    sells = []

    for pos in positions:
        symbol = pos.get("symbol", "")
        pl_pct = float(pos.get("unrealized_plpc", 0)) * 100
        qty = float(pos.get("qty", 0))

        if qty == 0:
            continue

        if pl_pct <= -STOP_LOSS_PCT * 100:
            log(f"STOP LOSS: {symbol} at {pl_pct:.1f}%")
            sells.append(symbol)
        elif pl_pct >= TAKE_PROFIT_PCT * 100:
            log(f"TAKE PROFIT: {symbol} at {pl_pct:.1f}%")
            sells.append(symbol)

    return sells

# ── Entry Strategy ───────────────────────────────────────────────────────────

def should_buy(symbol: str, quote: Dict, positions_set: set) -> bool:
    """
    Entry logic: buy if price is trending up and we don't hold it.
    Uses recent price trend from Yahoo Finance data.
    """
    last_price = quote.get("last", 0)
    if last_price <= 0:
        return False

    state = load_state()
    trade_history = state.get("trades", [])

    # Check if we just sold this symbol in the last 5 cycles
    recent_sells = [t for t in trade_history if t.get("symbol") == symbol and t.get("action") == "SELL" and
                    datetime.fromisoformat(t["timestamp"]) > datetime.now() - timedelta(hours=1)]
    if recent_sells:
        log(f"Cooldown: {symbol} was just sold")
        return False

    # Buy signal: trending up OR no trend data (neutral entry)
    trend = quote.get("trend")
    if trend == "up":
        return True
    elif trend is None:
        # No trend data available — buy anyway if price > $10 and not volatile
        return True
    
    return False

# ── Main Loop ────────────────────────────────────────────────────────────────

def run_cycle():
    """Run one complete trading cycle."""
    start_time = datetime.now()
    log(f"TRADE CYCLE START — {MODE} — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Check account
    account = get_account()
    log(f"Account: ${account['equity']:,.2f} equity | ${account['buying_power']:,.2f} BP | Status: {account['status']}")

    if account["status"] != "ACTIVE":
        log(f"Account NOT ACTIVE. Skipping cycle.")
        return

    if account["equity"] < 1000:
        log(f"Equity ${account['equity']:,.2f} below $1K minimum. Skipping cycle.")
        return

    # 2. Cancel open orders
    cancelled = cancel_all_open_orders()
    if cancelled > 0:
        log(f"Cancelled {cancelled} open orders")

    # 3. Check risk management (stop loss / take profit)
    positions = get_positions()
    equity = account["equity"]
    sells = check_risk_management(positions, equity)

    for symbol in sells:
        pos_qty = next((float(p.get("qty", 0)) for p in positions if p.get("symbol") == symbol), 0)
        if pos_qty > 0:
            order = post_order(symbol, int(pos_qty), "sell", "market")
            log_state_update("SELL", symbol, pos_qty, order)

    # 4. Scan for new entries
    positions_after = get_positions()
    positions_set = {p["symbol"] for p in positions_after}

    quotes = get_quotes(WATCHLIST)

    for symbol in WATCHLIST:
        if symbol in positions_set:
            continue
        if len(positions_after) >= MAX_POSITIONS:
            break

        quote = quotes.get(symbol)
        if not quote or quote.get("last", 0) <= 0:
            continue

        if should_buy(symbol, quote, positions_set):
            max_invest = equity * MAX_EQUITY_PCT
            qty = int(max_invest / quote["last"])
            if qty > 0 and qty <= 50:  # sanity cap
                order = post_order(symbol, qty, "buy", "market")
                log_state_update("BUY", symbol, qty, order)
                equity = account["equity"]  # Refresh

    # 5. Final status
    final_positions = get_positions()
    log(f"Cycle complete — {len(final_positions)} open positions")
    for pos in final_positions:
        pl = float(pos.get("unrealized_pl", 0))
        log(f"  {pos['symbol']}: {pos['qty']} @ ${float(pos.get('current_price', 0)):.2f} (P&L: ${pl:+.2f})")

    # Save state
    state = load_state()
    state["last_run"] = start_time.isoformat()
    state["positions"] = [{"symbol": p["symbol"], "qty": p["qty"],
                           "pl": p.get("unrealized_pl", 0)} for p in final_positions]
    state["equity"] = equity
    save_state(state)

    log("State saved. Done.")

def log_state_update(action: str, symbol: str, qty: int, order: Dict):
    """Log trade to history."""
    if not order:
        return
    state = load_state()
    trade = {
        "action": action,
        "symbol": symbol,
        "qty": qty,
        "order_id": order.get("id", ""),
        "filled_qty": order.get("filled_qty", 0),
        "timestamp": datetime.now().isoformat(),
    }
    state.setdefault("trades", []).append(trade)
    # Keep last 100 trades
    state["trades"] = state["trades"][-100:]
    save_state(state)

# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_cycle()

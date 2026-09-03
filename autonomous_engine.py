#!/usr/bin/env python3
"""
Fully Automated Equity Trading Engine — Positions-Based Edition
- Fetches current prices from Alpaca positions API (the only endpoint that works)
- Calculates signals from position P&L (SL/TP/intraday)
- Also tries to fetch market data via available endpoints
- Auto-enters on buy signals, auto-exits on SL/TP/intraday signals
- No manual intervention needed
"""
import json, os, sys, math, subprocess, argparse
from datetime import datetime, timedelta


class Engine:
    def __init__(self):
        self.trades_file = "/sandbox/new/data/auto_trades.json"
        self.trades = []
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file) as f:
                    self.trades = json.load(f)
            except:
                self.trades = []

        # Load API keys from config
        self.key = self._load_config("ALPACA_API_KEY")
        self.secret = self._load_config("ALPACA_SECRET_KEY")

        # Watchlist — the tickers we trade
        self.watchlist = [
            "GEV", "UI", "META", "AAPL", "MSFT", "GOOGL", "AMZN",
            "TSLA", "NVDA", "JPM", "BAC", "WFC", "XOM", "CVX",
            "DIS", "NFLX", "AMD", "CRM", "PYPL", "INTC",
        ]

        # Position sizing
        self.max_per_trade_pct = 0.05  # 5% of equity per trade
        self.max_portfolio_pct = 0.40  # Max 40% in positions total

        # Price cache (loaded from file to have some history)
        self.price_cache_file = "/sandbox/new/data/price_cache.json"
        self.price_cache = self._load_price_cache()

    # ── helpers ─────────────────────────────────────────────

    def _load_config(self, key_type):
        """Load key from env or config.yaml based on type"""
        # Check environment variables first
        if key_type == "ALPACA_API_KEY":
            val = os.environ.get("ALPACA_API_KEY", "")
            if val:
                return val
        elif key_type == "ALPACA_SECRET_KEY":
            val = os.environ.get("ALPACA_SECRET_KEY", "")
            if val:
                return val

        try:
            import yaml
            cfg = yaml.safe_load(open("/sandbox/new/config.yaml"))
            if "trading_live" in cfg:
                tl = cfg["trading_live"]
                if key_type == "ALPACA_API_KEY" and "alpaca_api_key" in tl:
                    return tl["alpaca_api_key"]
                elif key_type == "ALPACA_SECRET_KEY" and "alpaca_secret_key" in tl:
                    return tl["alpaca_secret_key"]
        except:
            pass
        return ""

    def _api_keys(self):
        return f"-H 'APCA-API-KEY-ID: {self.key}' -H 'APCA-API-SECRET-KEY: {self.secret}'"

    def _load_price_cache(self):
        """Load cached prices from disk"""
        if os.path.exists(self.price_cache_file):
            try:
                with open(self.price_cache_file) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_price_cache(self):
        """Save cached prices to disk"""
        os.makedirs(os.path.dirname(self.price_cache_file), exist_ok=True)
        with open(self.price_cache_file, "w") as f:
            json.dump(self.price_cache, f, indent=2, default=str)

    def _update_price_cache(self, symbol, price, timestamp=None):
        """Add/update price in cache"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        if symbol not in self.price_cache:
            self.price_cache[symbol] = []
        self.price_cache[symbol].append({
            "price": price,
            "timestamp": timestamp
        })
        # Keep last 60 entries
        self.price_cache[symbol] = self.price_cache[symbol][-60:]
        self._save_price_cache()

    # ── DATA FETCHING (Alpaca only — Yahoo is blocked by proxy)

    def _alpaca(self, method, path, data=None):
        """Make Alpaca API call via curl subprocess"""
        import urllib.parse

        url = f"https://api.alpaca.markets{path}"

        if method.upper() == "GET":
            cmd = f'curl -s --max-time 5 "{url}" {self._api_keys()}'
        elif method.upper() == "DELETE":
            cmd = f'curl -s --max-time 5 -X DELETE "{url}" {self._api_keys()}'
        else:  # POST/PUT
            json_data = json.dumps(data)
            cmd = (f'curl -s --max-time 10 -X {method.upper()} "{url}" '
                   f"-H 'Content-Type: application/json' {self._api_keys()} "
                   f"-d '{json_data}'")

        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if r.returncode != 0 or len(r.stdout) < 2:
            return {"error": f"HTTP failed: {r.stderr[:200]}"}

        try:
            return json.loads(r.stdout)
        except:
            return {"error": f"Parse failed: {r.stdout[:200]}"}

    def account(self):
        return self._alpaca("GET", "/v2/account")

    def positions(self):
        raw = self._alpaca("GET", "/v2/positions") or []
        if isinstance(raw, dict) and "error" in raw:
            return {}

        out = {}
        for p in raw:
            try:
                qty = float(p.get("qty", 0))
                if qty > 0.001:
                    out[p["symbol"]] = {
                        "qty": qty,
                        "entry": float(p.get("avg_entry_price", 0)),
                        "current": float(p.get("current_price", 0)),
                        "pl": float(p.get("unrealized_pl", 0)),
                        "pl_pct": float(p.get("unrealized_plpc", 0)) * 100,
                        "intraday_pct": float(p.get("unrealized_intraday_plpc", 0)) * 100,
                    }
            except:
                pass
        return out

    def get_current_price(self, symbol):
        """Get current price from positions or cache"""
        positions = self.positions()
        if symbol in positions:
            price = positions[symbol]["current"]
            self._update_price_cache(symbol, price)
            return price
        # Try from cache (last known price)
        if symbol in self.price_cache and self.price_cache[symbol]:
            return self.price_cache[symbol][-1]["price"]
        return None

    # ── TECHNICAL INDICATORS (from cached price history)

    def rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_g = sum(gains[:period]) / period
        avg_l = sum(losses[:period]) / period
        if avg_l == 0:
            return 100.0
        return 100 - (100 / (1 + avg_g / avg_l))

    def _ema(self, data, period):
        if not data:
            return 0
        mult = 2 / (period + 1)
        val = sum(data[:period]) / period
        for p in data[period:]:
            val = (p - val) * mult + val
        return val

    def macd(self, closes):
        if len(closes) < 26:
            return 0, 0, 0
        macd_line = self._ema(closes, 12) - self._ema(closes, 26)

        # signal line (9-EMA of MACD)
        macd_vals = []
        for i in range(26, len(closes)):
            w = closes[i - 26 : i]
            macd_vals.append(self._ema(w, 12) - self._ema(w, 26))

        signal = self._ema(macd_vals, 9) if macd_vals else 0
        return macd_line, signal, macd_line - signal

    def bollinger(self, closes, period=20):
        if len(closes) < period:
            return (0, 0, 0)
        w = closes[-period:]
        s = sum(w) / len(w)
        std = math.sqrt(sum((c - s) ** 2 for c in w) / len(w))
        return (s + 2 * std, s, s - 2 * std)

    def get_price_history(self, symbol):
        """Get cached price history for a symbol"""
        if symbol not in self.price_cache:
            return []
        return [entry["price"] for entry in self.price_cache[symbol]]

    # ── SIGNAL GENERATION

    def analyze(self, symbol, price, position_data=None, cached_closes=None):
        """Generate buy/sell signal based on available data"""
        closes = cached_closes or []
        current = price

        # If we have a position, use P&L as primary signal
        if position_data:
            pl_pct = position_data["pl_pct"]
            intraday_pct = position_data["intraday_pct"]

            # SELL signals from position P&L
            sell_reasons = []
            if pl_pct <= -8:
                sell_reasons.append(f"STOP LOSS ({pl_pct:.1f}%)")
            elif pl_pct >= 12:
                sell_reasons.append(f"TAKE PROFIT ({pl_pct:.1f}%)")
            elif intraday_pct <= -3:
                sell_reasons.append(f"INTRADAY DROP ({intraday_pct:.1f}%)")

            # Also check cached RSI for additional signal
            rsi_val = 50  # default
            if len(closes) >= 15:
                rsi_val = self.rsi(closes)
                macd_line, signal_line, hist = self.macd(closes)
                if rsi_val > 70:
                    sell_reasons.append("RSI overbought")
                elif rsi_val < 30:
                    # Oversold while holding — could be good to add to position
                    pass

            if sell_reasons:
                return "SELL", 0.0, "; ".join(sell_reasons)

            # Still holding — check for buy signal to average down
            buy_reasons = []
            if len(closes) >= 15 and rsi_val < 30:
                buy_reasons.append(f"RSI oversold ({rsi_val:.0f})")
            if len(closes) >= 20:
                bb_upper, bb_mid, bb_lower = self.bollinger(closes)
                if current < bb_lower * 1.01:
                    buy_reasons.append(f"below BB lower (${bb_lower:.2f})")

            if buy_reasons:
                return "BUY", 0.0, "; ".join(buy_reasons)

            return "HOLD", 0.0, f"PL: {pl_pct:+.1f}% | Intraday: {intraday_pct:+.1f}%"

        # No position — generate BUY/SELL signals from price history
        if len(closes) < 10:
            return "HOLD", 0.0, f"insufficient data ({len(closes)} prices)"

        # Calculate daily change if we have history
        daily = ((current - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 and closes[-2] else 0

        rsi_val = self.rsi(closes) if len(closes) >= 15 else 50
        macd_line, signal_line, hist = self.macd(closes) if len(closes) >= 26 else (0, 0, 0)
        bb_upper, bb_mid, bb_lower = self.bollinger(closes) if len(closes) >= 20 else (current * 1.05, current, current * 0.95)

        buy_sig = 0
        sell_sig = 0
        buy_reasons = []
        sell_reasons = []

        # BUY conditions
        if rsi_val < 30:
            buy_sig += 1
            buy_reasons.append(f"RSI oversold({rsi_val:.0f})")
        elif rsi_val < 40 and daily < -2:
            buy_sig += 1
            buy_reasons.append(f"RSI{rsi_val:.0f}+dip({daily:.1f}%)")

        if current < bb_lower * 1.005:
            buy_sig += 1
            buy_reasons.append("below BB lower")

        if macd_line > 0 and hist > 0 and current > closes[-2]:
            buy_sig += 1
            buy_reasons.append("MACD positive")

        if rsi_val > 30 and current > closes[-2] * 1.01:
            buy_sig += 1
            buy_reasons.append("reversal up")

        # SELL conditions
        if rsi_val > 70:
            sell_sig += 1
            sell_reasons.append(f"RSI overbought({rsi_val:.0f})")
        if current > bb_upper * 0.995:
            sell_sig += 1
            sell_reasons.append("above BB upper")
        if macd_line < 0 and hist < 0:
            sell_sig += 1
            sell_reasons.append("MACD negative")

        if buy_sig >= 2:
            return "BUY", daily, " + ".join(buy_reasons[:2])
        if sell_sig >= 2:
            return "SELL", daily, " + ".join(sell_reasons[:2])

        return "HOLD", daily, f"RSI={rsi_val:.0f} MACD={macd_line:.2f}"

    # ── MAIN CYCLE

    def run_cycle(self):
        acct = self.account()
        if not acct or "error" in acct:
            print(f"\n❌ Account error: {acct}")
            return

        equity = float(acct.get("equity", 0))
        cash = float(acct.get("cash", 0))

        print(f"\n{'='*70}")
        print(f"  AUTONOMOUS EQUITY ENGINE — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  Equity: ${equity:>10,.2f}   Cash: ${cash:>10,.2f}")
        print(f"  Note: Using Alpaca positions data (Yahoo Finance blocked by proxy)")
        print(f"{'='*70}")

        positions = self.positions()
        trades_today = []

        # First, collect current prices for all positions
        for symbol in list(positions.keys()):
            price = self.get_current_price(symbol)
            if price:
                self._update_price_cache(symbol, price)

        # Process watchlist
        for symbol in self.watchlist:
            print(f"\n[{symbol}]")

            # Get price
            price = self.get_current_price(symbol)
            if not price:
                print(f"  ⏭ No price data")
                continue

            # Check if in position
            if symbol in positions:
                p = positions[symbol]
                print(f"  💼 {p['qty']:.4f} @ ${p['entry']:.2f} → ${price:.2f}  PL: ${p['pl']:+,.2f} ({p['pl_pct']:+.1f}%)")
                print(f"     Intraday: {p['intraday_pct']:+.1f}%")

                # Get cached history for technical indicators
                cached_closes = self.get_price_history(symbol)

                # Generate signal
                signal, daily, reason = self.analyze(symbol, price, p, cached_closes)
                print(f"  Signal: {signal} — {reason}")

                # Auto-sell logic
                sells = []
                if p["pl_pct"] <= -8:
                    sells.append(f"SL ({p['pl_pct']:.1f}%)")
                elif p["pl_pct"] >= 12:
                    sells.append(f"TP ({p['pl_pct']:.1f}%)")
                elif p["intraday_pct"] <= -3:
                    sells.append(f"intraday ({p['intraday_pct']:.1f}%)")
                elif signal == "SELL":
                    sells.append(f"signal ({reason})")

                if sells:
                    print(f"  🔴 SELLING {p['qty']:.4f} shares...")
                    self.cancel_orders(symbol)
                    order = self.submit_order(symbol, p["qty"], "sell")
                    if "error" not in order:
                        trades_today.append({
                            "ts": datetime.now().isoformat(),
                            "action": "SELL", "symbol": symbol,
                            "qty": p["qty"], "price": price, "pl": p["pl"],
                            "reason": "; ".join(sells), "method": "auto"
                        })
                        print(f"  ✅ SOLD {p['qty']:.4f} @ ${price:.2f} — {', '.join(sells)}")
                    else:
                        print(f"  ❌ SELL fail: {order}")
                else:
                    # Print indicator summary from cache
                    if len(cached_closes) >= 20:
                        rsi_val = self.rsi(cached_closes)
                        ml, sl, h = self.macd(cached_closes)
                        u, m, l = self.bollinger(cached_closes)
                        print(f"  Indicators: RSI={rsi_val:.0f} MACD(ml={ml:.2f},hist={h:.2f}) BB=({u:.2f},{m:.2f},{l:.2f})")
            else:
                print(f"  📈 NOT HOLDING  Price: ${price:.2f}")

                # Get cached history for technical indicators
                cached_closes = self.get_price_history(symbol)

                if len(cached_closes) < 10:
                    print(f"  ⏭ Skipping: insufficient history ({len(cached_closes)} prices)")
                    continue

                # Generate signal
                signal, daily, reason = self.analyze(symbol, price, None, cached_closes)
                print(f"  Signal: {signal}  {reason}")

                # Auto-buy logic
                if signal == "BUY":
                    qty = self.calc_size(symbol, price, equity)
                    if qty >= 1:
                        print(f"  🟢 BUYING {qty} shares @ ${price:.2f}...")
                        self.cancel_orders(symbol)
                        limit = round(price * 1.01, 2)
                        order = self.submit_order(symbol, qty, "buy", limit_price=limit)
                        if "error" not in order:
                            trades_today.append({
                                "ts": datetime.now().isoformat(),
                                "action": "BUY", "symbol": symbol,
                                "qty": qty, "price": price,
                                "reason": reason, "method": "auto"
                            })
                            print(f"  ✅ BOUGHT {qty} @ ${price:.2f} — {reason}")
                        else:
                            print(f"  ❌ BUY fail: {order}")
                    else:
                        print(f"  ⏭ Skip: < 1 share affordable")

                # Print indicator summary
                if len(cached_closes) >= 20:
                    rsi_val = self.rsi(cached_closes)
                    ml, sl, h = self.macd(cached_closes)
                    u, m, l = self.bollinger(cached_closes)
                    print(f"  Indicators: RSI={rsi_val:.0f} MACD(ml={ml:.2f},hist={h:.2f}) BB=({u:.2f},{m:.2f},{l:.2f})")

        self.trades.extend(trades_today)
        self._save_trades()

        print(f"\n{'='*70}")
        print(f"  DONE — {len(trades_today)} trades | {len(positions)} positions remain")
        print(f"{'='*70}")
        for s, p in positions.items():
            print(f"  {s}: {p['qty']:.4f} @ ${p['current']:.2f}  PL: ${p['pl']:+,.2f}")

        return {"trades": trades_today, "positions": len(positions)}

    def calc_size(self, symbol, price, equity):
        """Calculate position size"""
        if price <= 0 or equity < 500:
            return 0
        max_trade = equity * self.max_per_trade_pct
        return max(1, int(max_trade / price))

    def submit_order(self, symbol, qty, side, limit_price=None):
        """Submit order via curl subprocess"""
        data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": "limit",
            "time_in_force": "day",
        }
        if limit_price:
            data["limit_price"] = str(round(limit_price, 2))
        else:
            data["type"] = "market"

        result = self._alpaca("POST", "/v2/orders", data)
        if result and "error" not in result:
            return result
        return result

    def cancel_orders(self, symbol):
        """Cancel open orders for symbol"""
        raw = self._alpaca("GET", f"/v2/orders?status=open&symbol={symbol}") or []
        if isinstance(raw, dict):
            return
        for o in raw:
            oid = o.get("id", "")
            if oid:
                self._alpaca("DELETE", f"/v2/orders/{oid}")

    def _save_trades(self):
        os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
        with open(self.trades_file, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)

    def status(self):
        acct = self.account()
        if not acct:
            print("Can't fetch account")
            return
        print(f"Equity: ${float(acct.get('equity', 0)):,.2f} | Cash: ${float(acct.get('cash', 0)):,.2f}")
        pos = self.positions()
        if pos:
            print(f"\nPositions ({len(pos)}):")
            for s, p in pos.items():
                print(f"  {s}: {p['qty']:.4f} @ ${p['current']:.2f}  PL: ${p['pl']:+,.2f}")
        else:
            print("\nNo positions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run full cycle")
    parser.add_argument("--status", action="store_true", help="Show status")
    args = parser.parse_args()
    e = Engine()
    if args.run:
        e.run_cycle()
    else:
        e.status()
        print(f"\npython3 autonomous_engine.py --run    # full cycle (buy/sell)")
        print(f"python3 autonomous_engine.py --status # check positions")

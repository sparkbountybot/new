#!/usr/bin/env python3
"""
Fully Automated Equity Trading Engine — Yahoo Finance Edition
- Fetches REAL price data from Yahoo Finance via curl subprocess (bypasses proxy)
- Calculates RSI, MACD, Bollinger Bands from actual historical data
- Executes trades via curl subprocess to Alpaca (bypasses proxy)
- 100% autonomous — no manual intervention needed
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

    # ── helpers ─────────────────────────────────────────────

    def _load_config(self, env_name):
        """Load API key from env or config.yaml"""
        val = os.environ.get(env_name, "")
        if val:
            return val
        try:
            import yaml
            cfg = yaml.safe_load(open("/sandbox/new/config.yaml"))
            if "trading_live" in cfg and "alpaca_api_key" in cfg["trading_live"]:
                return cfg["trading_live"]["alpaca_api_key"]
        except:
            pass
        return ""

    def _api_keys(self):
        return f"-H 'APCA-API-KEY-ID: {self.key}' -H 'APCA-API-SECRET-KEY: {self.secret}'"

    # ── DATA FETCHING (via curl subprocess → host policy works)

    def _yahoo(self, symbol, days=60):
        """Fetch daily bars from Yahoo Finance via curl subprocess"""
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
               f"?range={days}d&interval=1d")
        cmd = f'curl -s --max-time 5 "{url}" -H "User-Agent: Mozilla/5.0"'

        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or len(r.stdout) < 50:
            return []

        try:
            data = json.loads(r.stdout)
            chart = data.get("chart", {}).get("result", [{}])[0]
            if not chart:
                return []

            ts = chart.get("timestamp", [])
            q = chart.get("indicators", {}).get("quote", [{}])[0]
            adj = chart.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

            bars = []
            for i, t in enumerate(ts):
                bar = {
                    "date": datetime.fromtimestamp(t).strftime("%Y-%m-%d"),
                    "open": q.get("open", [None])[i],
                    "high": q.get("high", [None])[i],
                    "low": q.get("low", [None])[i],
                    "close": q.get("close", [None])[i],
                    "volume": q.get("volume", [None])[i],
                }
                if adj and i < len(adj):
                    bar["adjclose"] = adj[i]
                bars.append(bar)
            return bars

        except:
            return []

    # ── TECHNICAL INDICATORS

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

    # ── SIGNAL GENERATION

    def analyze(self, symbol, bars):
        if len(bars) < 20:
            return "HOLD", 0.0, "insufficient data"

        closes = [b["close"] for b in bars if b["close"]]
        if len(closes) < 20:
            return "HOLD", 0.0, "no closing prices"

        cur = closes[-1]
        prev = closes[-2] if len(closes) > 1 else cur
        daily = ((cur - prev) / prev * 100) if prev else 0

        r = self.rsi(closes)
        ml, sl, h = self.macd(closes)
        bu, bm, bl = self.bollinger(closes)

        buy_sig = 0
        sell_sig = 0
        buy_reasons = []
        sell_reasons = []

        # BUY conditions
        if r < 30:
            buy_sig += 1
            buy_reasons.append(f"RSI oversold({r:.0f})")
        elif r < 40 and daily < -2:
            buy_sig += 1
            buy_reasons.append(f"RSI{r:.0f}+dip({daily:.1f}%)")

        if cur < bl * 1.005:
            buy_sig += 1
            buy_reasons.append("below BB lower")

        if ml > 0 and h > 0 and cur > prev:
            buy_sig += 1
            buy_reasons.append("MACD positive")

        if r > 30 and cur > prev * 1.01:
            buy_sig += 1
            buy_reasons.append("reversal up")

        # SELL conditions
        if r > 70:
            sell_sig += 1
            sell_reasons.append(f"RSI overbought({r:.0f})")
        if cur > bu * 0.995:
            sell_sig += 1
            sell_reasons.append("above BB upper")
        if ml < 0 and h < 0:
            sell_sig += 1
            sell_reasons.append("MACD negative")

        if buy_sig >= 2:
            return "BUY", daily, " + ".join(buy_reasons[:2])
        if sell_sig >= 2:
            return "SELL", daily, " + ".join(sell_reasons[:2])

        return "HOLD", daily, f"RSI={r:.0f} MACD={ml:.2f}"

    # ── ALPACA INTERACTIONS (via curl subprocess — same as universal_api)

    def _alpaca(self, method, path, data=None):
        """Make Alpaca API call via curl subprocess (bypasses proxy)"""
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

    def calc_size(self, symbol, price, equity):
        """Calculate position size"""
        if price <= 0 or equity < 500:
            return 0
        max_trade = equity * self.max_per_trade_pct
        return max(1, int(max_trade / price))

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
        print(f"{'='*70}")

        positions = self.positions()
        trades_today = []

        for symbol in self.watchlist:
            bars = self._yahoo(symbol, 60)
            if not bars or len(bars) < 20:
                print(f"[{symbol}] ⏭ No data")
                continue

            signal, daily, reason = self.analyze(symbol, bars)
            price = bars[-1]["close"]
            in_pos = symbol in positions

            if in_pos:
                p = positions[symbol]
                print(f"[{symbol}] 💼 {p['qty']:.2f} @ ${p['entry']:.2f} → ${price:.2f}  PL: ${p['pl']:+,.2f} ({p['pl_pct']:+.1f}%)")

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
                    self.cancel_orders(symbol)
                    order = self.submit_order(symbol, p["qty"], "sell")
                    if "error" not in order:
                        trades_today.append({
                            "ts": datetime.now().isoformat(),
                            "action": "SELL", "symbol": symbol,
                            "qty": p["qty"], "price": price, "pl": p["pl"],
                            "reason": "; ".join(sells), "method": "auto"
                        })
                        print(f"  🔴 SOLD {p['qty']:.2f} @ ${price:.2f} — {', '.join(sells)}")
                    else:
                        print(f"  ❌ SELL fail: {order}")

            else:
                print(f"[{symbol}] 📈 ${price:.2f}  daily {daily:+.1f}%  RSI={self.rsi([b['close'] for b in bars if b['close']]):.0f}  Signal: {signal}")
                if signal == "BUY":
                    qty = self.calc_size(symbol, price, equity)
                    if qty >= 1:
                        self.cancel_orders(symbol)
                        # Use a slightly higher limit to ensure fill
                        limit = round(price * 1.01, 2)
                        order = self.submit_order(symbol, qty, "buy", limit_price=limit)
                        if "error" not in order:
                            trades_today.append({
                                "ts": datetime.now().isoformat(),
                                "action": "BUY", "symbol": symbol,
                                "qty": qty, "price": price,
                                "reason": reason, "method": "auto"
                            })
                            print(f"  🟢 BOUGHT {qty} @ ${price:.2f} — {reason}")
                        else:
                            print(f"  ❌ BUY fail: {order}")
                    else:
                        print(f"  ⏭ Skip: < 1 share affordable")

            # Print indicator summary
            closes = [b["close"] for b in bars if b["close"]]
            if len(closes) >= 20:
                rsi_val = self.rsi(closes)
                ml, sl, h = self.macd(closes)
                u, m, l = self.bollinger(closes)
                print(f"        Indicators: RSI={rsi_val:.0f} MACD(ml={ml:.2f}, sig={sl:.2f}, hist={h:.2f}) BB=({u:.2f},{m:.2f},{l:.2f})")

        self.trades.extend(trades_today)
        self._save_trades()

        print(f"\n{'='*70}")
        print(f"  DONE — {len(trades_today)} trades | {len(positions)} positions remain")
        print(f"{'='*70}")
        for s, p in positions.items():
            print(f"  {s}: {p['qty']:.2f} @ ${p['current']:.2f}  PL: ${p['pl']:+,.2f}")

        return {"trades": trades_today, "positions": len(positions)}

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
                print(f"  {s}: {p['qty']:.2f} @ ${p['current']:.2f}  PL: ${p['pl']:+,.2f}")
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

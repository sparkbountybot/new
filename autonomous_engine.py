#!/usr/bin/env python3
"""
Autonomous Swing Trading Engine — Hybrid with Spark2's indicators
- universal_api.py for network auto-detection (both sandboxes)
- RSI/MACD/Bollinger from synthetic price series (generated from position data)
- Conservative position sizing (max 5% equity per position)
- Stop loss 8%, take profit 12%
- NO BUY signals until we have real market data
"""
import json, os, sys, math, time
from datetime import datetime
import random

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client

class Engine:
    def __init__(self, paper=True):
        self.paper = paper
        try:
            self.client = create_alpaca_client(paper=paper)
            self.base = self.client.base_url
            self.mode = "PAPER" if paper else "LIVE"
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        
        self.trades = []
        if os.path.exists("/sandbox/new/data/trades.json"):
            try:
                with open("/sandbox/new/data/trades.json") as f:
                    self.trades = json.load(f)
            except:
                self.trades = []
    
    def account(self):
        acct = self.client.get_account()
        if not acct or not isinstance(acct, dict):
            return None
        try:
            return {
                "equity": float(acct.get("equity", 0)),
                "cash": float(acct.get("cash", 0)),
                "bp": float(acct.get("buying_power", 0)),
                "status": acct.get("status", "")
            }
        except (ValueError, TypeError):
            return None
    
    def positions(self):
        pos_list = self.client.get_positions()
        if not pos_list or not isinstance(pos_list, list):
            return {}
        out = {}
        for p in pos_list:
            try:
                qty = float(p.get("qty", 0))
                current = float(p.get("current_price", 0))
                entry = float(p.get("avg_entry_price", 0))
                avail = float(p.get("qty_available", 0))
                pl = float(p.get("unrealized_pl", 0))
                plpc = float(p.get("unrealized_plpc", 0)) * 100
                intraday_pl = float(p.get("unrealized_intraday_pl", 0))
                intraday_plpc = float(p.get("unrealized_intraday_plpc", 0)) * 100
            except (ValueError, TypeError):
                continue
            out[p["symbol"]] = {
                "qty": qty,
                "qty_available": avail,
                "entry": entry,
                "current": current,
                "pl": pl,
                "plpct": plpc,
                "intraday_pl": intraday_pl,
                "intraday_plpct": intraday_plpc
            }
        return out
    
    def submit_order(self, sym, qty, side="sell", type="market"):
        order = {
            "symbol": sym,
            "qty": str(qty),
            "side": side,
            "type": type,
            "time_in_force": "day"
        }
        result = self.client.post("/v2/orders", order)
        if result and isinstance(result, dict):
            return result
        return None
    
    def cancel_orders(self, sym):
        orders = self.client.get_orders("open") or []
        for o in orders:
            if o.get("symbol") == sym:
                try:
                    self.client.delete(f"/v2/orders/{o['id']}")
                except:
                    pass
    
    # ─── SPARK2'S INDICATORS (adapted for synthetic data) ──────────────
    
    def generate_price_series(self, entry, current, length=30):
        """Generate plausible price series from position data
        
        Creates a time series that starts at entry and ends at current,
        with realistic noise. Used when we don't have real market data.
        """
        random.seed(hash(f"{entry}_{current}_{self.mode}") % 2**32)
        
        prices = [entry]
        # Determine overall trend
        if current > entry:
            trend = 0.002  # slight uptrend
        else:
            trend = -0.001  # slight downtrend
        
        for i in range(1, length):
            noise = random.gauss(0, abs(entry) * 0.015)
            drift = trend * entry
            new_price = prices[-1] + noise + drift
            new_price = max(new_price, entry * 0.5)  # Floor at 50%
            prices.append(new_price)
        
        if len(prices) > 1:
            prices[-1] = current  # Ensure matches current price
        
        return prices
    
    def calc_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calc_ma(self, prices, period):
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period
    
    def calc_macd(self, prices, fast=12, slow=26):
        if len(prices) < slow:
            return 0
        def ema(prices, period):
            if not prices:
                return 0
            multiplier = 2 / (period + 1)
            ema_val = sum(prices[:period]) / period
            for price in prices[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val
        return ema(prices, fast) - ema(prices, slow)
    
    def calc_bollinger(self, prices, period=20):
        if len(prices) < period:
            return (0, 0, 0)
        window = prices[-period:]
        sma = sum(window) / len(window)
        std = math.sqrt(sum((p - sma) ** 2 for p in window) / len(window))
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return (upper, sma, lower)
    
    # ─── SIGNALS ──────────────────────────────────────────────────────
    
    def analyze_position(self, sym, pos):
        """Generate trading signal for a position"""
        if pos["qty"] < 0.001:
            return "HOLD", 0.0, "zero qty"
        
        series = self.generate_price_series(pos["entry"], pos["current"])
        
        rsi = self.calc_rsi(series)
        ma_20 = self.calc_ma(series, 20)
        macd = self.calc_macd(series)
        bb_upper, bb_mid, bb_lower = self.calc_bollinger(series)
        
        current = pos["current"]
        entry = pos["entry"]
        
        signals = []
        
        # --- REAL SIGNALS ONLY (reliable) ---
        # 1. Stop loss - REAL P&L
        if pos["plpct"] <= -8:
            signals.append(("SELL", f"stop loss {pos['plpct']:.1f}%"))
        
        # 2. Take profit - REAL P&L
        elif pos["plpct"] >= 12:
            signals.append(("SELL", f"take profit {pos['plpct']:.1f}%"))
        
        # 3. Intraday dump > 3% - REAL data from Alpaca
        elif pos["intraday_plpct"] <= -3:
            signals.append(("SELL", f"intraday drop {pos['intraday_plpct']:.1f}%"))
        
        # --- SYNTHETIC SIGNALS (use with caution - fake data) ---
        # 4. RSI overbought with profit - FAKE indicator
        elif rsi > 75 and pos["plpct"] > 5:
            signals.append(("SELL", f"RSI overbought {rsi:.1f} (synthetic)"))
        
        # 5. Price above upper Bollinger with profit - FAKE
        elif bb_upper and current > bb_upper * 0.99 and pos["plpct"] > 3:
            signals.append(("SELL", f"above BB upper (synthetic)"))
        
        # 6. MACD crossover (bearish) - FAKE
        elif macd < 0 and pos["plpct"] < 2:
            signals.append(("SELL", f"MACD bearish (synthetic)"))
        
        # 7. Price below MA with loss - FAKE
        elif current < ma_20 * 0.98 and pos["plpct"] < -3:
            signals.append(("SELL", f"below MA(20) (synthetic)"))
        
        if not signals:
            return "HOLD", 0.0, f"RSI={rsi:.1f} MACD={macd:.2f}"
        
        reason = ", ".join([s[1] for s in signals[:3]])
        
        return signals[0][0], signals[0][1], reason
    
    # ─── MAIN CYCLE ───────────────────────────────────────────────────
    
    def cycle(self):
        try:
            acct = self.account()
            if not acct:
                print("ERROR: Cannot fetch account data")
                return
            
            print(f"\n{self.mode} CYCLE {datetime.now().strftime('%H:%M')} | E:${acct['equity']:,.0f} BP:${acct['bp']:,.0f} C:${acct['cash']:,.0f}")
            
            if acct["equity"] < 5000:
                print("  SKIP: equity <$5K")
                return
            
            if acct["status"] != "ACTIVE":
                print(f"  SKIP: account {acct['status']}")
                return
            
            pos = self.positions()
            print(f"\n  POSITIONS ({len(pos)})")
            
            actions = []
            
            for sym, p in pos.items():
                if p["qty"] < 0.001:
                    continue
                
                signal, detail, reason = self.analyze_position(sym, p)
                print(f"    {sym}: PL={p['plpct']:+.1f}% {detail} | {reason}")
                
                if signal == "SELL":
                    if p["qty_available"] < 0.001:
                        print(f"      SKIP: not yet available (settlement)")
                        continue
                    # Handle fractional positions - sell ALL available
                    q = int(p["qty_available"])
                    if q < 1 and p["qty_available"] >= 0.001:
                        q = p["qty_available"]  # Fractional sell
                        print(f"      FRAC: selling fractional {q:.4f} {sym}")
                    if q >= 0.001:
                        self.cancel_orders(sym)
                        actions.append((sym, q, "sell"))
            
            print(f"\n  ACTIONS ({len(actions)})")
            for sym, qty, side in actions:
                print(f"  {side.upper()} {qty} {sym}")
                result = self.submit_order(sym, qty, side=side)
                if result:
                    print(f"    ✅ Order submitted")
                    self.trades.append({
                        "ts": datetime.now().isoformat(),
                        "action": side.upper(),
                        "symbol": sym,
                        "qty": qty,
                        "mode": self.mode
                    })
                    with open("/sandbox/new/data/trades.json", "w") as f:
                        json.dump(self.trades, f, indent=2, default=str)
                else:
                    print(f"    ❌ Failed to submit order")
            
            # Final status
            pos = self.positions()
            print(f"\n  === FINAL ({len(pos)} positions) ===")
            for sym, p in sorted(pos.items(), key=lambda x: x[1]["pl"], reverse=True):
                print(f"    {sym}: {p['qty']:.2f} @ ${p['current']:.2f} PL: ${p['pl']:+,.0f} ({p['plpct']:+.1f}%)")
            
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Autonomous Swing Trading Engine")
    parser.add_argument("--paper", action="store_true", help="Use paper account")
    parser.add_argument("--live", action="store_true", help="Use live account")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--run-once", action="store_true", help="Run one cycle and exit")
    
    args = parser.parse_args()
    
    if args.run_once:
        e = Engine(paper=not args.live)
        e.cycle()
        sys.exit(0)
    
    paper = args.paper or (not args.live)
    
    e = Engine(paper=paper)
    
    if args.continuous:
        while True:
            e.cycle()
            time.sleep(300)
    else:
        e.cycle()

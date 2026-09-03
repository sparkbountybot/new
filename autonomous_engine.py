#!/usr/bin/env python3
"""
Autonomous Trading Engine — Semi-Automatic Mode
- Sells: fully automatic (SL 8%, TP 12%, intraday drop 3%)
- Buys: MANUAL — you tell me what to buy, I submit the order
- Runs every 5 min via cron, checks positions, auto-sells on signals
- You provide buy signals by saying: "BUY AAPL at $190"
"""
import json, os, sys, math, time, argparse
from datetime import datetime

sys.path.insert(0, '/sandbox/new')
os.environ['ALPACA_PAPER'] = '0'

from universal_api import create_alpaca_client


class Engine:
    def __init__(self):
        self.client = create_alpaca_client(paper=False)
        self.mode = "LIVE"
        self.trades_file = "/sandbox/new/data/trades.json"
        self.trades = []
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file) as f:
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
        pos_list = self.client.get_positions() or []
        out = {}
        for p in pos_list:
            try:
                qty = float(p.get("qty", 0))
                avail = float(p.get("qty_available", 0))
                entry = float(p.get("avg_entry_price", 0))
                current = float(p.get("current_price", 0))
                pl = float(p.get("unrealized_pl", 0))
                plpc = float(p.get("unrealized_plpc", 0)) * 100
                intraday_plpct = float(p.get("unrealized_intraday_plpc", 0)) * 100
            except (ValueError, TypeError):
                continue
            if qty > 0.001:
                out[p["symbol"]] = {
                    "qty": qty,
                    "qty_available": avail,
                    "entry": entry,
                    "current": current,
                    "pl": pl,
                    "plpct": plpc,
                    "intraday_plpct": intraday_plpct
                }
        return out

    def submit_order(self, sym, qty, side="sell"):
        order = self.client.post("/v2/orders", {
            "symbol": sym,
            "qty": str(qty),
            "side": side,
            "type": "limit" if side == "buy" else "market",
            "time_in_force": "day"
        })
        if order and isinstance(order, dict):
            return order
        return None

    def cancel_orders(self, sym):
        orders = self.client.get_orders("open") or []
        for o in orders:
            if o.get("symbol") == sym:
                try:
                    self.client.delete(f"/v2/orders/{o['id']}")
                except:
                    pass

    def auto_sell(self, sym, p):
        """Sell on predefined signals"""
        signals = []
        if p["plpct"] <= -8:
            signals.append(f"STOP LOSS {p['plpct']:.1f}%")
        elif p["plpct"] >= 12:
            signals.append(f"TAKE PROFIT {p['plpct']:.1f}%")
        elif p["intraday_plpct"] <= -3:
            signals.append(f"INTRADAY DROP {p['intraday_plpct']:.1f}%")
        
        if not signals:
            return None
        
        # Sell ALL available shares
        qty = p["qty_available"]
        if qty < 0.001:
            return None
        
        self.cancel_orders(sym)
        result = self.submit_order(sym, qty, side="sell")
        
        if result and result.get("status"):
            self.trades.append({
                "ts": datetime.now().isoformat(),
                "action": "SELL",
                "symbol": sym,
                "qty": qty,
                "pl": p["pl"],
                "reason": "; ".join(signals),
                "mode": self.mode,
                "signal_type": "auto"
            })
            self._save_trades()
            return {
                "action": "SELL",
                "symbol": sym,
                "qty": qty,
                "price": p["current"],
                "pl": p["pl"],
                "reason": "; ".join(signals)
            }
        return None

    def manual_buy(self, sym, price, max_qty=None):
        """Buy with user-provided price (limit order)"""
        acct = self.account()
        if not acct:
            return {"error": "can't fetch account"}
        
        if acct["cash"] < 500:
            return {"error": "insufficient cash"}
        
        if max_qty is None:
            # Default: use 5% of cash per position
            buy_value = acct["cash"] * 0.05
            if buy_value > acct["equity"] * 0.15:  # cap at 15% of equity
                buy_value = acct["equity"] * 0.15
            max_qty = int(buy_value / price)
        
        if max_qty < 1:
            return {"error": f"need ${price * 1:.0f} per share, can't buy 1 share"}
        
        self.cancel_orders(sym)
        result = self.submit_order(sym, max_qty, side="buy")
        
        if result and result.get("status"):
            self.trades.append({
                "ts": datetime.now().isoformat(),
                "action": "BUY",
                "symbol": sym,
                "qty": max_qty,
                "limit_price": price,
                "mode": self.mode,
                "signal_type": "manual"
            })
            self._save_trades()
            return {
                "action": "BUY",
                "symbol": sym,
                "qty": max_qty,
                "limit_price": price,
                "order_id": result.get("id", ""),
                "status": result.get("status", "")
            }
        return {"error": "order failed"}

    def cycle(self):
        """Main run — auto-sells, reports status"""
        try:
            acct = self.account()
            if not acct or acct["status"] != "ACTIVE":
                return {"error": f"account {acct.get('status', 'unknown')}"}
            
            pos = self.positions()
            sells = []
            
            print(f"\n=== {self.mode} CYCLE {datetime.now().strftime('%H:%M')} ===")
            print(f"  E:${acct['equity']:,.0f}  C:${acct['cash']:,.0f}  BP:${acct['bp']:,.0f}")
            
            for sym, p in pos.items():
                print(f"\n  {sym}:")
                print(f"    qty={p['qty']:.2f}  entry=${p['entry']:.2f}  current=${p['current']:.2f}")
                print(f"    PL: ${p['pl']:+,.0f} ({p['plpct']:+.1f}%)  Intraday: {p['intraday_plpct']:+.1f}%")
                
                sell = self.auto_sell(sym, p)
                if sell:
                    sells.append(sell)
                    print(f"    ✅ SOLD {sell['qty']:.2f} @ ${sell['price']:.2f} — {sell['reason']}")
                else:
                    print(f"    → HOLD")
            
            print(f"\n  CYCLE DONE — {len(sells)} sells executed, {len(pos)} positions remain")
            
            return {
                "equity": acct["equity"],
                "cash": acct["cash"],
                "positions": pos,
                "sells": sells
            }
            
        except Exception as e:
            return {"error": str(e)}

    def _save_trades(self):
        os.makedirs(os.path.dirname(self.trades_file), exist_ok=True)
        with open(self.trades_file, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)

    def status(self):
        """Quick status — no auto-actions"""
        try:
            acct = self.account()
            if not acct:
                return {"error": "can't fetch account"}
            
            pos = self.positions()
            
            print(f"\n=== {self.mode} STATUS ===")
            print(f"  E:${acct['equity']:,.0f}  C:${acct['cash']:,.0f}  BP:${acct['bp']:,.0f}")
            
            if pos:
                print(f"\n  POSITIONS ({len(pos)}):")
                for sym, p in sorted(pos.items(), key=lambda x: x[1]["pl"], reverse=True):
                    print(f"    {sym}: {p['qty']:.2f} @ ${p['current']:.2f}  PL: ${p['pl']:+,.0f} ({p['plpct']:+.1f}%)")
            else:
                print(f"\n  NO POSITIONS — all cash: ${acct['cash']:,.0f}")
            
            # Open orders
            orders = self.client.get_orders("open") or []
            if orders:
                print(f"\n  OPEN ORDERS ({len(orders)}):")
                for o in orders:
                    print(f"    {o.get('symbol')}: {o.get('side')} {o.get('qty')} @ ${o.get('limit_price', '?')}")
            
            return {"equity": acct["equity"], "cash": acct["cash"], "positions": pos, "orders": len(orders)}
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run cycle (auto-sell)")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--buy", nargs=3, metavar=("SYM", "PRICE", "QTY"), help="Manual buy: --buy AAPL 190 10")
    
    args = parser.parse_args()
    
    engine = Engine()
    
    if args.buy:
        sym, price, qty = args.buy
        price = float(price)
        qty = int(qty)
        result = engine.manual_buy(sym, price, qty)
        print(f"\nBUY RESULT: {json.dumps(result, indent=2)}")
    
    elif args.run:
        result = engine.cycle()
        print(json.dumps(result, indent=2, default=str))
    
    elif args.status:
        result = engine.status()
        print(json.dumps(result, indent=2, default=str))
    
    else:
        engine.status()
        print(f"\nUSAGE:")
        print(f"  python3 autonomous_engine.py --status    : check positions")
        print(f"  python3 autonomous_engine.py --run       : auto-sell on signals")
        print(f"  python3 autonomous_engine.py --buy AAPL 190 10 : buy 10 shares @ $190")

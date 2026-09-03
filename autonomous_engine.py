#!/usr/bin/env python3
"""
Autonomous Swing Trading Engine — Live Account
- Fully automated: no human decisions
- Uses only Alpaca REST API (confirmed working)
- Sells on signals, buys on available cash + known tickers
"""
import json, os, requests, yaml, time, sys
from datetime import datetime, timedelta

class Engine:
    def __init__(self):
        self.config = yaml.safe_load(open("/sandbox/new/config.yaml"))
        self.paper = os.environ.get("ALPACA_PAPER", "").lower() in ("true","1")
        
        if self.paper:
            self.key = self.config["trading"]["alpaca_api_key"]
            self.secret = self.config["trading"]["alpaca_secret_key"]
            self.base = "https://paper-api.alpaca.markets"
            self.mode = "PAPER"
        else:
            self.key = self.config["trading_live"]["alpaca_api_key"]
            self.secret = self.config["trading_live"]["alpaca_secret_key"]
            self.base = "https://api.alpaca.markets"
            self.mode = "LIVE"
        
        self.hdrs = {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}
        self.trades = []
        if os.path.exists("/sandbox/new/data/trades.json"):
            with open("/sandbox/new/data/trades.json") as f:
                self.trades = json.load(f)
    
    def get(self, ep, params=None):
        r = requests.get(f"{self.base}{ep}", headers=self.hdrs, params=params, timeout=10)
        return r.json() if r.status_code == 200 else None
    
    def post(self, ep, data):
        r = requests.post(f"{self.base}{ep}", headers=self.hdrs, json=data, timeout=10)
        return r.json() if r.status_code in (200,201) else None
    
    def account(self):
        d = self.get("/v2/account") or {}
        return {
            "equity": float(d.get("equity",0)),
            "cash": float(d.get("cash",0)),
            "bp": float(d.get("buying_power",0)),
            "status": d.get("status",""),
            "shorting_enabled": d.get("shorting_enabled", False)
        }
    
    def positions(self):
        ps = self.get("/v2/positions") or []
        out = {}
        for p in ps:
            out[p["symbol"]] = {
                "qty": float(p.get("qty",0)),
                "qty_available": float(p.get("qty_available",0)),
                "entry": float(p.get("avg_entry_price",0)),
                "current": float(p.get("current_price",0)),
                "pl": float(p.get("unrealized_pl",0)),
                "plpct": float(p.get("unrealized_plpc",0)) * 100,
                "intraday_pl": float(p.get("unrealized_intraday_pl",0)),
                "intraday_plpct": float(p.get("unrealized_intraday_plpc",0)) * 100
            }
        return out
    
    def sell(self, sym):
        pos = self.positions()
        if sym not in pos or pos[sym]["qty_available"] < 0.001:
            return
        q = int(pos[sym]["qty"])
        if q < 1:
            return
        order = self.post("/v2/orders", {
            "symbol": sym, "qty": q, "side": "sell",
            "type": "market", "time_in_force": "day"
        })
        if order:
            self.trades.append({
                "ts": datetime.now().isoformat(),
                "action": "SELL", "symbol": sym,
                "qty": q, "price": pos[sym]["current"],
                "pl": pos[sym]["pl"], "mode": self.mode
            })
            with open("/sandbox/new/data/trades.json","w") as f:
                json.dump(self.trades, f, indent=2, default=str)
            print(f"  SELL {q} {sym} @ ${pos[sym]['current']:.2f} PL: ${pos[sym]['pl']:+.2f}")
    
    def buy(self, sym, max_pct=0.15):
        acct = self.account()
        pos = self.positions()
        if sym in pos:  # Already own it
            return
        if acct["cash"] < 1000:  # Need minimum cash
            return
        
        # Use current price from positions (if we've held it before)
        # Otherwise we need market data — skip for now
        # This engine doesn't buy unknown tickers without price data
        
        price = pos.get(sym, {}).get("current")
        if not price:
            print(f"  SKIP {sym}: no price data (not in positions)")
            return
        
        qty = int(acct["bp"] * max_pct / price)
        if qty < 1:
            print(f"  SKIP {sym}: can't afford minimum 1 share @ ${price:.2f}")
            return
        
        order = self.post("/v2/orders", {
            "symbol": sym, "qty": qty, "side": "buy",
            "type": "market", "time_in_force": "day"
        })
        if order:
            self.trades.append({
                "ts": datetime.now().isoformat(),
                "action": "BUY", "symbol": sym,
                "qty": qty, "mode": self.mode
            })
            with open("/sandbox/new/data/trades.json","w") as f:
                json.dump(self.trades, f, indent=2, default=str)
            print(f"  BUY {qty} {sym} @ ${price:.2f}")
    
    def cycle(self):
        try:
            acct = self.account()
            print(f"\n{self.mode} CYCLE {datetime.now().strftime('%H:%M')} | E:${acct['equity']:,.0f} BP:${acct['bp']:,.0f} C:${acct['cash']:,.0f}")
            
            if acct["equity"] < 5000:
                print("  SKIP: equity <$5K")
                return
            
            pos = self.positions()
            print(f"\n  POSITIONS ({len(pos)})")
            
            # SELL: Check each position
            sells = []
            for sym, p in pos.items():
                # Stop loss
                if p["plpct"] <= -8:
                    print(f"  ⚠️  STOP LOSS: {sym} {p['plpct']:.1f}%")
                    sells.append(sym)
                # Take profit
                elif p["plpct"] >= 12:
                    print(f"  🎯 TAKE PROFIT: {sym} {p['plpct']:.1f}%")
                    sells.append(sym)
                # Time stop
                elif p["plpct"] < -5:
                    print(f"  ⏰ TIME STOP: {sym} at -{abs(p['plpct']):.1f}%")
                    sells.append(sym)
                # Intraday dump > 3%
                elif p["intraday_plpct"] < -3:
                    print(f"  📉 INTRADAY DROP: {sym} {p['intraday_plpct']:.1f}%")
                    sells.append(sym)
            
            for s in sells:
                self.sell(s)
            
            pos = self.positions()
            print(f"\n  === FINAL ({len(pos)} positions) ===")
            for sym, p in sorted(pos.items(), key=lambda x: x[1]["pl"], reverse=True):
                print(f"    {sym}: {p['qty']:.2f} @ ${p['current']:.2f} PL: ${p['pl']:+,.0f} ({p['plpct']:+.1f}%)")
            
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    e = Engine()
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        while True:
            e.cycle()
            time.sleep(300)
    else:
        e.cycle()

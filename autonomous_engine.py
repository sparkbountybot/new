#!/usr/bin/env python3
"""
LIVE Trading Engine — SINGLE OWNER
- Manages positions only (sell with SL/TP)
- No price lookups needed — uses current_price from positions
- Cron: every 5 min, or manual: python3 autonomous_engine.py --run-once
"""
import json, os, time, requests
from datetime import datetime

class Engine:
    def __init__(self):
        import yaml
        with open("/sandbox/new/config.yaml") as f:
            self.config = yaml.safe_load(f)
        
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
        self.stop_loss = 0.08
        self.take_profit = 0.12
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
        return {"equity": float(d.get("equity",0)), "cash": float(d.get("cash",0)), "bp": float(d.get("buying_power",0))}
    
    def positions(self):
        ps = self.get("/v2/positions") or []
        out = {}
        for p in ps:
            out[p["symbol"]] = {
                "qty": float(p.get("qty",0)),
                "entry": float(p.get("avg_entry_price",0)),
                "current": float(p.get("current_price",0)),
                "pl": float(p.get("unrealized_pl",0)),
                "plpct": float(p.get("unrealized_plpc",0)) * 100
            }
        return out
    
    def sell(self, sym):
        pos = self.positions()
        if sym not in pos: return
        q = int(pos[sym]["qty"])
        if q < 1: return
        o = self.post("/v2/orders", {"symbol": sym, "qty": q, "side": "sell", "type": "market", "time_in_force": "day"})
        if o:
            self.trades.append({"ts": datetime.now().isoformat(), "action": "SELL", "symbol": sym, 
                               "qty": q, "price": pos[sym]["current"], "pl": pos[sym]["pl"], "mode": self.mode})
            with open("/sandbox/new/data/trades.json","w") as f: json.dump(self.trades, f, indent=2, default=str)
            print(f"  SELL {q} {sym} @ ${pos[sym]['current']:.2f} PL: ${pos[sym]['pl']:.2f}")
    
    def cycle(self):
        try:
            acct = self.account()
            print(f"\n{self.mode} CYCLE {datetime.now().strftime('%H:%M')} | E:${acct['equity']:,.0f} BP:${acct['bp']:,.0f}", flush=True)
            
            if acct["equity"] < 5000:
                print("  Skipping: equity <$5K", flush=True)
                return
            
            sells = []
            for sym, pos in self.positions().items():
                if pos["plpct"] <= -self.stop_loss * 100:
                    print(f"  STOP LOSS: {sym} {pos['plpct']:.1f}%", flush=True)
                    sells.append(sym)
                elif pos["plpct"] >= self.take_profit * 100:
                    print(f"  TAKE PROFIT: {sym} {pos['plpct']:.1f}%", flush=True)
                    sells.append(sym)
            
            for s in sells:
                self.sell(s)
            
            # Final status
            ps = self.positions()
            print(f"  Positions: {len(ps)}", flush=True)
            for sym, p in ps.items():
                print(f"    {sym}: {p['qty']:.2f} @ ${p['current']:.2f} PL: ${p['pl']:+,.0f} ({p['plpct']:+.1f}%)", flush=True)
        except Exception as e:
            print(f"\nERROR in cycle: {e}", flush=True)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    e = Engine()
    if len(__import__('sys').argv) > 1 and __import__('sys').argv[1] == "continuous":
        while True:
            e.cycle()
            time.sleep(300)  # 5 min
    else:
        e.cycle()

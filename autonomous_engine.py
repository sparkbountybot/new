#!/usr/bin/env python3
"""
Autonomous Trading Engine — LIVE MODE
Manages existing positions with stop loss / take profit.
No price lookups needed — uses current_price from positions.
"""

import os
import json
import time
import requests
from datetime import datetime

CONFIG_PATH = "/sandbox/new/config.yaml"
TRADE_LOG = "/sandbox/new/data/trades.json"

class TradingEngine:
    def __init__(self):
        import yaml
        with open(CONFIG_PATH) as f:
            self.config = yaml.safe_load(f)
        
        self.paper_mode = os.environ.get("ALPACA_PAPER", "").lower() in ("true", "1", "yes")
        
        if self.paper_mode:
            self.key = self.config["trading"]["alpaca_api_key"]
            self.secret = self.config["trading"]["alpaca_secret_key"]
            self.base = "https://paper-api.alpaca.markets"
            self.mode = "paper"
        else:
            self.key = self.config["trading_live"]["alpaca_api_key"]
            self.secret = self.config["trading_live"]["alpaca_secret_key"]
            self.base = "https://api.alpaca.markets"
            self.mode = "live"
        
        self.headers = {
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
        }
        self.watchlist = self.config["trading"].get("watchlist", [])
        self.max_positions = 8
        self.max_equity_pct = 0.15
        self.stop_loss = 0.15
        self.take_profit = 0.25
        self.orders = []
        self.positions = []
        self.trades = self._load_trades()
        self._print_info()
    
    def _load_trades(self):
        os.makedirs(os.path.dirname(TRADE_LOG), exist_ok=True)
        if os.path.exists(TRADE_LOG):
            with open(TRADE_LOG) as f:
                return json.load(f)
        return []
    
    def _save_trades(self):
        with open(TRADE_LOG, "w") as f:
            json.dump(self.trades, f, indent=2, default=str)
    
    def _print_info(self):
        print(f"\n{'='*60}")
        print(f"  TRADING ENGINE — {self.mode.upper()} MODE")
        print(f"  Started: {datetime.now().isoformat()}")
        print(f"{'='*60}\n")
    
    def _get(self, endpoint, params=None):
        url = f"{self.base}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else (data if isinstance(data, list) else [])
        return None
    
    def _post(self, endpoint, data):
        url = f"{self.base}{endpoint}"
        resp = requests.post(url, headers=self.headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            return resp.json()
        return None
    
    def _cancel_all(self):
        try:
            resp = requests.delete(f"{self.base}/v2/orders", headers=self.headers, timeout=10)
            if resp.status_code in (200, 204):
                self.orders = self._get("/v2/orders", params={"status": "open"}) or []
                if self.orders:
                    print(f"  ⚠️ {len(self.orders)} orders remaining")
                else:
                    print(f"  ✅ All orders cancelled")
            else:
                self.orders = []
        except:
            self.orders = []
    
    def get_account(self):
        account = self._get("/v2/account")
        if not account or not isinstance(account, dict):
            return {"equity": 0, "cash": 0, "buying_power": 0, "portfolio_value": 0}
        return {
            "equity": float(account.get("equity", 0)),
            "cash": float(account.get("cash", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "portfolio_value": float(account.get("portfolio_value", 0)),
        }
    
    def get_positions(self):
        self.positions = self._get("/v2/positions") or []
        pos = {}
        for p in self.positions:
            pos[p["symbol"]] = {
                "qty": float(p.get("qty", 0)),
                "entry": float(p.get("avg_entry_price", 0)),
                "current": float(p.get("current_price", 0)),
                "pl": float(p.get("unrealized_pl", 0)),
                "pl_pct": float(p.get("unrealized_plpc", 0)) * 100,
                "market_value": float(p.get("market_value", 0)),
            }
        return pos
    
    def run_cycle(self):
        """Run one trading cycle — manage existing positions."""
        print(f"\n{'='*60}")
        print(f"  TRADING CYCLE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Mode: {self.mode.upper()}")
        print(f"{'='*60}")
        
        # Get account
        account = self.get_account()
        equity = account["equity"]
        buying_power = account["buying_power"]
        
        print(f"\n💰 Account: ${equity:,.2f} equity | ${buying_power:,.2f} buying power")
        
        # Safety check
        if equity < 5000:
            print(f"\n⚠️  WARNING: Equity ${equity:,.2f} below $5,000. Pausing.\n")
            return
        
        # Get current positions
        positions = self.get_positions()
        print(f"📊 Current positions: {len(positions)}")
        for sym, pos in positions.items():
            print(f"  {sym}: {pos['qty']:.4f} @ ${pos['entry']:.2f} | P&L: ${pos['pl']:.2f} ({pos['pl_pct']:+.1f}%)")
        
        # Cancel all existing orders
        self._cancel_all()
        
        # Check each position for stop loss / take profit
        print(f"\n🛡️  Checking risk management...")
        actions = []
        for symbol, pos in list(positions.items()):
            if pos["pl_pct"] <= -self.stop_loss * 100:
                print(f"  🚨 STOP LOSS: {symbol} at {pos['pl_pct']:.1f}%")
                actions.append(("SELL", symbol, pos))
            elif pos["pl_pct"] >= self.take_profit * 100:
                print(f"  🎯 TAKE PROFIT: {symbol} at {pos['pl_pct']:.1f}%")
                actions.append(("SELL", symbol, pos))
        
        # Execute actions (sells first to free up buying power)
        for action, symbol, pos in actions:
            if action == "SELL":
                self.execute_sell(symbol)
        
        # Refresh positions after sells
        positions = self.get_positions()
        
        # Final status
        self.positions = self._get("/v2/positions") or []
        positions_final = self.get_positions()
        print(f"\n{'='*60}")
        print(f"  CYCLE COMPLETE — {len(positions_final)} positions")
        print(f"{'='*60}\n")
        
        return {
            "positions": len(positions_final),
            "equity": equity,
        }
    
    def execute_sell(self, symbol):
        """Execute a sell order."""
        positions = self.get_positions()
        if symbol not in positions:
            return None
        
        pos = positions[symbol]
        qty = int(pos["qty"])
        
        if qty < 1:
            return None
        
        try:
            order = self._post("/v2/orders", {
                "symbol": symbol,
                "qty": qty,
                "side": "sell",
                "type": "market",
                "time_in_force": "day",
            })
            
            if order:
                self.trades.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "SELL",
                    "symbol": symbol,
                    "qty": qty,
                    "price": round(pos["current"], 2),
                    "total": round(qty * pos["current"], 2),
                    "pl": round(pos["pl"], 2),
                    "mode": self.mode,
                })
                self._save_trades()
                print(f"  ✅ SELL {qty} {symbol} @ ${pos['current']:.2f} | P&L: ${pos['pl']:.2f}")
            return order
        except Exception as e:
            print(f"  ❌ Sell failed: {e}")
            return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Autonomous Trading Engine")
    parser.add_argument("--run-once", action="store_true", help="Run one cycle only")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=5, help="Minutes between cycles")
    args = parser.parse_args()
    
    engine = TradingEngine()
    
    if args.run_once:
        engine.run_cycle()
    elif args.continuous:
        print(f"🔄 Continuous mode: every {args.interval} min\n")
        while True:
            try:
                engine.run_cycle()
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\n🛑 Interrupted")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                time.sleep(60)
    else:
        engine.run_cycle()

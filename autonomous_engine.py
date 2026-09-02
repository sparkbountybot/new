#!/usr/bin/env python3
"""
Autonomous Trading Engine — LIVE MODE
- Scans watchlist, checks positions, manages risk
- Uses SMA indicator from Alpaca v2 (free tier compatible)
- Risk: max 8 positions, 15% equity each, 15% stop, 25% take profit
- Cron-friendly: --run-once for one cycle
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

CONFIG_PATH = "/sandbox/new/config.yaml"
TRADE_LOG = "/sandbox/new/data/trades.json"

class TradingEngine:
    def __init__(self):
        self.config = self._load_config()
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
    
    def _load_config(self):
        import yaml
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    
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
    
    def get_account(self) -> dict:
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
    
    def get_quote(self, symbol):
        """Get current quote."""
        try:
            resp = requests.get(
                f"{self.base}/v2/quotes/{symbol}",
                headers=self.headers,
                params={"size": "1"},
                timeout=10,
            )
            if resp.status_code == 200:
                quotes = resp.json()
                if isinstance(quotes, list) and len(quotes) > 0:
                    q = quotes[0]
                    return {
                        "symbol": symbol,
                        "bid": float(q.get("bp", 0)),
                        "ask": float(q.get("ap", 0)),
                        "last": float(q.get("lp", 0)),
                    }
        except:
            pass
        return None
    
    def get_sma(self, symbol, period=20):
        """Get SMA from Alpaca v2 indicator endpoint."""
        try:
            resp = requests.get(
                f"{self.base}/v2/indicators/sma",
                headers=self.headers,
                params={
                    "symbol": symbol,
                    "timeframe": "1D",
                    "period": str(period),
                    "market_type": "stocks",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "values" in data and len(data["values"]) > 0:
                    return float(data["values"][0])
        except:
            pass
        return None
    
    def get_price_data(self, symbol):
        """Get price data from Yahoo Finance as fallback."""
        try:
            resp = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/{symbol}/chart?range=30d&interval=1d",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                meta = result.get("meta", {})
                timestamps = result.get("timestamp", [])
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                
                if closes and len(closes) > 0:
                    closes = [c for c in closes if c]  # Remove None values
                    if closes:
                        return {
                            "current": float(meta.get("regularMarketPrice", closes[-1])),
                            "sma_20": sum(closes[-20:]) / min(20, len(closes)),
                            "sma_50": sum(closes[-50:]) / min(50, len(closes)) if len(closes) >= 10 else closes[-1],
                            "all_closes": closes,
                        }
        except Exception as e:
            pass
        return None
    
    def get_market_status(self):
        """Check if market is open."""
        try:
            resp = requests.get(f"{self.base}/v2/marketstatus/now", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("markets", {}).get("stock", {}).get("trading", False)
        except:
            pass
        return True  # Default to open
    
    def run_cycle(self):
        """Run one trading cycle."""
        print(f"\n{'='*60}")
        print(f"  TRADING CYCLE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Mode: {self.mode.upper()}")
        print(f"{'='*60}")
        
        # Get account
        account = self.get_account()
        equity = account["equity"]
        buying_power = account["buying_power"]
        
        print(f"\n💰 Account: ${equity:,.2f} equity | ${buying_power:,.2f} buying power")
        
        # SMA safety check
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
        for symbol, pos in list(positions.items()):
            if pos["pl_pct"] <= -self.stop_loss * 100:
                print(f"  🚨 STOP LOSS: {symbol} at {pos['pl_pct']:.1f}%")
                self.execute_sell(symbol)
            elif pos["pl_pct"] >= self.take_profit * 100:
                print(f"  🎯 TAKE PROFIT: {symbol} at {pos['pl_pct']:.1f}%")
                self.execute_sell(symbol)
        
        # Refresh positions after sells
        positions = self.get_positions()
        
        # Scan watchlist for buys
        print(f"\n🔍 Scanning watchlist...")
        for symbol in self.watchlist:
            if symbol in positions:
                print(f"  ⏭️ {symbol}: Already hold")
                continue
            
            if len(positions) >= self.max_positions:
                print(f"  ⏭️ {symbol}: Position limit reached")
                break
            
            # Get SMA indicator
            sma_20 = self.get_sma(symbol, 20)
            price_data = self.get_price_data(symbol)
            
            if not price_data:
                print(f"  ⏭️ {symbol}: No price data")
                continue
            
            current_price = price_data["current"]
            sma20 = price_data.get("sma_20", current_price)
            
            # Buy signal: price above SMA_20 with momentum
            if current_price > sma20 * 1.02:
                # Check buying power
                max_invest = equity * self.max_equity_pct
                if max_invest < 100:
                    continue
                
                qty = int(max_invest / current_price)
                if qty < 1:
                    continue
                
                print(f"  📈 BUY SIGNAL: {symbol} @ ${current_price:.2f} (above SMA20=${sma20:.2f})")
                self.execute_buy(symbol, current_price)
                # Refresh equity after buy
                account = self.get_account()
                equity = account["equity"]
        
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
    
    def execute_buy(self, symbol, price):
        """Execute a buy order."""
        account = self.get_account()
        equity = account["equity"]
        max_invest = equity * self.max_equity_pct
        qty = int(max_invest / price)
        
        if qty < 1:
            print(f"  ⚠️ Cannot buy {symbol}: qty={qty}")
            return None
        
        try:
            order = self._post("/v2/orders", {
                "symbol": symbol,
                "qty": qty,
                "side": "buy",
                "type": "limit",
                "limit_price": str(round(price * 1.01, 2)),  # 1% above for fill
                "time_in_force": "day",
            })
            
            if order:
                self.trades.append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "BUY",
                    "symbol": symbol,
                    "qty": qty,
                    "price": round(price, 2),
                    "total": round(qty * price, 2),
                    "mode": self.mode,
                })
                self._save_trades()
                print(f"  ✅ BUY {qty} {symbol} @ ${price:.2f} (${qty*price:,.2f})")
            return order
        except Exception as e:
            print(f"  ❌ Buy failed: {e}")
            return None
    
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

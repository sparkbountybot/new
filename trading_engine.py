#!/usr/bin/env python3
"""
Trading Engine — Paper trading with live API readiness

Paper API is operational. Live API blocked by proxy whitelist.
Once proxy allowlist includes api.alpaca.markets, flip paper=False in config.
"""

import os
import json
import requests
from datetime import datetime, timedelta

class TradingEngine:
    def __init__(self, config_path="/sandbox/new/config.yaml"):
        self.config = self._load_config(config_path)
        self.paper = self.config.get("paper", True)
        
        if self.paper:
            self.base_url = "https://paper-api.alpaca.markets"
            print("📊 Using PAPER trading API")
        else:
            self.base_url = "https://api.alpaca.markets"
            print("💰 Using LIVE trading API")
        
        self.key = self.config["alpaca_api_key"]
        self.secret = self.config["alpaca_secret_key"]
        self.headers = {
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret,
        }
        
        self.account = None
        self.positions = []
        self.orders = []
        self.watchlist = self.config.get("watchlist", [])
        
        self._max_position_pct = self.config.get("max_position_pct", 0.5)
        self._max_total_risk = self.config.get("max_total_risk", 0.15)
    
    def _load_config(self, config_path):
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            trading = cfg.get("trading", {})
            if not self.paper and "trading_live" in cfg:
                trading = cfg.get("trading_live", {})
            return trading
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}")
    
    def init(self):
        """Fetch account, positions, and orders."""
        self.account = self._get("/v2/account")
        self.positions = self._get("/v2/positions")
        self.orders = self._get("/v2/orders", params={"status": "open"})
        return {
            "account": self.account,
            "positions_count": len(self.positions),
            "orders_count": len(self.orders),
        }
    
    def _get(self, endpoint, params=None):
        """Make GET request to Alpaca API."""
        url = f"{self.base_url}{endpoint}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else []
        raise RuntimeError(f"GET {endpoint} failed: {resp.status_code} {resp.text}")
    
    def _post(self, endpoint, data):
        """Make POST request to Alpaca API."""
        url = f"{self.base_url}{endpoint}"
        resp = requests.post(url, headers=self.headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            result = resp.json()
            return result if isinstance(result, dict) else {}
        raise RuntimeError(f"POST {endpoint} failed: {resp.status_code} {resp.text}")
    
    def get_portfolio(self):
        """Get current portfolio status."""
        return {
            "equity": float(self.account.get("equity", 0)),
            "cash": float(self.account.get("cash", 0)),
            "buying_power": float(self.account.get("buying_power", 0)),
            "portfolio_value": float(self.account.get("portfolio_value", 0)),
            "positions_count": len(self.positions),
            "orders_count": len(self.orders),
        }
    
    def get_positions(self):
        """Get current positions."""
        result = []
        for pos in (self.positions or []):
            qty = float(pos.get("qty", 0))
            entry = float(pos.get("avg_entry_price", 0))
            current = float(pos.get("current_price", 0))
            pl = float(pos.get("unrealized_pl", 0))
            pl_pct = float(pos.get("unrealized_plpc", 0)) * 100
            mkt_val = float(pos.get("market_value", 0))
            
            result.append({
                "symbol": pos["symbol"],
                "qty": qty,
                "entry_price": entry,
                "current_price": current,
                "market_value": mkt_val,
                "unrealized_pl": pl,
                "unrealized_pl_pct": pl_pct,
                "change_today": pos.get("change_today", 0),
            })
        return result
    
    def submit_order(self, symbol, qty, side="buy", order_type="market", limit_price=None, time_in_force="day"):
        """Submit a new order."""
        data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if order_type == "limit":
            data["limit_price"] = str(limit_price)
        
        print(f"📤 Submitting {side} {qty} {symbol} ({order_type} order)...")
        order = self._post("/v2/orders", data)
        return order
    
    def cancel_all_orders(self):
        """Cancel all open orders."""
        self._post("/v2/orders/cancel-all", {})
        self.orders = self._get("/v2/orders", params={"status": "open"})
        return len(self.orders) == 0
    
    def get_market_hours(self):
        """Get market hours."""
        return self._get("/v2/marketstatus/now")
    
    def scan_watchlist(self):
        """Scan watchlist for trading signals."""
        signals = []
        for sym in self.watchlist:
            try:
                quote = self._get(f"/v2/quotes/{sym}", params={"size": "1"})
                if quote:
                    signals.append({
                        "symbol": sym,
                        "bid_price": quote[0].get("bp", 0) if isinstance(quote, list) else quote.get("bp", 0),
                        "ask_price": quote[0].get("ap", 0) if isinstance(quote, list) else quote.get("ap", 0),
                        "last_price": quote[0].get("lp", 0) if isinstance(quote, list) else quote.get("lp", 0),
                    })
            except:
                pass
        return signals


if __name__ == "__main__":
    engine = TradingEngine()
    engine.init()
    print(f"\n=== PORTFOLIO ===")
    portfolio = engine.get_portfolio()
    for key, val in portfolio.items():
        if "equity" in key or "value" in key or "power" in key:
            print(f"  {key}: ${val:,.2f}")
        else:
            print(f"  {key}: {val}")
    
    print(f"\n=== POSITIONS ===")
    positions = engine.get_positions()
    for pos in positions:
        print(f"  {pos['symbol']}: {pos['qty']} @ ${pos['entry_price']:.2f} | "
              f"Mkt: ${pos['market_value']:,.2f} | P&L: ${pos['unrealized_pl']:.2f} ({pos['unrealized_pl_pct']:.1f}%)")

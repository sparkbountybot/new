"""
Paper Trading Simulator — Full Alpaca paper account simulator.
Runs entirely offline with realistic market simulation.
Tracks positions, P&L, orders, and portfolio history.
"""
import random, time, json, uuid, math
from datetime import datetime, timedelta
from typing import Optional


class PaperAccount:
    """Simulated Alpaca paper trading account."""
    
    def __init__(self, config=None):
        trading = (config or {}).get("trading", {})
        self.initial_cash = trading.get("portfolio_value", 100000)
        self.cash = self.initial_cash
        self.portfolio_value = self.initial_cash
        self.positions = {}  # symbol -> {qty, avg_entry, current_price, unrealized_pl}
        self.orders = []
        self.trade_history = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.daytrade_count = 0
        
        # Simulated market state
        self.market_hours = True
        self.sim_time = datetime.utcnow()
        
    def update_account(self):
        """Recalculate portfolio value from positions and cash."""
        position_value = 0
        for sym, pos in self.positions.items():
            position_value += pos["qty"] * pos["current_price"]
        self.portfolio_value = self.cash + position_value
        self.daily_pnl = self.portfolio_value - self.initial_cash
        return {
            "cash": round(self.cash, 2),
            "portfolio_value": round(self.portfolio_value, 2),
            "position_value": round(position_value, 2),
            "daily_pnl": round(self.daily_pnl, 2),
        }


class MarketSimulator:
    """Simulates realistic stock price movements."""
    
    # Known base prices (realistic)
    BASE_PRICES = {
        "AAPL": 192.00, "MSFT": 425.00, "GOOGL": 175.00, "AMZN": 195.00,
        "META": 560.00, "NVDA": 135.00, "TSLA": 248.00, "JPM": 220.00,
        "V": 310.00, "JNJ": 145.00,
    }
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.price = self.BASE_PRICES.get(symbol, random.uniform(50, 500))
        self.daily_change = random.gauss(0, 0.012)  # ~1.2% daily volatility
        self.open_price = self.price / (1 + self.daily_change * 0.3)
        self.high_price = self.price * (1 + abs(random.gauss(0, 0.006)))
        self.low_price = self.price * (1 - abs(random.gauss(0, 0.006)))
        self.volume = random.randint(10_000_000, 80_000_000)
        self.history = [self.price]  # Track price history for realism
        
    def get_price(self, include_fee: bool = True) -> float:
        """Get current price with tiny spread."""
        spread = self.price * 0.0001  # $0.01 spread
        if random.random() < 0.5:
            price = self.price - spread
        else:
            price = self.price + spread
        return round(price, 2)
    
    def update_price(self):
        """Simulate price movement (small random walk)."""
        change = random.gauss(0, self.price * 0.002)  # 0.2% intra-candle
        self.price = max(1.0, self.price + change)
        self.price = round(self.price, 2)
        self.high_price = max(self.high_price, self.price)
        self.low_price = min(self.low_price, self.price)
        self.history.append(self.price)
        if len(self.history) > 50:
            self.history.pop(0)


class PaperTrader:
    """Full paper trading engine with realistic order execution."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.account = PaperAccount(config)
        self.markets = {}  # symbol -> MarketSimulator
        
        # Initialize markets for watchlist
        watchlist = self.config.get("trading", {}).get("watchlist", [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA",
            "TSLA", "JPM", "V", "JNJ"
        ])
        for sym in watchlist:
            self.markets[sym] = MarketSimulator(sym)
    
    def get_account(self) -> dict:
        """Get account state (matches Alpaca API response format)."""
        return self.account.update_account()
    
    def get_positions(self) -> list:
        """Get current positions (matches Alpaca API response format)."""
        positions = []
        for sym, pos in self.account.positions.items():
            positions.append({
                "symbol": sym,
                "qty": pos["qty"],
                "avg_entry_price": pos["avg_entry"],
                "current_price": pos["current_price"],
                "market_value": pos["qty"] * pos["current_price"],
                "unrealized_pl": pos["qty"] * (pos["current_price"] - pos["avg_entry"]),
                "unrealized_plpc": (pos["current_price"] - pos["avg_entry"]) / pos["avg_entry"] * 100,
                "today_pnl": 0,  # Simplified
            })
        return positions
    
    def submit_order(self, symbol: str, qty: int, side: str, price: Optional[float] = None) -> dict:
        """
        Execute a paper trade. Returns order object matching Alpaca format.
        """
        if symbol not in self.markets:
            # Create market for this symbol with random price
            self.markets[symbol] = MarketSimulator(symbol)
        
        market = self.markets[symbol]
        
        # Get filled price (market order)
        fill_price = price or market.get_price()
        
        # Calculate cost
        total_cost = qty * fill_price
        commission = 0  # Paper trading = free
        
        if side == "BUY":
            if total_cost > self.account.cash:
                return {
                    "id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "status": "rejected",
                    "error": "Insufficient funds",
                    "filled_price": 0,
                }
            
            # Update position
            if symbol in self.account.positions:
                pos = self.account.positions[symbol]
                # Calculate new average price
                old_total = pos["qty"] * pos["avg_entry"]
                new_total = old_total + total_cost
                pos["qty"] += qty
                pos["avg_entry"] = round(new_total / pos["qty"], 2)
            else:
                self.account.positions[symbol] = {
                    "qty": qty,
                    "avg_entry": fill_price,
                    "current_price": fill_price,
                }
            
            self.account.cash -= total_cost
            self.account.daytrade_count += 1
            
        elif side == "SELL":
            if symbol not in self.account.positions:
                return {
                    "id": str(uuid.uuid4()),
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "status": "rejected",
                    "error": f"No position in {symbol}",
                    "filled_price": 0,
                }
            
            pos = self.account.positions[symbol]
            if qty > pos["qty"]:
                qty = pos["qty"]  # Cap at available qty
            
            pnl = qty * (fill_price - pos["avg_entry"])
            self.account.total_pnl += pnl
            
            # Update position (or remove if zero)
            pos["qty"] -= qty
            if pos["qty"] <= 0:
                del self.account.positions[symbol]
            
            self.account.cash += qty * fill_price
        
        # Record order
        order = {
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "filled_price": fill_price,
            "status": "filled",
            "commission": commission,
            "filled_at": datetime.utcnow().isoformat(),
        }
        self.account.orders.append(order)
        self.account.trade_history.append(order)
        
        # Update current price
        market.update_price()
        for sym, pos in self.account.positions.items():
            if sym in self.markets:
                pos["current_price"] = self.markets[sym].price
        
        return order
    
    def run_trades(self, signals: list) -> list:
        """Execute trading signals through the paper trading engine."""
        results = []
        for sig in signals:
            symbol = sig.get("symbol", "")
            action = sig.get("action", "")
            confidence = sig.get("confidence", 0)
            signal_score = sig.get("net_score", 0)
            
            # Skip HOLD and weak signals (confidence < 0.6)
            if action in ("HOLD", "WEAK_BUY", "WEAK_SELL"):
                continue
            if confidence < 0.6:
                continue
            
            # Determine order direction
            side = "BUY" if action == "BUY" else "SELL"
            
            # Get position size from signal or calculate
            qty = sig.get("position_size")
            if qty and qty > 0:
                pass  # Use provided qty
            else:
                # Calculate position size: 20% of portfolio per position
                acct = self.account.update_account()
                max_invest = acct["portfolio_value"] * 0.2
                market = self.markets.get(symbol, MarketSimulator(symbol))
                price = market.price
                qty = max(1, int(max_invest / price / 10))  # Decent sized position
            
            # Check position limit
            if side == "BUY" and len(self.account.positions) >= 5:
                continue
            
            # Execute
            order = self.submit_order(symbol, qty, side)
            results.append({
                "symbol": symbol,
                "action": side,
                "qty": order.get("qty", 0),
                "filled_price": order.get("filled_price", 0),
                "order_id": order.get("id", ""),
                "status": order.get("status", ""),
                "signal": sig,
            })
        
        return results
    
    def print_state(self, header: str = ""):
        """Print current trading state in readable format."""
        acct = self.account.update_account()
        positions = self.get_positions()
        
        if header:
            print(f"\n  [{header}]")
        
        print(f"    Cash: ${acct['cash']:,.2f}")
        print(f"    Portfolio: ${acct['portfolio_value']:,.2f}")
        print(f"    Daily P&L: ${acct['daily_pnl']:,.2f} ({acct['daily_pnl']/acct['portfolio_value']*100:+.2f}%)")
        print(f"    Total P&L: ${self.account.total_pnl:,.2f}")
        print(f"    Positions: {len(positions)}")
        
        if positions:
            for p in positions:
                print(f"      {p['symbol']}: {p['qty']} shares @ ${p['avg_entry_price']:.2f}, "
                      f"Current: ${p['current_price']:.2f}, "
                      f"P&L: ${p['unrealized_pl']:.2f} ({p['unrealized_plpc']:+.1f}%)")
        
        if self.account.trade_history:
            print(f"    Trades: {len(self.account.trade_history)} total")
            for t in self.account.trade_history[-3:]:
                print(f"      {t['symbol']}: {t['side']} {t['qty']} @ ${t['filled_price']:.2f} [{t['status']}]")

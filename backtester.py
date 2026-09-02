"""
Swing Trading Backtester — Uses MarketSimulator for synthetic OHLCV data

Generates realistic price data using the same MarketSimulator that runs
in the paper trading engine, then tests all three strategies against it.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import random
from datetime import datetime, timedelta
from strategies import (
    Bar, Signal, MomentumStrategy, MeanReversionStrategy,
    VolatilityBreakoutStrategy, get_all_strategies
)


class MarketSimulator:
    """Generates synthetic OHLCV data with realistic patterns."""
    
    BASE_PRICES = {
        "AAPL": 192.00, "MSFT": 425.00, "GOOGL": 175.00, "AMZN": 195.00,
        "META": 560.00, "NVDA": 135.00, "TSLA": 248.00, "JPM": 220.00,
        "V": 310.00, "JNJ": 145.00,
    }
    
    def __init__(self, symbol: str, start_price: float = None, volatility: float = 0.02):
        self.symbol = symbol
        self.price = start_price or self.BASE_PRICES.get(symbol, 100.0)
        self.base_volatility = volatility  # Higher = more volatile stocks
        self.trend = 0  # Current market trend
        self.trend_duration = 0
        self.volume_base = random.randint(10_000_000, 50_000_000)
        
    def generate_bars(self, days: int = 180) -> list:
        """Generate synthetic OHLCV bars."""
        bars = []
        for i in range(days):
            # Change trend periodically
            if self.trend_duration <= 0:
                self.trend = random.gauss(0, 0.003)  # Small daily trend
                self.trend_duration = random.randint(5, 20)
            self.trend_duration -= 1
            
            # Generate OHLC
            daily_return = self.trend + random.gauss(0, self.base_volatility)
            open_price = self.price * (1 + random.gauss(0, 0.005))
            close_price = self.price * (1 + daily_return)
            
            # High/Low based on open/close and volatility
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, 0.01)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, 0.01)))
            
            # Volume correlated with price movement
            vol_change = abs(daily_return) / self.base_volatility
            volume = int(self.volume_base * (0.5 + 1.5 * vol_change))
            
            bars.append(Bar(
                timestamp=datetime.utcnow() - timedelta(days=days-i),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume
            ))
            
            # Update price for next bar
            self.price = close_price
        
        return bars


class Backtester:
    """Run backtests on synthetic data."""
    
    def __init__(self, symbols=None, days=180):
        self.symbols = symbols or [
            "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"
        ]
        self.days = days
        self.strategies = get_all_strategies()
        self.results = {}
    
    def backtest_symbol(self, symbol, volatility=0.02):
        """Generate data and test strategies."""
        sim = MarketSimulator(symbol, volatility=volatility)
        bars = sim.generate_bars(self.days)
        
        if len(bars) < 30:
            return {"symbol": symbol, "status": "insufficient_data"}
        
        # Collect signals from all strategies
        all_signals = []
        for strategy in self.strategies:
            name = strategy.__class__.__name__
            for i in range(20, len(bars)):
                window = bars[max(0, i-60):i]
                signal = strategy.analyze(window)
                if signal:
                    signal.symbol = symbol
                    signal.strategy = name
                    signal.entry_time = bars[i-1].timestamp
                    signal.close_time = bars[i].timestamp
                    all_signals.append(signal)
        
        # Simulate trading with signals
        trades = []
        equity = 100000
        position = None
        
        for sig in all_signals:
            if position is None:
                # Enter position (25% of equity)
                shares = int(equity * 0.25 / sig.entry_price)
                if shares > 0:
                    position = {
                        "shares": shares,
                        "entry_price": sig.entry_price,
                        "strategy": sig.strategy,
                        "stop_loss": sig.stop_loss,
                    }
            else:
                # Check exit conditions
                current_price = sig.entry_price  # Use last known price
                pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
                
                if pnl_pct < -0.03 or pnl_pct > 0.05:
                    # Stop loss or take profit
                    exit_price = sig.stop_loss if pnl_pct < 0 else sig.entry_price
                    pnl = (exit_price - position["entry_price"]) * position["shares"]
                    
                    trades.append({
                        "symbol": symbol,
                        "strategy": position["strategy"],
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                    })
                    equity += pnl
                    position = None
        
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        
        return {
            "symbol": symbol,
            "status": "complete",
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins)/len(trades) if trades else 0,
            "total_pnl": sum(t["pnl"] for t in trades),
            "strategies_used": list(set(t["strategy"] for t in trades)),
            "final_equity": equity,
        }
    
    def run_backtest(self):
        """Run backtest on all symbols."""
        for symbol in self.symbols:
            print(f"  Testing {symbol}...")
            result = self.backtest_symbol(symbol)
            self.results[symbol] = result
        return self.results


if __name__ == "__main__":
    print("=" * 60)
    print("  Swing Trading Backtester")
    print("  Using synthetic data with realistic patterns")
    print("  Testing 3 strategies on 180 days")
    print("=" * 60)
    
    # Test each strategy
    print("\n📈 Running backtests...")
    bt = Backtester(days=180)
    results = bt.run_backtest()
    
    print(f"\n{'='*60}")
    print(f"  RESULTS — Strategy Comparison")
    print(f"{'='*60}")
    
    # Group by strategy
    strategy_results = {}
    for symbol, data in results.items():
        if data.get("status") != "complete":
            continue
        for strat in data.get("strategies_used", []):
            if strat not in strategy_results:
                strategy_results[strat] = {"total_trades": 0, "total_pnl": 0, "equities": []}
            strategy_results[strat]["total_trades"] += 1
            strategy_results[strat]["total_pnl"] += data.get("total_pnl", 0)
            strategy_results[strat]["equities"].append(data.get("final_equity", 100000))
    
    for strategy, stats in strategy_results.items():
        avg_eq = np.mean(stats["equities"])
        total_pnl = stats["total_pnl"]
        print(f"\n{strategy}:")
        print(f"  Total P&L: ${total_pnl:>12,.2f}")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Avg Final Equity: ${avg_eq:>12,.2f}")
    
    print(f"\n{'='*60}")
    print(f"  Per-Stock Breakdown")
    print(f"{'='*60}")
    
    for symbol in ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]:
        data = results.get(symbol, {})
        if data.get("status") == "complete":
            print(f"\n{symbol}:")
            print(f"  Final Equity: ${data['final_equity']:>12,.2f}")
            print(f"  Total P&L: ${data['total_pnl']:>12,.2f}")
            print(f"  Trades: {data['total_trades']}")
            print(f"  Win Rate: {data['win_rate']:.0%}")

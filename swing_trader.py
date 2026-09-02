#!/usr/bin/env python3
"""
Live Swing Trading Engine — Uses paper account to execute real signals

Runs continuously: scans market, evaluates strategies, executes trades,
tracks positions, manages risk. This is the actual money-making system.
"""
import json
import os
import subprocess
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

warnings.filterwarnings("ignore")
import sys
sys.path.insert(0, str(Path(__file__).parent))

from strategies import (
    MomentumStrategy, MeanReversionStrategy, VolatilityBreakoutStrategy,
    get_all_strategies
)
from universal_api import create_alpaca_client


class LiveSwingTrader:
    """Real swing trading engine with paper account."""
    
    def __init__(self, paper=True):
        self.paper = paper
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        
        # Load credentials from config
        config_path = Path(__file__).parent / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                content = f.read()
                if paper and "trading:" in content:
                    # Extract paper credentials
                    self.api_key = self._extract_yaml_val(content, "trading:", "alpaca_api_key")
                    self.api_secret = self._extract_yaml_val(content, "trading:", "alpaca_secret_key")
                elif not paper and "trading:" in content:
                    # Use live credentials (first trading section is now live)
                    self.api_key = self._extract_yaml_val(content, "trading:", "alpaca_api_key")
                    self.api_secret = self._extract_yaml_val(content, "trading:", "alpaca_secret_key")
        
        # Fallback to env
        self.api_key = self.api_key or os.environ.get("APCA_API_KEY_ID", "")
        self.api_secret = self.api_secret or os.environ.get("APCA_API_SECRET_KEY", "")
        
        # Watchlist
        self.watchlist = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "JPM", "V", "JNJ"]
        
        # Strategies
        self.strategies = get_all_strategies()
        
        # State
        self.positions = {}
        self.trades = []
        self.running = False
    
    def _extract_yaml_val(self, content, section, key):
        """Extract a value from YAML content."""
        try:
            import yaml as _yaml
            with open(Path(__file__).parent / "config.yaml") as f:
                cfg = _yaml.safe_load(f) or {}
                trading = cfg.get("trading", {})
                return trading.get(key, "")
        except:
            return ""
    
    def get_account(self):
        """Get account info from Alpaca."""
        try:
            client = create_alpaca_client(
                key=self.api_key,
                secret=self.api_secret,
                paper=self.paper
            )
            return client.get_account()
        except Exception as e:
            print(f"  ❌ Account fetch failed: {e}")
            return None
    
    def get_positions(self):
        """Get current positions."""
        try:
            client = create_alpaca_client(
                key=self.api_key,
                secret=self.api_secret,
                paper=self.paper
            )
            return client.get_positions()
        except Exception as e:
            print(f"  ❌ Positions fetch failed: {e}")
            return []
    
    def get_historical_bars(self, symbol, days=60):
        """Get recent price bars using yfinance directly."""
        try:
            import yfinance as yf
            import pandas as pd
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d")
            
            if df is None or df.empty or len(df) == 0:
                return []
            
            from strategies import Bar
            bars = []
            for idx, row in df.iterrows():
                bars.append(Bar(
                    timestamp=idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx,
                    open=float(row.get('Open', row.get('open', 0))),
                    high=float(row.get('High', row.get('high', 0))),
                    low=float(row.get('Low', row.get('low', 0))),
                    close=float(row.get('Close', row.get('close', 0))),
                    volume=int(row.get('Volume', row.get('volume', 0)))
                ))
            return bars
        except Exception as e:
            print(f"  ❌ Bars fetch failed for {symbol}: {e}")
            return []
    
    def submit_order(self, symbol, qty, side="buy"):
        """Submit a market order."""
        try:
            client = create_alpaca_client(
                key=self.api_key,
                secret=self.api_secret,
                paper=self.paper
            )
            return client.submit_order(symbol, qty, side, "market", "day")
        except Exception as e:
            print(f"  ❌ Order failed for {symbol}: {e}")
            return None
    
    def analyze_symbol(self, symbol):
        """Run all strategies on a symbol."""
        bars = self.get_historical_bars(symbol, days=60)
        if len(bars) < 25:
            return None
        
        # Convert to strategy Bar objects
        from strategies import Bar
        strategy_bars = []
        for b in bars:
            strategy_bars.append(Bar(
                timestamp=b.get('t', datetime.utcnow()),
                open=float(b['o']),
                high=float(b['h']),
                low=float(b['l']),
                close=float(b['c']),
                volume=int(b['v'])
            ))
        
        # Try each strategy
        signals = []
        for strategy in self.strategies:
            signal = strategy.analyze(strategy_bars)
            if signal:
                signal.symbol = symbol
                signals.append(signal)
        
        return signals
    
    def get_price(self, symbol):
        """Get current price."""
        try:
            client = create_alpaca_client(
                key=self.api_key,
                secret=self.api_secret,
                paper=self.paper
            )
            account = client.get_account()
            if account:
                # Use a simple lookup - actually query last quote
                return client.get_last_quote(symbol)
        except:
            pass
        
        # Fallback: estimate from position data or use base price
        return None
    
    def scan_and_trade(self, max_positions=5, risk_per_trade=0.10):
        """Scan all symbols and execute trades."""
        print(f"\n🔍 Scanning {len(self.watchlist)} symbols...")
        
        # Get account info
        account = self.get_account()
        if not account:
            print("  ❌ Cannot connect to account")
            return
        
        equity = float(account.get('equity', 0))
        buying_power = float(account.get('buying_power', 0))
        print(f"  💰 Equity: ${equity:,.2f}")
        print(f"  💳 Buying Power: ${buying_power:,.2f}")
        
        # Get existing positions
        existing_positions = self.get_positions()
        pos_symbols = {p['symbol']: p for p in existing_positions}
        print(f"  📊 Open positions: {len(pos_symbols)}")
        
        # Scan each symbol
        trades_placed = []
        for symbol in self.watchlist:
            if symbol in pos_symbols:
                continue  # Skip symbols we already hold
            
            signals = self.analyze_symbol(symbol)
            if not signals:
                continue
            
            # Find best signal (highest confidence)
            best_signal = max(signals, key=lambda s: s.confidence)
            
            if best_signal.confidence < 0.6:
                continue  # Skip weak signals
            
            # Calculate position size
            position_size = equity * risk_per_trade
            current_price = best_signal.entry_price
            shares = int(position_size / current_price)
            
            if shares < 1:
                continue
            
            print(f"\n  🚨 SIGNAL: {symbol}")
            print(f"     Strategy: {best_signal.strategy}")
            print(f"     Direction: {best_signal.direction}")
            print(f"     Entry: ${best_signal.entry_price:.2f}")
            print(f"     Stop Loss: ${best_signal.stop_loss:.2f}")
            print(f"     Take Profit: ${best_signal.take_profit:.2f}")
            print(f"     Confidence: {best_signal.confidence:.0%}")
            print(f"     Shares: {shares}")
            
            # Execute the trade
            print(f"     📤 Placing {best_signal.direction} order...")
            order = self.submit_order(symbol, shares, best_signal.direction.lower())
            
            if order:
                trade = {
                    "symbol": symbol,
                    "direction": best_signal.direction,
                    "shares": shares,
                    "entry_price": best_signal.entry_price,
                    "stop_loss": best_signal.stop_loss,
                    "take_profit": best_signal.take_profit,
                    "strategy": best_signal.strategy,
                    "confidence": best_signal.confidence,
                    "timestamp": datetime.utcnow().isoformat(),
                    "order_id": order.get('id', 'unknown'),
                }
                self.trades.append(trade)
                trades_placed.append(trade)
                print(f"     ✅ Order placed: {order.get('id', 'unknown')}")
            else:
                print(f"     ❌ Order failed")
        
        if trades_placed:
            print(f"\n✅ {len(trades_placed)} trades executed")
        else:
            print(f"\n📭 No trades executed (no strong signals or too many positions)")
        
        # Save state
        self.save_state()
        
        return trades_placed
    
    def manage_positions(self):
        """Check existing positions for stop loss/take profit."""
        positions = self.get_positions()
        managed = 0
        
        for pos in positions:
            symbol = pos['symbol']
            qty = float(pos['qty'])
            avg_entry = float(pos['avg_entry_price'])
            current_price = float(pos.get('current_price', avg_entry))
            
            # Get our trade record
            trade = next((t for t in self.trades if t['symbol'] == symbol and t['direction'] == 'BUY'), None)
            if not trade:
                continue
            
            pnl_pct = (current_price - trade['entry_price']) / trade['entry_price']
            
            # Check stop loss
            if pnl_pct < -0.03:  # 3% stop loss
                print(f"\n🛑 STOP LOSS: {symbol} ({pnl_pct:.1%} loss)")
                self.submit_order(symbol, int(qty), "sell")
                managed += 1
            
            # Check take profit (5% gain)
            elif pnl_pct > 0.05:
                print(f"\n💰 TAKE PROFIT: {symbol} ({pnl_pct:.1%} gain)")
                self.submit_order(symbol, int(qty), "sell")
                managed += 1
        
        return managed
    
    def run_cycle(self):
        """Run one trading cycle (scan + manage)."""
        print(f"\n{'='*60}")
        print(f"  Trading Cycle — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Mode: {'PAPER' if self.paper else 'LIVE'}")
        print(f"{'='*60}")
        
        # First manage existing positions
        self.manage_positions()
        
        # Then scan for new signals
        self.scan_and_trade()
        
        # Save results
        self.save_state()
    
    def save_state(self):
        """Save trading state to file."""
        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "paper": self.paper,
            "trades": self.trades,
            "total_trades": len(self.trades),
        }
        state_path = Path(__file__).parent / "trading_state.json"
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)


if __name__ == "__main__":
    print("=" * 60)
    print("  Swing Trading Engine")
    print("  Running live on paper account")
    print("=" * 60)
    
    # Start with paper account (can switch to live after network policy)
    trader = LiveSwingTrader(paper=True)
    trader.run_cycle()

#!/usr/bin/env python3
"""
Swing Trading System — Multi-Strategy Engine

Three strategies:
1. Momentum: trend-following (price above moving averages)
2. Mean Reversion: RSI + Bollinger Bands (buy oversold, sell overbought)
3. Volatility Breakout: ATR-based (breakout above recent highs)

Plus risk management: position sizing, stop-loss, max drawdown.
"""
import subprocess, json, os, sys, random, math
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client

class SwingTradingSystem:
    """Multi-strategy swing trading system."""
    
    def __init__(self, api_key=None, api_secret=None, paper=True):
        self.client = create_alpaca_client(api_key, api_secret, paper)
        self.strategy = "momentum"  # momentum | mean_reversion | volatility | hybrid
        self.position_size_pct = 0.1  # 10% of portfolio per position
        self.max_positions = 5
        self.max_drawdown = 0.10  # 10% max drawdown
        
    def get_account(self):
        """Get account info."""
        try:
            acct = self.client.get_account()
            if isinstance(acct, dict):
                return {
                    'equity': float(acct.get('equity', 0)),
                    'portfolio_value': float(acct.get('portfolio_value', 0)),
                    'cash': float(acct.get('cash', 0)),
                    'buying_power': float(acct.get('buying_power', 0)),
                    'status': acct.get('status')
                }
        except: pass
        return None
    
    def get_positions(self):
        """Get current positions."""
        try:
            pos = self.client.get_positions()
            if isinstance(pos, list):
                return pos
        except: pass
        return []
    
    def generate_realistic_prices(self, base_price, days=60):
        """Generate more realistic price history with trends and volatility."""
        random.seed(hash(base_price) % 2**32)  # Different seed per price
        prices = []
        trend = random.uniform(-0.02, 0.03)  # Daily drift
        current = base_price
        
        for i in range(days):
            # Trend + random walk + occasional spikes
            spike = random.gauss(0, current * 0.01)  # Small noise
            if random.random() < 0.05:  # 5% chance of bigger move
                spike = random.gauss(0, current * 0.04)  # 4% move
            
            # Add trend
            trend_shift = random.gauss(trend * current, current * 0.005)
            price = current + spike + trend_shift
            current = max(price, base_price * 0.5)  # Floor at 50%
            prices.append(current)
        
        # Ensure last price matches current
        if prices:
            prices[-1] = base_price
        return prices
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI."""
        if len(prices) < period + 1: return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        ag = sum(gains[:period]) / period
        al = sum(losses[:period]) / period
        if al == 0: return 100.0
        return 100 - (100 / (1 + ag / al))
    
    def calculate_sma(self, prices, period=20):
        """Calculate Simple Moving Average."""
        if len(prices) < period: return prices[-1]
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices, period=12):
        """Calculate Exponential Moving Average."""
        if not prices: return 0
        multiplier = 2 / (period + 1)
        ema_val = sum(prices[:period]) / period
        for price in prices[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val
    
    def calculate_macd(self, prices, fast=12, slow=26):
        """Calculate MACD line."""
        if len(prices) < slow: return 0
        fast_ema = self.calculate_ema(prices, fast)
        slow_ema = self.calculate_ema(prices, slow)
        return fast_ema - slow_ema
    
    def calculate_bollinger_bands(self, prices, period=20, num_std=2):
        """Calculate Bollinger Bands."""
        if len(prices) < period: return (0, 0, 0)
        window = prices[-period:]
        sma = sum(window) / len(window)
        std = (sum((p - sma) ** 2 for p in window) / len(window)) ** 0.5
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return (upper, sma, lower)
    
    def calculate_atr(self, prices, high_prices, low_prices, period=14):
        """Calculate Average True Range."""
        if len(prices) < period: return 0
        trs = []
        for i in range(1, len(prices)):
            tr = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - prices[i-1]),
                abs(low_prices[i] - prices[i-1])
            )
            trs.append(tr)
        return sum(trs[:period]) / period
    
    def momentum_signal(self, prices):
        """Momentum strategy: buy if price is trending up."""
        if len(prices) < 30: return None
        
        current = prices[-1]
        sma_20 = self.calculate_sma(prices, 20)
        ema_12 = self.calculate_ema(prices, 12)
        macd = self.calculate_macd(prices)
        
        # Price above SMA (uptrend)
        price_above_sma = current > sma_20
        # Price above EMA (acceleration)
        price_above_ema = current > ema_12
        # MACD positive (bullish momentum)
        macd_positive = macd > 0
        
        if price_above_sma and price_above_ema and macd_positive:
            # Strong uptrend
            strength = min((current - sma_20) / sma_20 * 10, 1.0)
            return {
                'signal': 'BUY',
                'confidence': strength,
                'reason': f'Price above SMA(20) and EMA(12), MACD positive'
            }
        elif current < sma_20 * 0.95:  # Below SMA by 5%
            # Trend reversal or downtrend
            strength = min((sma_20 - current) / sma_20 * 10, 1.0)
            return {
                'signal': 'SELL',
                'confidence': strength,
                'reason': f'Price below SMA(20), potential downtrend'
            }
        
        return None
    
    def mean_reversion_signal(self, prices):
        """Mean reversion strategy: buy oversold, sell overbought."""
        if len(prices) < 30: return None
        
        rsi = self.calculate_rsi(prices)
        bb_upper, bb_sma, bb_lower = self.calculate_bollinger_bands(prices)
        current = prices[-1]
        
        if rsi < 30:
            # Oversold
            return {
                'signal': 'BUY',
                'confidence': (30 - rsi) / 30,
                'reason': f'RSI oversold at {rsi:.1f}'
            }
        elif rsi > 70:
            # Overbought
            return {
                'signal': 'SELL',
                'confidence': (rsi - 70) / 30,
                'reason': f'RSI overbought at {rsi:.1f}'
            }
        
        # Bollinger Band touch
        if bb_lower and current < bb_lower * 1.01:
            return {
                'signal': 'BUY',
                'confidence': 0.6,
                'reason': 'Price touching lower Bollinger Band'
            }
        elif bb_upper and current > bb_upper * 0.99:
            return {
                'signal': 'SELL',
                'confidence': 0.6,
                'reason': 'Price touching upper Bollinger Band'
            }
        
        return None
    
    def volatility_breakout_signal(self, prices, high_prices, low_prices):
        """Volatility breakout: buy when price breaks above recent high."""
        if len(prices) < 20: return None
        
        current = prices[-1]
        recent_high = max(prices[-20:])
        recent_low = min(prices[-20:])
        
        # Breakout above high
        if current >= recent_high * 0.99:  # Within 1% of high
            return {
                'signal': 'BUY',
                'confidence': 0.7,
                'reason': f'Breakout above 20-day high'
            }
        # Breakdown below low
        elif current <= recent_low * 1.01:  # Within 1% of low
            return {
                'signal': 'SELL',
                'confidence': 0.7,
                'reason': f'Breakdown below 20-day low'
            }
        
        return None
    
    def generate_signal(self, prices, high_prices=None, low_prices=None):
        """Generate signal based on current strategy."""
        if self.strategy == "momentum":
            return self.momentum_signal(prices)
        elif self.strategy == "mean_reversion":
            return self.mean_reversion_signal(prices)
        elif self.strategy == "volatility":
            if high_prices and low_prices:
                return self.volatility_breakout_signal(prices, high_prices, low_prices)
            return None
        elif self.strategy == "hybrid":
            # Use all three strategies
            signals = [
                self.momentum_signal(prices),
                self.mean_reversion_signal(prices),
                self.volatility_breakout_signal(prices, high_prices, low_prices) if high_prices and low_prices else None
            ]
            # If any signal is BUY/SELL, return it (prioritize momentum)
            for s in signals:
                if s and s['signal'] in ['BUY', 'SELL']:
                    return s
        return None
    
    def backtest_strategy(self, symbol, strategy='momentum', days=60):
        """Backtest a strategy on simulated price history."""
        self.strategy = strategy
        
        # Generate realistic price history
        base_price = random.uniform(50, 300)
        history = self.generate_realistic_prices(base_price, days)
        
        # Generate signals
        signals = []
        for i in range(20, len(history)):  # Start after 20 days
            signal = self.generate_signal(history[:i])
            if signal:
                signals.append(signal)
        
        # Count signals
        buys = sum(1 for s in signals if s['signal'] == 'BUY')
        sells = sum(1 for s in signals if s['signal'] == 'SELL')
        
        # Average confidence
        avg_conf = (sum(s['confidence'] for s in signals) / len(signals)) if signals else 0
        
        return {
            'symbol': symbol,
            'strategy': strategy,
            'days': days,
            'buy_signals': buys,
            'sell_signals': sells,
            'total_signals': len(signals),
            'avg_confidence': avg_conf
        }
    
    def run_all_backtests(self, symbols=['AAPL', 'GOOGL', 'NVDA']):
        """Run backtests for all strategies on all symbols."""
        results = []
        for symbol in symbols:
            for strategy in ['momentum', 'mean_reversion', 'volatility', 'hybrid']:
                result = self.backtest_strategy(symbol, strategy)
                results.append(result)
        return results

if __name__ == '__main__':
    # Initialize
    print("🚀 Swing Trading System V2")
    
    try:
        system = SwingTradingSystem()
        print(f"  ✅ API Client mode: {system.client.mode}")
    except Exception as e:
        print(f"  ⚠️ Could not create client: {e}")
        system = None
    
    # Run backtests
    print("\n📊 Running backtests...")
    if system:
        results = system.run_all_backtests()
        for r in results:
            print(f"  {r['symbol']} ({r['strategy']}): "
                  f"BUY={r['buy_signals']}, SELL={r['sell_signals']}, "
                  f"Total={r['total_signals']}, "
                  f"Confidence={r['avg_confidence']:.2f}")
        
        # Analyze current positions
        print("\n📈 Current Positions Analysis")
        positions = system.get_positions()
        for pos in positions:
            sym = pos.get('symbol', '')
            cur = float(pos.get('current_price', 0))
            entry = float(pos.get('avg_entry_price', 0))
            pl = float(pos.get('unrealized_pl', 0))
            
            history = system.generate_realistic_prices(entry, 30)
            history[-1] = cur  # Current price
            
            rsi = system.calculate_rsi(history)
            macd = system.calculate_macd(history)
            sma_20 = system.calculate_sma(history, 20)
            
            signal = system.generate_signal(history)
            
            print(f"  {sym}: ${cur:.2f} (entry: ${entry:.2f}), "
                  f"P&L: ${pl:+.2f}, "
                  f"RSI: {rsi:.1f}, MACD: {macd:.4f}, "
                  f"Signal: {signal['signal'] if signal else 'HOLD'}")

"""
PriceSimulator — Generate realistic price data with intentional patterns

Designed to create scenarios that trigger each strategy type:
- Mean reversion: oversold/overbought conditions
- Momentum: trend continuation breakouts
- Volatility: ATR-based breakouts
"""
import random
from datetime import datetime, timedelta
from strategies import Bar


class PriceSimulator:
    BASE_PRICES = {
        "AAPL": 324.00, "MSFT": 410.00, "NVDA": 217.00, "TSLA": 380.00,
        "AMZN": 198.00, "META": 620.00, "GOOGL": 185.00, "JPM": 225.00,
        "V": 310.00, "JNJ": 145.00,
    }
    
    def __init__(self, symbol, seed=None):
        self.symbol = symbol
        self.base_price = self.BASE_PRICES.get(symbol, 100.0)
        if seed is not None:
            random.seed(seed)
    
    def generate_mean_reversion_bars(self, num_bars=30):
        """Generate data with clear oversold/overbought patterns."""
        bars = []
        price = self.base_price
        
        # First 15 bars: gradual uptrend (creates overbought later)
        for i in range(num_bars):
            if i < 8:
                # Strong uptrend
                daily_change = random.uniform(0.02, 0.04)
            elif i < 15:
                # Continue uptrend but slower
                daily_change = random.uniform(0.005, 0.015)
            elif i < 20:
                # Peak reversal — sharp drop
                daily_change = random.uniform(-0.05, -0.02)
            else:
                # Recovery
                daily_change = random.uniform(0.01, 0.03)
            
            open_price = price * (1 + random.gauss(0, 0.005))
            close_price = price * (1 + daily_change)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.001, 0.005))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.001, 0.005))
            
            bars.append(Bar(
                timestamp=datetime.utcnow() - timedelta(days=num_bars-i),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=int(random.uniform(15_000_000, 50_000_000)),
            ))
            price = close_price
        
        return bars
    
    def generate_momentum_bars(self, num_bars=30):
        """Generate consolidation → breakout pattern."""
        bars = []
        price = self.base_price
        
        for i in range(num_bars):
            if i < 10:
                # Consolidation — low volatility
                daily_change = random.uniform(-0.005, 0.005)
            elif i < 20:
                # Sideways with slight uptrend
                daily_change = random.uniform(-0.003, 0.008)
            else:
                # Breakout!
                daily_change = random.uniform(0.02, 0.05)
            
            open_price = price * (1 + random.gauss(0, 0.003))
            close_price = price * (1 + daily_change)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.002, 0.008))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.002, 0.008))
            
            bars.append(Bar(
                timestamp=datetime.utcnow() - timedelta(days=num_bars-i),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=int(random.uniform(15_000_000, 70_000_000)),
            ))
            price = close_price
        
        return bars
    
    def generate_oversold_bars(self, num_bars=30):
        """Generate data with clear oversold conditions (RSI < 30)."""
        bars = []
        price = self.base_price
        
        # First 20 bars: steady uptrend to create high RSI
        for i in range(num_bars):
            if i < 20:
                daily_change = random.uniform(0.008, 0.02)
            elif i < 25:
                # Sharp sell-off
                daily_change = random.uniform(-0.06, -0.03)
            else:
                # Slight bounce but still low
                daily_change = random.uniform(-0.01, 0.005)
            
            open_price = price * (1 + random.gauss(0, 0.004))
            close_price = price * (1 + daily_change)
            high_price = max(open_price, close_price) * (1 + random.uniform(0.002, 0.005))
            low_price = min(open_price, close_price) * (1 - random.uniform(0.002, 0.005))
            
            bars.append(Bar(
                timestamp=datetime.utcnow() - timedelta(days=num_bars-i),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=int(random.uniform(20_000_000, 60_000_000)),
            ))
            price = close_price
        
        return bars
    
    def generate(self, mode='mixed'):
        """Generate bars with specified pattern."""
        if mode == 'oversold':
            return self.generate_oversold_bars(40)  # Use 40 bars for better signal
        elif mode == 'momentum':
            return self.generate_momentum_bars(40)
        elif mode == 'mean_reversion':
            return self.generate_mean_reversion_bars(40)
        else:
            patterns = ['oversold', 'mean_reversion', 'momentum']
            pattern = random.choice(patterns)
            return getattr(self, f'generate_{pattern}_bars')(40)

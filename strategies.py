"""
Swing Trading Strategies — Multi-strategy system
Strategies:
1. Momentum Breakout — trend continuation after consolidation
2. Mean Reversion — RSI/Bollinger Band reversals
3. Volatility Breakout — ATR-based breakouts
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import numpy as np


@dataclass
class Signal:
    symbol: str
    direction: str  # "BUY" or "SELL"
    strategy: str
    confidence: float  # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime
    
    @property
    def risk_reward(self):
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MomentumStrategy:
    """Trend-following with breakout confirmation."""
    
    def __init__(self, lookback=20, breakout_pct=0.02):
        self.lookback = lookback
        self.breakout_pct = breakout_pct  # 2% breakout threshold
    
    def analyze(self, bars: list) -> Optional[Signal]:
        if len(bars) < self.lookback + 5:
            return None
        
        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        
        current = closes[-1]
        
        # Calculate consolidation zone (last N bars range)
        recent_highs = highs[-self.lookback:]
        recent_lows = lows[-self.lookback:]
        consolidation_high = max(recent_highs)
        consolidation_low = min(recent_lows)
        
        # Detect breakout above consolidation
        if current > consolidation_high * (1 + self.breakout_pct):
            # Momentum confirmed — rising volume
            if bars[-1].volume > np.mean([b.volume for b in bars[-5:-1]]) * 1.2:
                stop = consolidation_high * 0.98
                target = consolidation_high * 1.05
                confidence = 0.75 if bars[-1].volume > np.mean([b.volume for b in bars[-10:-1]]) * 1.5 else 0.65
                
                return Signal(
                    symbol="UNKNOWN",  # filled by caller
                    direction="BUY",
                    strategy="MOMENTUM",
                    confidence=confidence,
                    entry_price=current,
                    stop_loss=stop,
                    take_profit=target,
                    timestamp=bars[-1].timestamp
                )
        
        # Detect breakdown below consolidation
        if current < consolidation_low * (1 - self.breakout_pct):
            stop = consolidation_low * 1.02
            target = consolidation_low * 0.95
            
            return Signal(
                symbol="UNKNOWN",
                direction="SELL",  # short signal
                strategy="MOMENTUM",
                confidence=0.7,
                entry_price=current,
                stop_loss=stop,
                take_profit=target,
                timestamp=bars[-1].timestamp
            )
        
        return None


class MeanReversionStrategy:
    """RSI + Bollinger Band mean reversion."""
    
    def __init__(self, rsi_period=14, bb_period=20, bb_std=2):
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
    
    def _rsi(self, closes: list) -> float:
        if len(closes) < self.rsi_period:
            return 50
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _bollinger_bands(self, closes: list) -> tuple:
        if len(closes) < self.bb_period:
            return (0, 0, 0)
        window = closes[-self.bb_period:]
        sma = np.mean(window)
        std = np.std(window)
        upper = sma + self.bb_std * std
        lower = sma - self.bb_std * std
        return (upper, sma, lower)
    
    def analyze(self, bars: list) -> Optional[Signal]:
        if len(bars) < 30:
            return None
        
        closes = [b.close for b in bars]
        current = closes[-1]
        
        rsi = self._rsi(closes)
        bb_upper, bb_mid, bb_lower = self._bollinger_bands(closes)
        
        # Oversold at lower band — BUY signal
        if current < bb_lower and rsi < 30:
            stop = bb_lower * 0.98
            target = bb_upper * 0.95  # Mean reversion to upper band
            confidence = 0.65 if rsi < 25 else 0.6
            
            return Signal(
                symbol="UNKNOWN",
                direction="BUY",
                strategy="MEAN_REVERSION",
                confidence=confidence,
                entry_price=current,
                stop_loss=stop,
                take_profit=target,
                timestamp=bars[-1].timestamp
            )
        
        # Overbought at upper band — SELL signal
        if current > bb_upper and rsi > 70:
            stop = bb_upper * 1.02
            target = bb_lower * 1.05
            confidence = 0.65 if rsi > 75 else 0.6
            
            return Signal(
                symbol="UNKNOWN",
                direction="SELL",
                strategy="MEAN_REVERSION",
                confidence=confidence,
                entry_price=current,
                stop_loss=stop,
                take_profit=target,
                timestamp=bars[-1].timestamp
            )
        
        return None


class VolatilityBreakoutStrategy:
    """ATR-based volatility breakout."""
    
    def __init__(self, atr_period=14, breakout_mult=2.0):
        self.atr_period = atr_period
        self.breakout_mult = breakout_mult
    
    def _atr(self, bars: list) -> float:
        if len(bars) < self.atr_period + 1:
            return 0
        trs = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return np.mean(trs[-self.atr_period:])
    
    def analyze(self, bars: list) -> Optional[Signal]:
        if len(bars) < 20:
            return None
        
        atr = self._atr(bars)
        if atr == 0:
            return None
        
        current = bars[-1].close
        recent_high = max(b.high for b in bars[-5:])
        recent_low = min(b.low for b in bars[-5:])
        
        # Breakout above recent high + ATR buffer
        if current > recent_high + atr * self.breakout_mult:
            stop = recent_high * 0.98
            target = current + atr * self.breakout_mult * 2
            confidence = 0.7 if bars[-1].volume > 1.5 * np.mean([b.volume for b in bars[-10:-1]]) else 0.65
            
            return Signal(
                symbol="UNKNOWN",
                direction="BUY",
                strategy="VOLATILITY_BREAKOUT",
                confidence=confidence,
                entry_price=current,
                stop_loss=stop,
                take_profit=target,
                timestamp=bars[-1].timestamp
            )
        
        # Breakdown below recent low
        if current < recent_low - atr * self.breakout_mult:
            stop = recent_low * 1.02
            target = current - atr * self.breakout_mult * 2
            
            return Signal(
                symbol="UNKNOWN",
                direction="SELL",
                strategy="VOLATILITY_BREAKOUT",
                confidence=0.7,
                entry_price=current,
                stop_loss=stop,
                take_profit=target,
                timestamp=bars[-1].timestamp
            )
        
        return None


def get_all_strategies():
    """Return list of all strategy instances."""
    return [
        MomentumStrategy(),
        MeanReversionStrategy(),
        VolatilityBreakoutStrategy()
    ]

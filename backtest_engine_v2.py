#!/usr/bin/env python3
"""
Backtest Engine — Full pipeline with Universal API Client

Fetches real portfolio data, generates trading signals, and runs backtest
using simulated price history based on real entry prices.
"""
import subprocess, json, os, sys, random
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client

def get_positions(client):
    """Fetch real positions from Alpaca."""
    try:
        positions = client.get("/v2/positions")
        if isinstance(positions, list):
            return positions
    except:
        pass
    return []

def generate_price_history(current_price, entry_price, days=30):
    """Generate simulated price history around current price."""
    random.seed(42)  # Deterministic
    history = []
    
    # Start from entry price, walk to current price
    for i in range(days):
        t = i / days
        base = entry_price * (1 - t) + current_price * t
        
        # Add realistic volatility (2% daily)
        noise = random.gauss(0, base * 0.02)
        price = base + noise
        
        # Keep positive
        history.append(max(price, 1.0))
    
    # Ensure last price matches current
    if history:
        history[-1] = current_price
    
    return history

def calculate_rsi(prices, period=14):
    """Calculate RSI from closing prices."""
    if len(prices) < period + 1:
        return 50  # Neutral if not enough data
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_indicators(prices):
    """Calculate all indicators for price history."""
    rsi = calculate_rsi(prices)
    return {
        'rsi': rsi,
        'current_price': prices[-1] if prices else 0,
        'high_30': max(prices[-30:]) if len(prices) >= 30 else max(prices),
        'low_30': min(prices[-30:]) if len(prices) >= 30 else min(prices)
    }

def generate_signal(indicators, position_size=0.2):
    """Generate buy/sell/hold based on indicators."""
    if indicators['current_price'] <= 0:
        return 'HOLD', 0.0, position_size
    
    rsi = indicators['rsi']
    
    # RSI-based signals
    if rsi < 30:
        confidence = (30 - rsi) / 30
        return 'BUY', confidence, position_size
    elif rsi > 70:
        confidence = (rsi - 70) / 30
        return 'SELL', confidence, position_size
    
    # Price position in 30-day range
    price_range = indicators['high_30'] - indicators['low_30']
    if price_range > 0:
        position_in_range = (indicators['current_price'] - indicators['low_30']) / price_range
        if position_in_range > 0.9:
            return 'SELL', 0.5, position_size * 0.5
        elif position_in_range < 0.1:
            return 'BUY', 0.5, position_size * 0.5
    
    return 'HOLD', 0.0, position_size

def backtest():
    """Run backtest across current positions."""
    print("🚀 Starting backtest engine...")
    
    try:
        client = create_alpaca_client()
        print(f"  ✅ API Client mode: {client.mode}")
    except Exception as e:
        print(f"  ⚠️ Could not create client: {e}")
        return None

    # Get account
    try:
        acct = client.get_account()
        if isinstance(acct, dict) and acct.get('status') == 'ACTIVE':
            portfolio = float(acct.get('portfolio_value', 0))
            print(f"  ✅ Account: ${portfolio:,.2f} portfolio")
        else:
            print("  ⚠️ Account not ACTIVE")
            return None
    except Exception as e:
        print(f"  ⚠️ Could not fetch account: {e}")
        return None

    # Get positions
    positions = get_positions(client)
    if not positions:
        print("  ⚠️ No positions")
        return None
    
    print(f"\n  📊 Analyzing {len(positions)} positions:\n")
    
    results = []
    for pos in positions:
        symbol = pos.get('symbol', '')
        current_price = float(pos.get('current_price', 0))
        entry_price = float(pos.get('avg_entry_price', 0))
        qty = pos.get('qty', '0')
        pl = float(pos.get('unrealized_pl', 0))
        
        # Generate price history for backtest
        history = generate_price_history(current_price, entry_price)
        indicators = calculate_indicators(history)
        signal, confidence, size = generate_signal(indicators)
        
        result = {
            'symbol': symbol,
            'current_price': current_price,
            'entry_price': entry_price,
            'qty': qty,
            'unrealized_pl': pl,
            'rsi': indicators['rsi'],
            'high_30': indicators['high_30'],
            'low_30': indicators['low_30'],
            'signal': signal,
            'confidence': confidence
        }
        results.append(result)
        
        # Print signal if not HOLD
        if signal != 'HOLD':
            print(f"  📈 {symbol}: {signal} @ ${current_price:.2f} "
                  f"(RSI={indicators['rsi']:.1f}, "
                  f"P&L=${pl:+.2f}, "
                  f"confidence={confidence:.2f})")
    
    return results

if __name__ == '__main__':
    results = backtest()
    if results:
        print(f"\n  ✅ Backtest complete: {len(results)} positions analyzed")
        print(f"  ⚠️ No real data source — signals based on simulated history")
        print(f"  💡 Next: Add historical price data source for true backtesting")
    else:
        print("\n  ⚠️ No positions to analyze")

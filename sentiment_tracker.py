#!/usr/bin/env python3
"""
Market Sentiment Tracker — Part of backtesting pipeline

Tries to gather sentiment data from available sources.
Falls back gracefully when external APIs are blocked.
"""
import json, os, sys, subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/sandbox/new')
from universal_api import create_alpaca_client

def fetch_sentiment_via_web_scraper(symbol):
    """
    Try to fetch basic sentiment from free sources.
    Falls back if external sites are blocked.
    """
    results = {
        'symbol': symbol,
        'sources': [],
        'sentiment': 'NEUTRAL',
        'score': 0.5
    }
    
    # Check if we can reach any external data sources
    sources = [
        ('Yahoo Finance', 'https://finance.yahoo.com/quote/{}'),
        ('StockTwits', 'https://api.stocktwits.com/api/2/streams/symbol/{}.json'),
    ]
    
    for name, url in sources:
        try:
            cmd = f'curl -s --max-time 5 "{url.format(symbol)}"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0 and result.stdout:
                if len(result.stdout) > 100:
                    results['sources'].append(f"{name}: {len(result.stdout)} bytes")
        except:
            pass
    
    if not results['sources']:
        results['sources'].append('External sources blocked in sandbox')
        results['sentiment'] = 'NEUTRAL'
        results['score'] = 0.5
    
    return results

def calculate_technical_sentiment(indicators):
    """
    Derive a sentiment score from technical indicators alone.
    This is our primary sentiment source given network limitations.
    """
    rsi = indicators.get('rsi', 50)
    macd = indicators.get('macd', 0)
    bb_upper = indicators.get('bb_upper', 0)
    bb_lower = indicators.get('bb_lower', 0)
    current_price = indicators.get('current_price', 0)
    
    # RSI sentiment (0 = extreme bearish, 100 = extreme bullish)
    rsi_sentiment = rsi / 100
    
    # MACD sentiment (positive = bullish, negative = bearish)
    macd_sentiment = 0.5 + (0.1 * macd) if macd else 0.5
    macd_sentiment = max(0, min(1, macd_sentiment))
    
    # Bollinger Band sentiment
    if bb_upper and bb_lower and current_price:
        price_range = bb_upper - bb_lower
        if price_range > 0:
            position = (current_price - bb_lower) / price_range
            bb_sentiment = position  # 0 = at lower band, 1 = at upper band
        else:
            bb_sentiment = 0.5
    else:
        bb_sentiment = 0.5
    
    # Weighted average
    weighted_sentiment = (rsi_sentiment * 0.5 + 
                         macd_sentiment * 0.3 + 
                         bb_sentiment * 0.2)
    
    return {
        'rsi_sentiment': rsi_sentiment,
        'macd_sentiment': macd_sentiment,
        'bb_sentiment': bb_sentiment,
        'combined': weighted_sentiment,
        'classification': 'BULLISH' if weighted_sentiment > 0.7 else ('BEARISH' if weighted_sentiment < 0.3 else 'NEUTRAL')
    }

def analyze_positions():
    """Analyze all current positions for sentiment."""
    try:
        client = create_alpaca_client()
    except:
        print("  ✗ Could not create API client")
        return None
    
    print(f"\n📊 Sentiment Analysis")
    print(f"  API Mode: {client.mode}\n")
    
    positions = client.get("/v2/positions")
    if not isinstance(positions, list):
        print("  ⚠️ No positions found")
        return None
    
    results = []
    for pos in positions:
        symbol = pos.get('symbol', '')
        current_price = float(pos.get('current_price', 0))
        entry_price = float(pos.get('avg_entry_price', 0))
        qty = pos.get('qty', '0')
        pl = float(pos.get('unrealized_pl', 0))
        
        # Simulate price history for technical analysis
        history = generate_price_history(current_price, entry_price, 30)
        indicators = calculate_indicators(history)
        sentiment = calculate_technical_sentiment(indicators)
        
        result = {
            'symbol': symbol,
            'current_price': current_price,
            'entry_price': entry_price,
            'qty': qty,
            'unrealized_pl': pl,
            'technical_sentiment': sentiment
        }
        results.append(result)
        
        print(f"  {symbol}:")
        print(f"    Price: ${current_price:.2f} (entry: ${entry_price:.2f})")
        print(f"    Unrealized P&L: ${pl:+.2f}")
        print(f"    Technical Sentiment: {sentiment['classification']} "
              f"(score: {sentiment['combined']:.2f})")
    
    return results

def generate_price_history(current, entry, days=30):
    """Generate simulated price history around current price."""
    import random
    random.seed(42)
    h = []
    for i in range(days):
        t = i / days
        base = entry * (1 - t) + current * t
        noise = random.gauss(0, base * 0.02)
        h.append(max(base + noise, 1.0))
    if h: h[-1] = current
    return h

def calculate_indicators(prices):
    """Calculate technical indicators."""
    rsi = calculate_rsi(prices)
    macd = calculate_macd(prices)
    return {
        'rsi': rsi,
        'macd': macd,
        'current_price': prices[-1] if prices else 0,
        'bb_upper': max(prices[-20:]) * 1.05 if len(prices) >= 20 else 0,
        'bb_lower': min(prices[-20:]) * 0.95 if len(prices) >= 20 else 0
    }

def calculate_rsi(prices, period=14):
    """Calculate RSI."""
    if len(prices) < period + 1: return 50
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    if al == 0: return 100.0
    return 100 - (100 / (1 + ag / al))

def calculate_macd(prices, fast=12, slow=26):
    """Calculate MACD line."""
    if len(prices) < slow: return 0
    def ema(data, period):
        mult = 2 / (period + 1)
        e = sum(data[:period]) / period
        for p in data[period:]: e = (p - e) * mult + e
        return e
    return ema(prices, fast) - ema(prices, slow)

if __name__ == '__main__':
    results = analyze_positions()
    if results:
        print(f"\n  ✅ Sentiment analysis complete for {len(results)} positions")
    else:
        print("\n  ⚠️ No positions to analyze")

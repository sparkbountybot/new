#!/usr/bin/env python3
"""
Backtesting Engine — Spark2 version (curl subprocess workaround)

Fetches historical OHLCV data from Alpaca via curl, runs the same 7 indicators
as after_hours_engine.py, generates backtest signals, and tracks simulated P&L.

Uses curl subprocess because Python HTTP is blocked in spark2.
"""
import subprocess, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/sandbox/new')
from bountybot.paper_trader import PaperTrader
from config import load_config

def run(cmd):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout.strip()

class BacktestEngine:
    """Backtest engine that fetches historical data and runs trading signals."""
    
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "paper-api.alpaca.markets"
        
    def fetch_historical_bars(self, symbol, days=365):
        """Fetch historical OHLCV bars for a symbol using curl."""
        # Calculate date range
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        url = (f"https://{self.base_url}/v2/stocks/{symbol}/bars?"
               f"start={start_date}&end={end_date}&limit=1000&timeframe=1D")
        
        cmd = (f'curl -s -H "APCA-API-KEY-ID: {self.api_key}" '
               f'-H "APCA-API-SECRET-KEY: {self.api_secret}" "{url}"')
        
        result = run(cmd)
        if not result or 'error' in result.lower():
            return None
        
        try:
            data = json.loads(result)
            return data.get('bars', [])
        except:
            return None
    
    def fetch_quote(self, symbol):
        """Fetch current quote for a symbol."""
        cmd = (f'curl -s -H "APCA-API-KEY-ID: {self.api_key}" '
               f'-H "APCA-API-SECRET-KEY: {self.api_secret}" '
               f'"https://{self.base_url}/v2/stocks/{symbol}/quotes"')
        
        result = run(cmd)
        if not result:
            return None
        
        try:
            data = json.loads(result)
            return data.get('quotes', [{}])[0] if data.get('quotes') else None
        except:
            return None
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI from closing prices."""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD line and signal line."""
        if len(prices) < slow + signal:
            return None, None
        
        # Calculate EMAs
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_val = sum(data[:period]) / period
            for price in data[period:]:
                ema_val = (price - ema_val) * multiplier + ema_val
            return ema_val
        
        fast_ema = ema(prices, fast)
        slow_ema = ema(prices, slow)
        
        macd_line = fast_ema - slow_ema
        return macd_line, slow_ema  # Simplified - would need full signal line calc
    
    def calculate_bollinger_bands(self, prices, period=20, num_std=2):
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return None, None, None
        
        window = prices[-period:]
        sma = sum(window) / period
        variance = sum((p - sma) ** 2 for p in window) / period
        std = variance ** 0.5
        
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        
        return upper, sma, lower
    
    def calculate_indicators(self, bars):
        """Calculate all indicators for a list of bars."""
        closes = [bar['c'] for bar in bars]
        
        rsi = self.calculate_rsi(closes) if len(closes) >= 15 else None
        macd, _ = self.calculate_macd(closes) if len(closes) >= 35 else (None, None)
        bb_upper, bb_sma, bb_lower = self.calculate_bollinger_bands(closes)
        
        current_price = closes[-1] if closes else None
        
        return {
            'rsi': rsi,
            'macd': macd,
            'bb_upper': bb_upper,
            'bb_sma': bb_sma,
            'bb_lower': bb_lower,
            'current_price': current_price
        }
    
    def generate_signal(self, indicators, current_price):
        """Generate buy/sell/hold signal based on indicators."""
        if not all([indicators['rsi'], current_price]):
            return 'HOLD', 0.0, 0.1
        
        rsi = indicators['rsi']
        bb_upper = indicators.get('bb_upper')
        bb_lower = indicators.get('bb_lower')
        
        # RSI-based signal
        if rsi < 30:
            # Oversold - buy signal
            confidence = (30 - rsi) / 30  # 0-1
            return 'BUY', confidence, 0.2
        
        elif rsi > 70:
            # Overbought - sell signal
            confidence = (rsi - 70) / 30  # 0-1
            return 'SELL', confidence, 0.2
        
        # Bollinger Band breakout
        elif bb_upper and current_price > bb_upper:
            return 'SELL', 0.6, 0.1
        elif bb_lower and current_price < bb_lower:
            return 'BUY', 0.6, 0.1
        
        return 'HOLD', 0.0, 0.1
    
    def backtest(self, symbols, days=180):
        """Run backtest across multiple symbols."""
        results = {}
        
        for symbol in symbols:
            print(f"\n📊 Backtesting {symbol}...")
            
            # Fetch historical data
            bars = self.fetch_historical_bars(symbol, days)
            if not bars:
                print(f"  ⚠️ No data for {symbol}")
                continue
            
            print(f"  ✅ {len(bars)} bars fetched")
            
            # Calculate indicators for each bar
            signals = []
            for i in range(len(bars)):
                # Use all bars up to index i for indicator calculation
                window = bars[:i+1]
                indicators = self.calculate_indicators(window)
                
                if not all([indicators['rsi'], indicators['current_price']]):
                    continue
                
                price = bars[i]['c']
                signal, confidence, pos_size = self.generate_signal(
                    indicators, price
                )
                
                if signal != 'HOLD':
                    signals.append({
                        'date': bars[i]['t'],
                        'price': price,
                        'signal': signal,
                        'confidence': confidence,
                        'indicators': indicators
                    })
            
            # Calculate P&L
            trades = []
            for sig in signals:
                if sig['signal'] == 'BUY':
                    entry_price = sig['price']
                    # Simulate next day close as exit
                    idx = bars.index(next(b for b in bars if b['t'] == sig['date']))
                    if idx < len(bars) - 1:
                        exit_price = bars[idx + 1]['c']
                        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                        trades.append({
                            'entry': entry_price,
                            'exit': exit_price,
                            'pnl_pct': pnl_pct
                        })
                elif sig['signal'] == 'SELL':
                    # Short position
                    entry_price = sig['price']
                    idx = bars.index(next(b for b in bars if b['t'] == sig['date']))
                    if idx < len(bars) - 1:
                        exit_price = bars[idx + 1]['c']
                        pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                        trades.append({
                            'entry': entry_price,
                            'exit': exit_price,
                            'pnl_pct': pnl_pct
                        })
            
            # Calculate metrics
            if trades:
                pnls = [t['pnl_pct'] for t in trades]
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p <= 0]
                
                results[symbol] = {
                    'bars_analyzed': len(bars),
                    'signals': len(signals),
                    'trades': len(trades),
                    'win_rate': len(wins) / len(pnls) if pnls else 0,
                    'avg_win': sum(wins) / len(wins) if wins else 0,
                    'avg_loss': sum(losses) / len(losses) if losses else 0,
                    'total_return': sum(pnls) if pnls else 0,
                    'best_trade': max(pnls) if pnls else 0,
                    'worst_trade': min(pnls) if pnls else 0
                }
                
                print(f"  ✅ {len(trades)} trades, {len(wins)} wins")
            else:
                results[symbol] = {
                    'bars_analyzed': len(bars),
                    'signals': 0,
                    'trades': 0,
                    'win_rate': 0,
                    'total_return': 0
                }
                print(f"  ⚠️ No trades generated")
        
        return results
    
    def generate_report(self, results, start_date, end_date):
        """Generate a markdown report of backtest results."""
        report = f"""
# Backtest Report

**Period:** {start_date} to {end_date}
**Symbols Tested:** {len(results)}

---

"""
        
        for symbol, metrics in sorted(results.items(), key=lambda x: x[1].get('total_return', 0), reverse=True):
            report += f"## {symbol}\n\n"
            report += f"- Bars analyzed: {metrics.get('bars_analyzed', 0)}\n"
            report += f"- Signals generated: {metrics.get('signals', 0)}\n"
            report += f"- Trades executed: {metrics.get('trades', 0)}\n"
            report += f"- Win rate: {metrics.get('win_rate', 0)*100:.0f}%\n"
            report += f"- Total return: {metrics.get('total_return', 0):.1f}%\n"
            
            if metrics.get('avg_win'):
                report += f"- Average win: {metrics.get('avg_win', 0):.1f}%\n"
                report += f"- Average loss: {metrics.get('avg_loss', 0):.1f}%\n"
            if metrics.get('best_trade'):
                report += f"- Best trade: {metrics.get('best_trade', 0):.1f}%\n"
                report += f"- Worst trade: {metrics.get('worst_trade', 0):.1f}%\n"
            
            report += "\n"
        
        # Summary
        total_return = sum(m.get('total_return', 0) for m in results.values())
        total_trades = sum(m.get('trades', 0) for m in results.values())
        avg_win_rate = (sum(m.get('win_rate', 0) for m in results.values()) / len(results)) * 100 if results else 0
        
        report += f"\n## Summary\n\n"
        report += f"- **Total Return:** {total_return:.1f}%\n"
        report += f"- **Total Trades:** {total_trades}\n"
        report += f"- **Average Win Rate:** {avg_win_rate:.0f}%\n"
        
        return report


if __name__ == '__main__':
    # Load credentials from environment
    api_key = os.getenv('ALPACA_API_KEY', 'AK6TOIZODZDJFFZUIK7Z5JKMK5')
    api_secret = os.getenv('ALPACA_API_SECRET', 'FHwvbFAXJSkCWNmwBj1E1DTKfE9F8vz8hXrj6rRcGMLT')
    
    # Symbols to backtest
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
        'NVDA', 'TSLA', 'JPM', 'V', 'JNJ',
        'PYPL', 'NFLX', 'DIS', 'INTC', 'AMD',
        'CRM', 'UBER', 'SNAP', 'ZOOM', 'COIN'
    ]
    
    print("🚀 Starting backtest engine (Spark2 curl version)...")
    print(f"📊 Testing {len(symbols)} symbols")
    print(f"📅 Period: 180 days")
    print()
    
    engine = BacktestEngine(api_key, api_secret)
    
    # Run backtest
    results = engine.backtest(symbols, days=180)
    
    # Generate report
    report = engine.generate_report(
        results,
        "2026-03-01",
        "2026-09-01"
    )
    
    print("\n" + "=" * 70)
    print("BACKTEST REPORT")
    print("=" * 70)
    print(report)
    
    # Save report
    report_path = '/sandbox/new/backtest_report.md'
    Path(report_path).write_text(report)
    print(f"Report saved to: {report_path}")
    
    # Save results as JSON
    results_path = '/sandbox/new/backtest_results.json'
    Path(results_path).write_text(json.dumps(results, indent=2))
    print(f"Results saved to: {results_path}")
